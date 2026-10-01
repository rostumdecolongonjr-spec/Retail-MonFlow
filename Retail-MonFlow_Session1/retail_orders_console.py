"""
retail_orders_console.py - Retail-Orders Session 1 Parallel Compute Console

Desktop GUI (Tkinter, standard library only) over the Session 1 pipeline.

Nothing on screen is typed in by hand. Every table is read from the files the
pipeline scripts write to results/, and every "Run" button executes the real
script (python <script>.py) and streams its output into the Console tab:

    profile_files.py       -> results/file_profile.json
    load_and_join.py       -> results/working_dataset.parquet | .pkl
    partition_strategy.py  -> results/partition_strategy.json
    sequential_baseline.py -> results/baseline_result.csv
    parallel_compute.py    -> results/validation_report.json, category_revenue.parquet
    benchmark.py           -> results/session1_benchmark.csv
    partition_analysis.py  -> results/partition_sizes.csv
    render_diagrams.py     -> docs/*.png, architecture/*.png

A stage whose output file is missing is shown as NOT RUN, never with a
placeholder number. Re-running a stage on another machine changes the
console because the numbers come from that run.

Put this file in the session1 folder next to config.py and run:
    python retail_orders_console.py            # GUI
    python retail_orders_console.py --check    # print what results/ contains
    python retail_orders_console.py --dir PATH # if the scripts live elsewhere

The console finds the pipeline folder (the one with config.py and
profile_files.py) by itself if it is the console's own folder, its parent,
a subfolder, or a sibling folder; otherwise use --dir or the
"Choose pipeline folder" button.
"""

from __future__ import annotations

import csv
import json
import os
import queue
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

CONSOLE_DIR = Path(__file__).resolve().parent
PIPELINE_MARKERS = ("config.py", "profile_files.py")


def is_pipeline_dir(d: Path) -> bool:
    return all((d / m).is_file() for m in PIPELINE_MARKERS)


CONSOLE_VERSION = "v4 - finds the pipeline folder"

# Your pipeline folder, tried FIRST (taken from your own PowerShell prompt), then
# your course folder searched 5 levels deep. Edit these lines if you move things.
KNOWN_PIPELINE_DIRS = [
    Path(r"C:\Users\rostu\OneDrive\Desktop\Master Files\MIT261- DECOLONGON, ROSTUM JR"
         r"\session1_parralel_compute"),
]
PREFERRED_ROOTS = [
    Path(r"C:\Users\rostu\OneDrive\Desktop\Master Files\MIT261- DECOLONGON, ROSTUM JR"),
]
SAVED_LOCATION = CONSOLE_DIR / "pipeline_location.txt"
_SKIP = {"results", "datasets", "docs", "architecture", "__pycache__", ".git", ".venv",
         "venv", "node_modules", "stream_log"}


def save_pipeline_dir(d: Path) -> None:
    try:
        SAVED_LOCATION.write_text(str(d), encoding="utf-8")
    except OSError:
        pass


def _walk(root: Path, max_depth: int, budget=20000):
    stack, seen = [(root, 0)], set()
    while stack and budget:
        d, depth = stack.pop()
        try:
            key = d.resolve()
            if key in seen:
                continue
            seen.add(key)
            budget -= 1
            yield d
            if depth < max_depth:
                stack += [(c, depth + 1) for c in d.iterdir()
                          if c.is_dir() and not c.name.startswith(".")
                          and c.name.lower() not in _SKIP]
        except OSError:
            continue


def find_pipeline_dir(explicit: str | None = None) -> Path | None:
    """
    The folder holding config.py and the Session 1 scripts, in this order:
      1. --dir PATH
      2. the folder chosen earlier with the button (pipeline_location.txt)
      3. KNOWN_PIPELINE_DIRS
      4. this console's folder, its parent, subfolders and siblings
      5. PREFERRED_ROOTS, 5 levels deep (session1-named folders win ties)
    """
    if explicit:
        p = Path(explicit).expanduser().resolve()
        return p if is_pipeline_dir(p) else None
    candidates = []
    if SAVED_LOCATION.exists():
        try:
            candidates.append(Path(SAVED_LOCATION.read_text(encoding="utf-8").strip()))
        except OSError:
            pass
    candidates += KNOWN_PIPELINE_DIRS
    here, parent = CONSOLE_DIR, CONSOLE_DIR.parent
    candidates += [here, parent]
    try:
        candidates += sorted(d for d in here.iterdir() if d.is_dir())
        siblings = sorted(d for d in parent.iterdir() if d.is_dir() and d != here)
        candidates += sorted(siblings, key=lambda d: "session1" not in d.name.lower())
    except OSError:
        pass
    for d in candidates:
        try:
            if is_pipeline_dir(d):
                return d.resolve()
        except OSError:
            continue
    found = [d for r in PREFERRED_ROOTS if r.is_dir() for d in _walk(r, 5) if is_pipeline_dir(d)]
    if found:
        found.sort(key=lambda d: ("session1" not in str(d).lower().replace("_", "").replace(" ", ""),
                                  not (d / "results").is_dir(), len(d.parts)))
        return found[0].resolve()
    return None


HERE = CONSOLE_DIR                 # replaced by set_pipeline_dir() at start-up
RESULTS = HERE / "results"
DIAGRAMS: list = []


def set_pipeline_dir(d: Path | None) -> None:
    global HERE, RESULTS, DIAGRAMS
    HERE = d if d is not None else CONSOLE_DIR
    RESULTS = HERE / "results"
    DIAGRAMS = [HERE / "docs" / "entity-model-session1.png",
                HERE / "architecture" / "architecture-session1.png"]


def load_config():
    """Import the pipeline's config.py from HERE, whatever folder that is."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("config", HERE / "config.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
NAVY = "#16233d"
NAVY2 = "#1f3358"
BLUE = "#2e5aa8"
GREEN = "#2e7d32"
GREEN_BG = "#e9f5ea"
AMBER = "#b5590a"
AMBER_BG = "#fdf0e2"
AMBER_BORDER = "#e4a765"
RED = "#a33636"
RED_BG = "#fbeaea"
GOLD_BG = "#fff3d6"
GOLD_FG = "#9a6a00"
GREY = "#5b6472"
GREY_LINE = "#d9dee6"
INK = "#1c2430"
BG = "#eef1f6"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUB = ("Segoe UI", 10)
FONT_SECTION = ("Segoe UI", 12, "bold")
FONT_STAT = ("Segoe UI", 22, "bold")
FONT_MONO_SM = ("Consolas", 9)

# (key, label, script, engine, output files that prove it ran)
STAGES = [
    ("profile", "1. Profile files", "profile_files.py", "pandas", ["file_profile.json"]),
    ("join", "2. Load and join", "load_and_join.py", "pandas",
     ["working_dataset.parquet", "working_dataset.pkl"]),
    ("strategy", "3. Partition strategy", "partition_strategy.py", "pandas",
     ["partition_strategy.json"]),
    ("baseline", "4. Sequential baseline", "sequential_baseline.py", "pandas",
     ["baseline_result.csv"]),
    ("parallel", "5. Parallel compute", "parallel_compute.py", "Spark",
     ["validation_report.json"]),
    ("benchmark", "6. Benchmark", "benchmark.py", "Spark", ["session1_benchmark.csv"]),
    ("balance", "7. Partition balance", "partition_analysis.py", "Spark",
     ["partition_sizes.csv"]),
    ("diagrams", "Render diagrams", "render_diagrams.py", "graphviz", []),
]


# ===========================================================================
# Reading results/
# ===========================================================================
def _read_json(name):
    p = RESULTS / name
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None
    except (OSError, json.JSONDecodeError):
        return None


def _read_csv(name):
    p = RESULTS / name
    if not p.is_file():
        return None
    with open(p, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _size(p: Path) -> str:
    n = p.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024


class Results:
    """Everything the console shows, loaded from disk in one place."""

    def __init__(self):
        self.reload()

    def reload(self):
        self.profile = _read_json("file_profile.json")
        self.strategy = _read_json("partition_strategy.json")
        self.validation = _read_json("validation_report.json")
        self.baseline = _read_csv("baseline_result.csv")
        self.bench = _read_csv("session1_benchmark.csv")
        self.psizes = _read_csv("partition_sizes.csv")
        self.loaded_at = time.strftime("%Y-%m-%d %H:%M:%S")

    # ---- derived values -------------------------------------------------
    def has(self, key):
        outs = next(s[4] for s in STAGES if s[0] == key)
        if key == "diagrams":
            return all(p.is_file() for p in DIAGRAMS)
        return any((RESULTS / o).is_file() for o in outs)

    def join_report(self):
        if self.strategy and "join" in self.strategy:
            return self.strategy["join"]
        return None

    def baseline_rows(self):
        if not self.baseline:
            return []
        return [{"category_id": int(float(r["category_id"])),
                 "line_count": int(float(r["line_count"])),
                 "revenue_total": float(r["revenue_total"]),
                 "revenue_mean": float(r["revenue_mean"])} for r in self.baseline]

    def bench_rows(self):
        if not self.bench:
            return None, []
        base, par = None, []
        for r in self.bench:
            t = float(r["execution_time_s"])
            if r["run"].lower().startswith("sequential"):
                base = t
            else:
                par.append({"partitions": int(float(r["parallelism_partitions"])),
                            "median": t, "groups": r["groups"],
                            "speedup": float(r["speedup_vs_baseline"]),
                            "observation": r.get("observation", "")})
        return base, par

    def best_parallel(self):
        base, par = self.bench_rows()
        if base is None or not par:
            return None
        best = min(par, key=lambda r: r["median"])
        return {**best, "baseline": base, "slowdown": best["median"] / base}

    def partition_levels(self):
        """{n: [sizes]} for physical partitions, plus key-level counts."""
        phys, keys = {}, {}
        for r in self.psizes or []:
            if r["level"] == "spark_partition":
                phys.setdefault(int(r["setting"]), []).append(int(r["record_count"]))
            elif r["level"] == "partition_key":
                keys[r["identifier"]] = int(r["record_count"])
        return phys, keys

    def artefacts(self):
        writers = {"file_profile.json": "profile_files.py",
                   "working_dataset.parquet": "load_and_join.py",
                   "working_dataset.pkl": "load_and_join.py (parquet fallback)",
                   "partition_strategy.json": "partition_strategy.py",
                   "baseline_result.csv": "sequential_baseline.py",
                   "category_revenue.parquet": "parallel_compute.py",
                   "category_revenue.pkl": "parallel_compute.py (parquet fallback)",
                   "validation_report.json": "parallel_compute.py",
                   "session1_benchmark.csv": "benchmark.py",
                   "partition_sizes.csv": "partition_analysis.py"}
        rows = []
        for name, by in writers.items():
            p = RESULTS / name
            if p.is_file():
                rows.append((f"results/{name}", by, "written", _size(p),
                             time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)),
                             "done"))
            elif not name.endswith((".pkl",)) and not (
                    name.endswith(".parquet") and (RESULTS / name.replace(".parquet", ".pkl")).is_file()):
                rows.append((f"results/{name}", by, "missing", "-", "-", "pending"))
        for p in DIAGRAMS:
            rel = p.relative_to(HERE).as_posix()
            rows.append((rel, "render_diagrams.py", "written" if p.is_file() else "missing",
                         _size(p) if p.is_file() else "-",
                         time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
                         if p.is_file() else "-", "done" if p.is_file() else "pending"))
        return rows

    def headline(self, key):
        try:
            if key == "profile" and self.profile:
                integ = self.profile["integrity"]["foreign_keys_resolve"]
                elig = self.profile["eligibility"]
                met = sum(1 for v in elig.values() if v["met"])
                return (f"{len(self.profile['profiles'])} files profiled · "
                        f"{sum(integ.values())}/{len(integ)} foreign keys resolve · "
                        f"{met}/{len(elig)} eligibility conditions met")
            if key == "join" and self.join_report():
                j = self.join_report()
                return (f"{j['join_path']} - {j['rows_before']:,} -> {j['rows_after']:,} rows, "
                        f"{j['columns_after']} columns, {j['join_seconds']} s")
            if key == "join" and self.has("join"):
                return "working dataset written (run Partition strategy for the join report)"
            if key == "strategy" and self.strategy:
                p = self.strategy["prediction"]
                cands = self.strategy["all_candidates"]
                viable = sum(1 for c in cands if c["viable"])
                return (f"{self.strategy['chosen_key']} chosen: {p['distinct']} groups, "
                        f"{p['skew_ratio']}:1 skew - {viable} viable of {len(cands)} "
                        f"columns scored")
            if key == "baseline" and self.baseline:
                rows = self.baseline_rows()
                total = sum(r["revenue_total"] for r in rows)
                return f"{len(rows)} groups · total revenue {total:,.2f}"
            if key == "parallel" and self.validation:
                v, j = self.validation["validation"], self.validation["join"]
                a = self.validation["aggregation"]
                return (f"{j['rows_before']:,} -> {j['rows_after']:,} rows, {a['groups']} groups, "
                        f"{'PASSED' if v['passed'] else 'FAILED'} correctness in "
                        f"{a['seconds']} s ({a['partitions']} partitions)")
            if key == "benchmark" and self.bench:
                b = self.best_parallel()
                word = "slower" if b["slowdown"] > 1 else "faster"
                factor = b["slowdown"] if b["slowdown"] > 1 else 1 / b["slowdown"]
                return (f"best: {b['partitions']} partitions at {b['median']:.4f} s median - "
                        f"{factor:.1f}x {word} than the {b['baseline']:.4f} s pandas baseline")
            if key == "balance" and self.psizes:
                phys, keys = self.partition_levels()
                ns = sorted(phys)
                ratio = lambda s: max(s) / min(s) if min(s) else float("inf")  # noqa: E731
                k = max(keys.values()) / min(keys.values()) if keys else 0
                return (f"key-level skew {k:.2f}:1; physical-partition skew "
                        + " · ".join(f"{n}p {ratio(phys[n]):.2f}:1" for n in ns))
            if key == "diagrams" and self.has("diagrams"):
                return " + ".join(p.name for p in DIAGRAMS) + " rendered"
        except (KeyError, ValueError, TypeError, ZeroDivisionError) as exc:
            return f"results file present but unreadable ({type(exc).__name__}: {exc})"
        return f"not run - run {next(s[2] for s in STAGES if s[0] == key)}"


# ===========================================================================
# Widgets (only constructed when the GUI runs)
# ===========================================================================
tk = ttk = scrolledtext = None


class _ScrollableTab:
    """A tab page that scrolls; the wheel is bound only while the pointer is over it."""

    def __init__(self, parent):
        self.frame = tk.Frame(parent, bg=BG)
        canvas = tk.Canvas(self.frame, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self.frame, orient="vertical", command=canvas.yview)
        self.body = tk.Frame(canvas, bg=BG, padx=22, pady=18)
        self.body.bind("<Configure>",
                       lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def wheel(e):
            if getattr(e, "num", None) in (4, 5):
                canvas.yview_scroll(-1 if e.num == 4 else 1, "units")
            else:
                canvas.yview_scroll(int(-e.delta / 120) or (-1 if e.delta > 0 else 1), "units")

        def enter(_):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.bind_all(ev, wheel)

        def leave(_):
            for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                canvas.unbind_all(ev)

        self.frame.bind("<Enter>", enter)
        self.frame.bind("<Leave>", leave)


def stat_card(parent, value, label, value_color=NAVY2):
    frame = tk.Frame(parent, bg="white", highlightbackground=GREY_LINE,
                     highlightthickness=1, bd=0)
    tk.Label(frame, text=value, font=FONT_STAT, fg=value_color, bg="white").pack(pady=(16, 4))
    tk.Label(frame, text=label, font=("Segoe UI", 9), fg=GREY, bg="white",
             wraplength=200, justify="center").pack(pady=(0, 14), padx=8)
    return frame


def banner(parent, text, kind="amber"):
    colours = {"amber": (AMBER_BG, AMBER_BORDER, "#5c2f00"),
               "green": (GREEN_BG, "#9bcf9e", "#173d19"),
               "red": (RED_BG, "#e3a0a0", "#5c1414"),
               "grey": ("white", GREY_LINE, GREY)}
    bgc, bd, fgc = colours[kind]
    outer = tk.Frame(parent, bg=bd)
    inner = tk.Frame(outer, bg=bgc)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Label(inner, text=text, bg=bgc, fg=fgc, font=("Segoe UI", 9), justify="left",
             wraplength=1080, anchor="w").pack(padx=16, pady=12, anchor="w", fill="x")
    return outer


def section_title(parent, text):
    return tk.Label(parent, text=text, font=FONT_SECTION, fg=NAVY2, bg=BG, anchor="w")


def note(parent, text):
    return tk.Label(parent, text=text, bg=BG, fg=GREY, font=("Segoe UI", 9),
                    wraplength=1080, justify="left", anchor="w")


def card(parent):
    outer = tk.Frame(parent, bg=GREY_LINE)
    inner = tk.Frame(outer, bg="white")
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return outer, inner


TAGS = {"done": (GREEN_BG, GREEN), "pass": (GREEN_BG, GREEN), "pending": (AMBER_BG, AMBER),
        "fail": (RED_BG, RED), "rejected": (RED_BG, RED), "viable": (GREEN_BG, GREEN),
        "chosen": (GOLD_BG, GOLD_FG), "running": ("#e8eef8", BLUE)}


def make_table(parent, columns, widths, rows, height=None, tagged=False):
    """If tagged, the LAST element of each row is a tag name from TAGS."""
    container = tk.Frame(parent, bg=GREY_LINE)
    inner = tk.Frame(container, bg="white")
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    n = len(rows) if height is None else height
    tree = ttk.Treeview(inner, columns=columns, show="headings",
                        height=min(max(n, 1), 16), style="Console.Treeview")
    for c, w in zip(columns, widths):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")
    tree.grid(row=0, column=0, sticky="nsew")
    if len(rows) > min(max(n, 1), 16):
        vsb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
    inner.grid_columnconfigure(0, weight=1)
    for row in rows:
        if tagged:
            tree.insert("", "end", values=[str(v) for v in row[:-1]], tags=(row[-1],))
        else:
            tree.insert("", "end", values=[str(v) for v in row])
    for tag, (bgc, fgc) in TAGS.items():
        tree.tag_configure(tag, background=bgc, foreground=fgc)
    return container


def not_run(root, *scripts):
    banner(root, "Not run yet - no output file in results/. Run "
           + ", then ".join(scripts) + " from the Pipeline tab.", "grey"
           ).pack(fill="x", pady=(0, 14))


# ===========================================================================
# App
# ===========================================================================
class ConsoleApp:
    TABS = [("Pipeline", "pipeline"), ("Files & eligibility", "files"),
            ("Join & partition key", "join"), ("Baseline vs parallel", "baseline"),
            ("Correctness & output", "correctness"), ("Partition balance", "balance")]

    def __init__(self):
        self.res = Results()
        self.q = queue.Queue()
        self.busy = False
        self.exit_codes: dict[str, int] = {}
        self.running: str | None = None

        self.root = tk.Tk()
        self.root.title(f"Retail-Orders — Session 1 Parallel Compute Console  ({CONSOLE_VERSION})")
        self.root.geometry("1240x840")
        self.root.configure(bg=BG)
        self._style()
        self._header()
        self._tabs()
        self.refresh()
        self.root.after(100, self._poll)

    # ---------------- chrome ----------------
    def _style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=FONT_BOLD, padding=(16, 10),
                        background="white", foreground=GREY)
        style.map("TNotebook.Tab", background=[("selected", "white")],
                  foreground=[("selected", NAVY2)])
        style.configure("Console.Treeview", rowheight=24, font=FONT, fieldbackground="white")
        style.configure("Console.Treeview.Heading", font=FONT_BOLD, background=NAVY,
                        foreground="white")
        style.map("Console.Treeview.Heading", background=[("active", NAVY)])

    def _header(self):
        header = tk.Frame(self.root, bg=NAVY2)
        header.pack(fill="x")
        tk.Label(header, text="Retail-Orders — Session 1 Parallel Compute Console",
                 bg=NAVY2, fg="white", font=FONT_TITLE).pack(anchor="w", padx=26, pady=(16, 2))
        self.subtitle = tk.Label(header, bg=NAVY2, fg="#c7d2e6", font=FONT_SUB)
        self.subtitle.pack(anchor="w", padx=26, pady=(0, 4))
        self.status = tk.Label(header, bg=NAVY2, fg="#ffd27a", font=("Segoe UI", 9))
        self.status.pack(anchor="w", padx=26, pady=(0, 12))

    def _subtitle_text(self):
        if not is_pipeline_dir(HERE):
            return ("MIT 261 Parallel and Distributed Systems   ·   pipeline folder not "
                    "found - click 'Choose pipeline folder…'")
        try:
            cfg = load_config()  # the pipeline's own settings, not a copy
            return (f"MIT 261 Parallel and Distributed Systems   ·   partition key "
                    f"{cfg.PARTITION_KEY}   ·   bounded parallelism {cfg.CHOSEN_PARTITIONS}"
                    f"   ·   settings {tuple(cfg.PARTITION_SETTINGS)}   ·   {cfg.SPARK_MASTER}")
        except Exception as exc:                                  # noqa: BLE001
            return f"MIT 261 Parallel and Distributed Systems   ·   config.py not importable ({exc})"

    def _tabs(self):
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True)
        self.bodies = {}
        for label, key in self.TABS:
            page = _ScrollableTab(self.nb)
            self.nb.add(page.frame, text=label)
            self.bodies[key] = page.body
        self._console_tab()

    def _console_tab(self):
        f = tk.Frame(self.nb, bg=BG, padx=22, pady=18)
        self.nb.add(f, text="Console")
        bar = tk.Frame(f, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        tk.Label(bar, text="Live output of every script run from this console",
                 font=FONT_SECTION, fg=NAVY2, bg=BG).pack(side="left")
        tk.Button(bar, text="Clear", command=lambda: self.text.delete("1.0", "end"),
                  relief="solid", bd=1, font=("Segoe UI", 9), padx=8).pack(side="right")
        tk.Button(bar, text="Save transcript…", command=self._save, relief="solid", bd=1,
                  font=("Segoe UI", 9), padx=8).pack(side="right", padx=6)
        self.text = scrolledtext.ScrolledText(f, bg="#0f1a2e", fg="#c9d6ea", font=FONT_MONO_SM,
                                              insertbackground="white", bd=0, padx=16,
                                              pady=14, wrap="word")
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("h", foreground="#7fd8ff")
        self.text.tag_configure("g", foreground="#8fdc8f")
        self.text.tag_configure("a", foreground="#ffcf8f")
        self.text.tag_configure("r", foreground="#ff9b9b")
        self._log(f"Results folder: {RESULTS}", "h")
        self._log("Tables are read from results/. Press a Run button on the Pipeline tab to "
                  "execute a script; its output appears here.")

    def _log(self, line, tag=None):
        if tag is None:
            up = line.upper()
            if "PASSED" in up or line.strip().startswith("PASS") or "MET " in line:
                tag = "g"
            elif "FAIL" in up or "ERROR" in up or "TRACEBACK" in up or "EXCEPTION" in up:
                tag = "r"
            elif line.startswith("=") or line.startswith("$"):
                tag = "h"
            elif "SLOWER" in up or "WORSENS" in up or "WARNING" in up:
                tag = "a"
        self.text.insert("end", line + "\n", tag or ())
        self.text.see("end")

    def _save(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".txt",
                                            initialfile="session1_transcript.txt")
        if path:
            Path(path).write_text(self.text.get("1.0", "end"), encoding="utf-8")

    def choose_folder(self):
        from tkinter import filedialog, messagebox
        if self.busy:
            return
        path = filedialog.askdirectory(title="Folder with config.py and profile_files.py",
                                       initialdir=str(CONSOLE_DIR.parent))
        if not path:
            return
        d = Path(path)
        if not is_pipeline_dir(d):
            messagebox.showerror("Not the pipeline folder",
                                 f"{d} does not contain {' and '.join(PIPELINE_MARKERS)}.")
            return
        set_pipeline_dir(d)
        save_pipeline_dir(d)                 # remembered next time the console opens
        self.exit_codes.clear()
        self.res.reload()
        self._log(f"Pipeline folder: {HERE}", "h")
        self.status.config(text=f"Using {HERE}")
        self.refresh()

    # ---------------- running scripts ----------------
    def run_stages(self, keys):
        if self.busy:
            self.status.config(text="Busy - wait for the current script to finish.")
            return
        if not is_pipeline_dir(HERE):
            self.choose_folder()
            return
        self.busy = True
        here = HERE

        def worker():
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
            for key in keys:
                script = next(s[2] for s in STAGES if s[0] == key)
                self.q.put(("start", key))
                self.q.put(("line", f"$ python {script}"))
                if not (here / script).is_file():
                    self.q.put(("line", f"  {script} not found in {here}"))
                    self.q.put(("end", (key, 127)))
                    continue
                proc = subprocess.Popen([sys.executable, "-u", script], cwd=here, env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
                for line in proc.stdout:
                    self.q.put(("line", line.rstrip("\n")))
                code = proc.wait()
                self.q.put(("line", f"  -> exit code {code}"))
                self.q.put(("end", (key, code)))
            self.q.put(("done", None))

        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        dirty = False
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "line":
                    self._log(payload)
                elif kind == "start":
                    self.running = payload
                    self.status.config(text=f"Running {payload} …")
                    dirty = True
                elif kind == "end":
                    key, code = payload
                    self.exit_codes[key] = code
                    self.running = None
                    dirty = True
                elif kind == "done":
                    self.busy = False
                    failed = [k for k, c in self.exit_codes.items() if c]
                    self.status.config(text="Ready." if not failed else
                                       f"Ready - failed: {', '.join(failed)} (see Console)")
                    dirty = True
        except queue.Empty:
            pass
        if dirty:
            self.res.reload()
            self.refresh()
        self.root.after(100, self._poll)

    # ---------------- rendering ----------------
    def refresh(self):
        self.subtitle.config(text=self._subtitle_text())
        if not self.busy:
            self.status.config(text=self.status.cget("text") or
                               f"results/ loaded {self.res.loaded_at}")
        for key, body in self.bodies.items():
            for w in body.winfo_children():
                w.destroy()
            getattr(self, "build_" + key)(body)

    def _stage_state(self, key):
        if self.running == key:
            return "running", "running"
        code = self.exit_codes.get(key)
        if code == 127:
            return "script missing", "fail"
        if code:
            return f"failed ({code})", "fail"
        if self.res.has(key):
            return "completed", "done"
        return "not run", "pending"

    # ---------------- PIPELINE ----------------
    def build_pipeline(self, root):
        r = self.res
        j = r.join_report() or (r.validation or {}).get("join")
        base_rows = r.baseline_rows()
        best = r.best_parallel()
        stats = tk.Frame(root, bg=BG)
        stats.pack(fill="x", pady=(0, 16))
        for i in range(4):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")
        cards = [
            (f"{j['rows_after']:,}" if j else "-", "rows through the join", NAVY2),
            (str(len(base_rows)) if base_rows else "-",
             f"groups in the result ({(r.strategy or {}).get('chosen_key', 'partition key')})", NAVY2),
            (f"{best['baseline']:.4f}s" if best else "-",
             "pandas baseline median (benchmark.py run)", NAVY2),
            ((f"{best['slowdown']:.1f}x slower" if best['slowdown'] > 1
              else f"{1 / best['slowdown']:.1f}x faster") if best else "-",
             f"best Spark setting ({best['partitions']} partitions) vs that baseline"
             if best else "best Spark setting vs pandas baseline",
             AMBER if best and best["slowdown"] > 1 else GREEN),
        ]
        for i, (v, lab, col) in enumerate(cards):
            stat_card(stats, v, lab, col).grid(row=0, column=i, sticky="nsew",
                                               padx=(0 if i == 0 else 8, 0))

        if not is_pipeline_dir(HERE):
            banner(root, f"Pipeline scripts not found. This console is in {CONSOLE_DIR} but "
                         f"there is no config.py + profile_files.py there, in its parent, "
                         f"its subfolders or its sibling folders. Either move "
                         f"retail_orders_console.py into your Session 1 folder (the one with "
                         f"config.py and the Datasets/ folder), or click 'Choose pipeline "
                         f"folder…' below.", "red").pack(fill="x", pady=(0, 10))
            tk.Button(root, text="Choose pipeline folder…", relief="solid", bd=1, bg=NAVY2,
                      fg="white", font=("Segoe UI", 10, "bold"), padx=10, pady=4,
                      command=self.choose_folder).pack(anchor="w", pady=(0, 18))
            return
        done = sum(1 for s in STAGES if self._stage_state(s[0])[1] == "done")
        failed = [s[1] for s in STAGES if self._stage_state(s[0])[1] == "fail"]
        kind = "red" if failed else ("green" if done == len(STAGES) else "amber")
        msg = (f"{done} of {len(STAGES)} stages have output in results/."
               + (f" Failed this session: {', '.join(failed)} - see the Console tab." if failed else "")
               + " Every number in this console is read from those files; a missing file "
                 "shows as 'not run' rather than a placeholder.")
        if any(self._stage_state(k)[1] != "done" for k in ("parallel", "benchmark", "balance")):
            msg += (" Spark stages need Java (JDK 17) and pyspark - if they fail with a JVM "
                    "error, set JAVA_HOME to a JDK 17 install and reopen the terminal.")
        banner(root, msg, kind).pack(fill="x", pady=(0, 18))

        bar = tk.Frame(root, bg=BG)
        bar.pack(fill="x", pady=(0, 8))
        section_title(bar, "Run a stage").pack(side="left", padx=(0, 12))
        for key, label, _, _, _ in STAGES:
            tk.Button(bar, text=label.split(". ")[-1], relief="solid", bd=1, bg="white",
                      fg=NAVY2, font=("Segoe UI", 9), padx=6,
                      command=lambda k=key: self.run_stages([k])).pack(side="left", padx=2)
        tk.Button(bar, text="Run everything", relief="solid", bd=1, bg=NAVY2, fg="white",
                  font=("Segoe UI", 9, "bold"), padx=8,
                  command=lambda: self.run_stages([s[0] for s in STAGES])
                  ).pack(side="left", padx=(10, 2))
        tk.Button(bar, text="Reload results/", relief="solid", bd=1, bg="white", fg=NAVY2,
                  font=("Segoe UI", 9), padx=6,
                  command=lambda: (self.res.reload(), self.refresh())).pack(side="left", padx=2)
        tk.Button(bar, text="Change folder…", relief="solid", bd=1, bg="white", fg=NAVY2,
                  font=("Segoe UI", 9), padx=6, command=self.choose_folder
                  ).pack(side="left", padx=2)
        tk.Label(root, text=f"Pipeline folder: {HERE}", bg=BG, fg=GREY,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 6))

        rows = []
        for key, label, script, engine, _ in STAGES:
            state, tag = self._stage_state(key)
            rows.append((label, engine, state, r.headline(key), tag))
        make_table(root, ("Stage", "Engine", "Status", "Headline result"),
                   (170, 80, 100, 800), rows, tagged=True).pack(fill="x", pady=(0, 20))

        section_title(root, f"Artefacts ({HERE.name}/)").pack(anchor="w", pady=(0, 8))
        make_table(root, ("Artefact", "Written by", "Status", "Size", "Last written"),
                   (300, 290, 90, 100, 150), r.artefacts(), tagged=True).pack(fill="x")

    # ---------------- FILES & ELIGIBILITY ----------------
    def build_files(self, root):
        p = self.res.profile
        if not p:
            return not_run(root, "profile_files.py")
        profs = p["profiles"]
        section_title(root, f"{len(profs)} input files").pack(anchor="w", pady=(0, 8))
        rows = [(x["file"], x["role"], f"{x['rows']:,}", x["columns"], f"{x['size_kb']:,} KB",
                 ", ".join(x["candidate_primary_keys"]) or "-",
                 ", ".join(x["constant_columns"]) or "-") for x in profs.values()]
        make_table(root, ("File", "Role", "Rows", "Cols", "Size", "Candidate primary key(s)",
                          "Constant columns"), (160, 70, 90, 50, 100, 260, 140), rows
                   ).pack(fill="x", pady=(0, 20))

        integ = p["integrity"]
        fks = integ["foreign_keys_resolve"]
        orphans = sum(integ["orphan_counts"].values())
        section_title(root, f"Referential integrity - {len(fks)} foreign keys, "
                            f"{sum(fks.values())}/{len(fks)} pass, {orphans:,} orphans"
                      ).pack(anchor="w", pady=(0, 8))
        orphan_vals = list(integ["orphan_counts"].values())
        make_table(root, ("Foreign key", "Result", "Orphan rows"), (480, 90, 120),
                   [(lab, "PASS" if ok else "FAIL", f"{orphan_vals[i]:,}",
                     "pass" if ok else "fail") for i, (lab, ok) in enumerate(fks.items())],
                   tagged=True).pack(fill="x", pady=(0, 20))

        e = p["eligibility"]
        met = sum(1 for v in e.values() if v["met"])
        section_title(root, f"Dataset eligibility (Part 2) - {met}/{len(e)} conditions met"
                      ).pack(anchor="w", pady=(0, 8))
        c1, c2, c3, c4 = (e["condition_1_three_related_files"], e["condition_2_one_to_many"],
                          e["condition_3_timestamp"], e["condition_4_volume"])
        assoc = []
        for a in c2["associations"]:
            txt = (f"{a['parent']} -> {a['child']} (min {a['children_min']}, median "
                   f"{a['children_median']}, max {a['children_max']} per {a['parent'][:-1]})")
            if a.get("parents_without_children"):
                txt += (f"; {a['parents_without_children']:,} of {a['parents_total']:,} "
                        f"{a['parent']} have none, so the multiplicity is 0..*, not 1..*")
            assoc.append(txt)
        ones = [n for n, flag in (("payments", c2["payments_is_one_to_one"]),
                                  ("shipments", c2["shipments_is_one_to_one"])) if flag]
        conditions = [
            ("Condition 1 - at least 3 qualifying files", c1["met"],
             f"{len(c1['qualifying_files'])} Event/Entity files qualify (Lookup files "
             f"{', '.join(c1['lookup_files_excluded'])} excluded)."),
            ("Condition 2 - genuine one-to-many association", c2["met"],
             "; ".join(assoc) + "." + (f" {' and '.join(ones)}.order_id "
                                       f"{'is' if len(ones) == 1 else 'are'} unique -> 1:1 "
                                       f"extension(s) of Order." if ones else "")),
            ("Condition 3 - usable timestamp", c3["met"],
             f"{c3['field']}, {c3['min'][:10]} -> {c3['max'][:10]} ({c3['span_days']:,}-day span)."),
            ("Condition 4 - transactional volume", c4["met"],
             f"{c4['event_rows']:,} combined Event rows >= 50,000 minimum."),
        ]
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="c")
        grid.grid_columnconfigure(1, weight=1, uniform="c")
        for i, (title, ok, body) in enumerate(conditions):
            outer, inner = card(grid)
            outer.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            tk.Label(inner, text=("\u2713 " if ok else "\u2717 ") + title, font=FONT_BOLD,
                     fg=NAVY2 if ok else RED, bg="white", anchor="w"
                     ).pack(anchor="w", padx=14, pady=(12, 4))
            tk.Label(inner, text=body, font=("Segoe UI", 9), fg=INK, bg="white",
                     wraplength=500, justify="left", anchor="w"
                     ).pack(anchor="w", padx=14, pady=(0, 12))

    # ---------------- JOIN & PARTITION KEY ----------------
    def build_join(self, root):
        s, v = self.res.strategy, self.res.validation
        section_title(root, "Join path (Part 4)").pack(anchor="w", pady=(0, 8))
        flow = tk.Frame(root, bg="#0f1a2e")
        flow.pack(fill="x", pady=(0, 16))
        if v:
            sj = v["join"]
            if sj["sort_merge_joins"] == 0:
                strat = ("ACTUAL Spark plan: no SortMergeJoin - every join was broadcast, "
                         "including orders (it fit under spark.sql.autoBroadcastJoinThreshold), "
                         "so there was no shuffle anywhere.")
            else:
                strat = (f"ACTUAL Spark plan: {sj['sort_merge_joins']} SortMergeJoin node(s) - "
                         "order_items |> orders shuffled; stores and products broadcast.")
            strat += (f"  (final physical plan: BroadcastHashJoin {sj['broadcast_hash_joins']}, "
                      f"SortMergeJoin {sj['sort_merge_joins']}"
                      + ("" if sj["broadcast_hash_joins"] + sj["sort_merge_joins"] == 3 else
                         " - expected 3 joins in total; an old parallel_compute.py double-counted"
                         " the plan, re-run the fixed version")
                      + ")")
        else:
            strat = "Spark join strategy: not measured yet - run parallel_compute.py."
        flow_text = ("order_items |> orders    on order_id    - not hinted; Spark decides\n"
                     "order_items |> stores    on store_id    - broadcast hint\n"
                     "order_items |> products  on product_id  - broadcast hint\n\n" + strat)
        tk.Label(flow, text=flow_text, bg="#0f1a2e", fg="#dbe6f7", font=("Consolas", 10),
                 justify="left", anchor="w", wraplength=1060).pack(padx=16, pady=14, anchor="w")

        if not s:
            return not_run(root, "partition_strategy.py")
        j = s["join"]
        outer, inner = card(root)
        outer.pack(fill="x", pady=(0, 20))
        tk.Label(inner, text="Row reconciliation (pandas)", font=FONT_BOLD, fg=NAVY2,
                 bg="white").pack(anchor="w", padx=14, pady=(12, 6))
        for label, value, color in [
                ("Rows before join", f"{j['rows_before']:,}", INK),
                ("Rows after join", f"{j['rows_after']:,}", INK),
                ("Difference", f"{j['delta']:,}", GREEN if j["delta"] == 0 else RED),
                ("Columns after join (incl. derived amount)", str(j["columns_after"]), INK),
                ("Join time (pandas)", f"{j['join_seconds']} s", INK)]:
            row = tk.Frame(inner, bg="white")
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text=label, bg="white", fg=INK, font=FONT).pack(side="left")
            tk.Label(row, text=value, bg="white", fg=color, font=FONT_BOLD).pack(side="right")
        tk.Label(inner, text="amount = qty x unit_price (order_items.price). Renamed to avoid "
                             "collisions: order_items.price -> unit_price, products.price -> "
                             "catalog_price, stores.city -> store_city.",
                 bg="white", fg=GREY, font=("Segoe UI", 9), wraplength=1050, justify="left"
                 ).pack(anchor="w", padx=14, pady=(6, 14))

        cands = sorted(s["all_candidates"], key=lambda c: (not c["viable"], -c["skew_ratio"]))
        chosen = s["chosen_key"]
        viable = sum(1 for c in cands if c["viable"])
        section_title(root, f"Partition key candidates - {len(cands)} columns scored, "
                            f"{viable} viable (Part 5)").pack(anchor="w", pady=(0, 8))
        rows = []
        for c in cands:
            if c["column"] == chosen:
                verdict, tag = "CHOSEN", "chosen"
            elif c["viable"]:
                verdict, tag = "viable - not chosen", "viable"
            else:
                verdict, tag = "rejected - " + c["rejected_because"], "rejected"
            rows.append((c["column"], c["source_file"], f"{c['distinct']:,}", f"{c['min']:,}",
                         f"{c['median']:,}", f"{c['max']:,}", f"{c['skew_ratio']:.2f}",
                         verdict, tag))
        make_table(root, ("Column", "Source", "Distinct", "Min", "Median", "Max", "Skew",
                          "Verdict (from partition_strategy.py)"),
                   (110, 120, 80, 80, 80, 80, 60, 520), rows, height=len(rows), tagged=True
                   ).pack(fill="x", pady=(0, 10))
        higher = [c["column"] for c in cands if c["viable"] and c["column"] != chosen
                  and c["skew_ratio"] > next(x["skew_ratio"] for x in cands
                                             if x["column"] == chosen)]
        note(root, f"The script rejects identifiers, the measure, the timestamp, near-unique "
                   f"columns and semantically weak keys, then {chosen} is chosen by hand from the "
                   f"viable set (config.PARTITION_KEY)."
                   + (f" Viable columns with MORE skew than {chosen}: {', '.join(higher)} - say "
                      f"why you passed them over in the write-up." if higher else "")
             ).pack(anchor="w")

    # ---------------- BASELINE VS PARALLEL ----------------
    def build_baseline(self, root):
        r = self.res
        base, par = r.bench_rows()
        if par:
            best = r.best_parallel()
            slower = best["slowdown"] > 1
            banner(root, f"benchmark.py: pandas baseline median {base:.4f} s; best Spark setting "
                         f"{best['partitions']} partitions at {best['median']:.4f} s - "
                         + (f"{best['slowdown']:.1f}x SLOWER. At this volume the data fits in "
                            f"memory, so JVM start-up, task scheduling, serialisation and the "
                            f"Python-JVM boundary dominate. A valid finding, not a bug."
                            if slower else f"{1 / best['slowdown']:.2f}x faster."),
                   "amber" if slower else "green").pack(fill="x", pady=(0, 14))
            section_title(root, "Parallel conditions vs baseline (results/session1_benchmark.csv)"
                          ).pack(anchor="w", pady=(0, 8))
            rows = [("Sequential baseline", "1 / non-parallel", f"{base:.4f}",
                     r.bench[0]["groups"], "1.00", "pandas, in-process")]
            rows += [(f"Parallel ({p['partitions']} partitions)", p["partitions"],
                      f"{p['median']:.4f}", p["groups"], f"{p['speedup']:.4f}",
                      p["observation"]) for p in par]
            make_table(root, ("Run", "Partitions", "Median (s)", "Groups",
                              "Speedup vs baseline", "Observation"),
                       (180, 120, 100, 70, 150, 320), rows).pack(fill="x", pady=(0, 6))
            note(root, "Speedup below 1.00 means slower than pandas. Note the baseline here is "
                       "the median benchmark.py measured in the same run as the Spark "
                       "conditions, so the ratio compares like with like.").pack(anchor="w", pady=(0, 20))
        else:
            not_run(root, "benchmark.py")

        rows = r.baseline_rows()
        if not rows:
            return not_run(root, "sequential_baseline.py")
        top = sorted(rows, key=lambda x: -x["revenue_total"])[:10]
        section_title(root, "Top 10 categories by revenue (results/baseline_result.csv)"
                      ).pack(anchor="w", pady=(0, 8))
        make_table(root, ("category_id", "line_count", "revenue_total", "revenue_mean"),
                   (110, 110, 170, 140),
                   [(x["category_id"], f"{x['line_count']:,}", f"{x['revenue_total']:,.2f}",
                     f"{x['revenue_mean']:,.2f}") for x in top]).pack(fill="x", pady=(0, 12))
        total = sum(x["revenue_total"] for x in rows)
        lines = sum(x["line_count"] for x in rows)
        tk.Label(root, text=f"Total revenue across all {len(rows)} categories: {total:,.2f}  "
                            f"·  {lines:,} line items", bg=BG, fg=NAVY2, font=FONT_BOLD
                 ).pack(anchor="w")

    # ---------------- CORRECTNESS & OUTPUT ----------------
    def build_correctness(self, root):
        v = self.res.validation
        if not v:
            not_run(root, "parallel_compute.py")
        else:
            val, agg = v["validation"], v["aggregation"]
            ok = val["passed"]
            banner(root, f"{'PASSED' if ok else 'FAILED'}. validate() compared the Spark "
                         f"aggregation ({agg['partitions']} partitions) with "
                         f"baseline_result.csv: {val['parallel_groups']} vs "
                         f"{val['baseline_groups']} groups, max line_count difference "
                         f"{val['max_line_count_difference']}, max revenue_mean difference "
                         f"{val['max_revenue_mean_difference']:.6e} (tolerance "
                         f"{val['tolerance']:.0e})."
                         + (" A nonzero mean residual is floating-point summation order - "
                            "Spark sums partitions independently then combines."
                            if ok and val["max_revenue_mean_difference"] > 0 else ""),
                   "green" if ok else "red").pack(fill="x", pady=(0, 16))
            outer, inner = card(root)
            outer.pack(fill="x", pady=(0, 14))
            tk.Label(inner, text="Validation result (results/validation_report.json)",
                     font=FONT_BOLD, fg=NAVY2, bg="white").pack(anchor="w", padx=16, pady=(14, 8))
            make_table(inner, ("Metric", "Value"), (300, 220), [
                ("parallel groups", val["parallel_groups"]),
                ("baseline groups", val["baseline_groups"]),
                ("max line_count difference", val["max_line_count_difference"]),
                ("max revenue_total difference", f"{val['max_revenue_total_difference']:.6e}"),
                ("max revenue_mean difference", f"{val['max_revenue_mean_difference']:.6e}"),
                ("tolerance", f"{val['tolerance']:.0e}"),
                ("aggregation time", f"{agg['seconds']} s at {agg['partitions']} partitions"),
                ("result", "PASSED" if ok else "FAILED"),
            ]).pack(anchor="w", padx=16, pady=(0, 16))

        outer, inner = card(root)
        outer.pack(fill="x", pady=(0, 14))
        tk.Label(inner, text="What validate() checks, in order", font=FONT_BOLD, fg=NAVY2,
                 bg="white").pack(anchor="w", padx=16, pady=(14, 6))
        for c in ("1. Group count - parallel and baseline must produce the same groups.",
                  "2. line_count difference - must be exactly 0. Anything else means the join "
                  "duplicated or dropped rows, however plausible the averages look.",
                  "3. revenue_mean difference - must be under the tolerance; summation order "
                  "alone can differ in the last digits."):
            tk.Label(inner, text=c, bg="white", fg=INK, font=FONT, wraplength=1040,
                     justify="left", anchor="w").pack(anchor="w", padx=16, pady=(0, 8))
        out = (self.res.strategy or {}).get("output_schema")
        if out:
            tk.Label(inner, text="Output schema (partition_strategy.json)", font=FONT_BOLD,
                     fg=NAVY2, bg="white").pack(anchor="w", padx=16, pady=(6, 6))
            make_table(inner, ("Column", "Type"), (200, 120), list(out.items())
                       ).pack(anchor="w", padx=16, pady=(0, 16))

    # ---------------- PARTITION BALANCE ----------------
    def build_balance(self, root):
        r = self.res
        phys, keys = r.partition_levels()
        if not keys and r.strategy:          # key level is pandas-only; show it anyway
            p = r.strategy["prediction"]
            keys_note = (f"Key level (partition_strategy.json): {p['distinct']} values, "
                         f"min {p['min']:,} / median {p['median']:,} / max {p['max']:,} -> "
                         f"{p['skew_ratio']} : 1.")
        else:
            keys_note = None
        if not phys:
            not_run(root, "partition_analysis.py")
            if keys_note:
                note(root, keys_note).pack(anchor="w")
            return

        total = sum(phys[min(phys)])
        rows = []
        for n in sorted(phys):
            s = phys[n]
            rows.append((n, f"{total / n:,.1f}", f"{min(s):,}", f"{max(s):,}",
                         f"{max(s) / min(s):.2f}" if min(s) else "inf",
                         f"{max(s) / (total / n):.2f}x"))
        ns = sorted(phys)
        first, last = phys[ns[0]], phys[ns[-1]]
        r0 = max(first) / min(first) if min(first) else float("inf")
        r1 = max(last) / min(last) if min(last) else float("inf")
        worsens = r1 > r0
        banner(root, f"Measured by partition_analysis.py with repartition(n, key) and "
                     f"rdd.glom().map(len). Physical-partition skew "
                     f"{'WORSENS' if worsens else 'does not worsen'} from {r0:.2f}:1 at "
                     f"{ns[0]} partitions to {r1:.2f}:1 at {ns[-1]}"
                     + (", even though key-level skew is fixed by the data." if worsens else "."),
               "amber" if worsens else "green").pack(fill="x", pady=(0, 16))
        section_title(root, "Physical partition-level skew (results/partition_sizes.csv)"
                      ).pack(anchor="w", pady=(0, 8))
        make_table(root, ("n partitions", "even share", "min", "max", "skew ratio",
                          "worst vs even"), (110, 110, 110, 110, 100, 120), rows
                   ).pack(fill="x", pady=(0, 10))
        if worsens:
            note(root, f"Cause: hash collision. With few partitions each holds many categories "
                       f"and imbalances average out; with more partitions an unlucky pairing of "
                       f"heavy categories is no longer diluted. The slowest task sets elapsed "
                       f"time, so the partition holding {max(last):,} records at {ns[-1]} "
                       f"partitions ({max(last) / (total / ns[-1]):.2f}x the even share) bounds "
                       f"the job. Mitigation: range partitioning on cumulative volume or balanced "
                       f"buckets before repartitioning.").pack(anchor="w", pady=(0, 20))

        if keys:
            ordered = sorted(keys.items(), key=lambda kv: -kv[1])
            vals = [v for _, v in ordered]
            section_title(root, f"Key-level skew - {len(keys)} keys (results/partition_sizes.csv)"
                          ).pack(anchor="w", pady=(0, 8))
            grid = tk.Frame(root, bg=BG)
            grid.pack(fill="x", pady=(0, 14))
            grid.grid_columnconfigure(0, weight=1, uniform="g")
            grid.grid_columnconfigure(1, weight=1, uniform="g")
            for col, (title, data, colr) in enumerate(
                    (("Heaviest 5", ordered[:5], BLUE), ("Lightest 5", ordered[-5:], "#9db8e0"))):
                outer, inner = card(grid)
                outer.grid(row=0, column=col, sticky="nsew", padx=(0, 8) if col == 0 else (8, 0))
                tk.Label(inner, text=title, font=FONT_BOLD, fg=NAVY2, bg="white"
                         ).pack(anchor="w", padx=14, pady=(12, 8))
                self._bars(inner, data, vals[0], colr)
            note(root, f"min {min(vals):,} / median {int(statistics.median(vals)):,} / max "
                       f"{max(vals):,} -> {max(vals) / min(vals):.2f} : 1. Fixed by the data; it "
                       f"does not change with partition count.").pack(anchor="w", pady=(0, 18))

        if r.strategy:
            alts = r.strategy.get("rejected_alternatives", [])
            if alts:
                section_title(root, "Rejected alternatives (partition_strategy.json)"
                              ).pack(anchor="w", pady=(0, 8))
                make_table(root, ("Key", "Distinct", "Skew ratio", "Why not chosen"),
                           (110, 90, 100, 760),
                           [(a["column"], f"{a['distinct']:,}", f"{a['skew_ratio']:.2f} : 1",
                             a["rejected_because"] or "numerically viable") for a in alts]
                           ).pack(fill="x")

    def _bars(self, parent, data, max_val, color):
        for label, value in data:
            row = tk.Frame(parent, bg="white")
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text=f"cat {label}", bg="white", fg=INK, font=("Segoe UI", 9),
                     width=8, anchor="w").pack(side="left")
            track = tk.Frame(row, bg="#eef1f6", height=14)
            track.pack(side="left", fill="x", expand=True, padx=6)
            tk.Frame(track, bg=color, height=14).place(relx=0, rely=0,
                                                       relwidth=value / max_val, relheight=1)
            tk.Label(row, text=f"{value:,}", bg="white", fg=INK, font=("Segoe UI", 9),
                     width=8, anchor="e").pack(side="left")
        tk.Frame(parent, bg="white", height=10).pack()


# ===========================================================================
def check() -> int:
    """Print what the console would show, without a GUI."""
    r = Results()
    print(f"results folder: {RESULTS}")
    for key, label, script, engine, _ in STAGES:
        print(f"  {label:<24} {'done   ' if r.has(key) else 'NOT RUN'}  {r.headline(key)}")
    return 0


def main() -> int:
    explicit = None
    if "--dir" in sys.argv:
        i = sys.argv.index("--dir")
        explicit = sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    found = find_pipeline_dir(explicit)
    set_pipeline_dir(found)
    if "--check" in sys.argv:
        if found is None:
            print(f"pipeline folder not found (looked around {CONSOLE_DIR}); pass --dir PATH")
            return 1
        return check()
    global tk, ttk, scrolledtext
    import tkinter as _tk
    from tkinter import scrolledtext as _st
    from tkinter import ttk as _ttk
    tk, ttk, scrolledtext = _tk, _ttk, _st
    app = ConsoleApp()
    app.root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
