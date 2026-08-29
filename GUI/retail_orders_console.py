"""
console.py - Retail-Orders Session 1 Parallel Compute Console (desktop GUI)

A Tkinter re-implementation of the HTML dashboard: same tabs, same real
pipeline data, no browser required.

Requires only the Python standard library (tkinter ships with the default
CPython installer on Windows and macOS). On Linux, if you see
"ModuleNotFoundError: No module named 'tkinter'", install it with:
    sudo apt install python3-tk        (Debian/Ubuntu)
    sudo dnf install python3-tkinter   (Fedora)

Run:
    python console.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext

# ---------------------------------------------------------------------------
# Palette (matches the HTML console this was built alongside)
# ---------------------------------------------------------------------------
NAVY = "#16233d"
NAVY2 = "#1f3358"
BLUE = "#2e5aa8"
BLUE_LIGHT = "#e8eef8"
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
FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 9)


# ---------------------------------------------------------------------------
# Reusable scrollable tab container
# ---------------------------------------------------------------------------
class ScrollableTab(tk.Frame):
    """A tab page that scrolls vertically when content overflows."""

    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.body = tk.Frame(canvas, bg=BG, padx=22, pady=18)

        self.body.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        window_id = canvas.create_window((0, 0), window=self.body, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(window_id, width=e.width),
        )
        canvas.configure(yscrollcommand=vsb.set)

        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def _wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _wheel)  # Windows / macOS
        canvas.bind_all("<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all("<Button-5>", lambda e: canvas.yview_scroll(1, "units"))


# ---------------------------------------------------------------------------
# Small widget builders
# ---------------------------------------------------------------------------
def stat_card(parent, value, label, value_color=NAVY2):
    frame = tk.Frame(parent, bg="white", highlightbackground=GREY_LINE,
                      highlightthickness=1, bd=0)
    tk.Label(frame, text=value, font=FONT_STAT, fg=value_color, bg="white"
              ).pack(pady=(16, 4))
    tk.Label(frame, text=label, font=("Segoe UI", 9), fg=GREY, bg="white",
              wraplength=170, justify="center").pack(pady=(0, 14), padx=8)
    return frame


def banner(parent, text, kind="amber"):
    bgc = AMBER_BG if kind == "amber" else GREEN_BG
    bd = AMBER_BORDER if kind == "amber" else "#9bcf9e"
    fgc = "#5c2f00" if kind == "amber" else "#173d19"
    outer = tk.Frame(parent, bg=bd)
    inner = tk.Frame(outer, bg=bgc)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Label(inner, text=text, bg=bgc, fg=fgc, font=("Segoe UI", 9),
              justify="left", wraplength=1020, anchor="w"
              ).pack(padx=16, pady=12, anchor="w", fill="x")
    return outer


def section_title(parent, text):
    return tk.Label(parent, text=text, font=FONT_SECTION, fg=NAVY2, bg=BG,
                     anchor="w")


def card(parent):
    outer = tk.Frame(parent, bg=GREY_LINE)
    inner = tk.Frame(outer, bg="white")
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return outer, inner


def make_table(parent, columns, col_widths, rows, height=None, tag_colors=None):
    """
    rows: list of tuples. If tag_colors is given, the LAST element of each
    row tuple is treated as a tag name (not displayed) used to color that row.
    """
    container = tk.Frame(parent, bg=GREY_LINE)
    inner = tk.Frame(container, bg="white")
    inner.pack(fill="both", expand=True, padx=1, pady=1)

    style_name = f"Table{id(columns)}.Treeview"
    style = ttk.Style()
    style.configure(style_name, rowheight=24, font=FONT, fieldbackground="white")
    style.configure(f"{style_name}.Heading", font=FONT_BOLD, background=NAVY,
                     foreground="white")
    style.map(f"{style_name}.Heading", background=[("active", NAVY)])

    n_rows = len(rows) if height is None else height
    tree = ttk.Treeview(inner, columns=columns, show="headings",
                         height=min(max(n_rows, 1), 16), style=style_name)
    for c, w in zip(columns, col_widths):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="w")

    vsb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    inner.grid_columnconfigure(0, weight=1)
    inner.grid_rowconfigure(0, weight=1)

    for row in rows:
        if tag_colors:
            values, tag = row[:-1], row[-1]
            tree.insert("", "end", values=values, tags=(tag,))
        else:
            tree.insert("", "end", values=row)

    if tag_colors:
        for tag, (bgc, fgc) in tag_colors.items():
            tree.tag_configure(tag, background=bgc, foreground=fgc)

    return container


PILL_TAGS = {
    "done": (GREEN_BG, GREEN),
    "pending": (AMBER_BG, AMBER),
    "pass": (GREEN_BG, GREEN),
}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
class ConsoleApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Retail-Orders — Session 1 Parallel Compute Console")
        self.geometry("1220x820")
        self.configure(bg=BG)
        self._build_style()
        self._build_header()
        self._build_tabs()

    # ---------------- chrome ----------------
    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", font=FONT_BOLD, padding=(16, 10),
                         background="white", foreground=GREY)
        style.map("TNotebook.Tab",
                  background=[("selected", "white")],
                  foreground=[("selected", NAVY2)])

    def _build_header(self):
        titlebar = tk.Frame(self, bg=NAVY, height=26)
        titlebar.pack(fill="x")
        tk.Label(titlebar, text="●  Retail-Orders — Session 1 Parallel Compute Console",
                 bg=NAVY, fg="#d9dee6", font=("Segoe UI", 9)
                 ).pack(side="left", padx=14, pady=4)

        header = tk.Frame(self, bg=NAVY2)
        header.pack(fill="x")
        tk.Label(header, text="Retail-Orders — Session 1 Parallel Compute Console",
                 bg=NAVY2, fg="white", font=FONT_TITLE
                 ).pack(anchor="w", padx=26, pady=(16, 2))
        sub = tk.Frame(header, bg=NAVY2)
        sub.pack(anchor="w", padx=26, pady=(0, 14))
        parts = [
            ("MIT 261 Parallel and Distributed Systems", "#c7d2e6", FONT_SUB),
            ("   ·   partition key ", "#c7d2e6", FONT_SUB),
            ("category_id", "white", ("Segoe UI", 10, "bold")),
            ("   ·   bounded parallelism ", "#c7d2e6", FONT_SUB),
            ("4", "white", ("Segoe UI", 10, "bold")),
            ("   ·   settings ", "#c7d2e6", FONT_SUB),
            ("(2, 4, 8)", "white", ("Segoe UI", 10, "bold")),
        ]
        for text, fg, font in parts:
            tk.Label(sub, text=text, bg=NAVY2, fg=fg, font=font).pack(side="left")

    def _build_tabs(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        tabs = [
            ("Pipeline", self.build_pipeline),
            ("Files & eligibility", self.build_files),
            ("Join & partition key", self.build_join),
            ("Baseline vs parallel", self.build_baseline),
            ("Correctness & output", self.build_correctness),
            ("Partition balance", self.build_balance),
            ("Console", self.build_console),
        ]
        for label, builder in tabs:
            page = ScrollableTab(nb)
            nb.add(page, text=label)
            builder(page.body)

        footer = tk.Label(
            self,
            text="Retail-Orders Session 1 · generated from real pipeline output · "
                 "Spark-dependent figures marked \"not run\" are placeholders for the "
                 "expected workflow, not fabricated numbers.",
            bg=BG, fg=GREY, font=("Segoe UI", 9))
        footer.pack(fill="x", pady=(0, 8))

    # ---------------- PIPELINE ----------------
    def build_pipeline(self, root):
        stats = tk.Frame(root, bg=BG)
        stats.pack(fill="x", pady=(0, 16))
        for i in range(4):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")
        stat_card(stats, "600,000", "rows through the join").grid(
            row=0, column=0, sticky="nsew", padx=(0, 8))
        stat_card(stats, "30", "groups in the result (category_id)").grid(
            row=0, column=1, sticky="nsew", padx=8)
        stat_card(stats, "0.0100s", "pandas baseline median (5 runs)").grid(
            row=0, column=2, sticky="nsew", padx=8)
        stat_card(stats, "PENDING", "parallel vs baseline — needs PySpark",
                   value_color=AMBER).grid(row=0, column=3, sticky="nsew", padx=(8, 0))

        banner(root, "Stages 5-7 need Spark. This machine has no internet access to "
                      "install PySpark, so parallel_compute.py, benchmark.py, and "
                      "partition_analysis.py haven't executed yet - they're written, "
                      "reviewed, and ready. Stages 1-4 and the diagram renderer ran "
                      "end-to-end against your real 12 CSVs; every number on this "
                      "console except the Spark-only tabs is genuine output, not a "
                      "placeholder. See the Console tab for the exact JDK fix needed "
                      "on your machine.").pack(fill="x", pady=(0, 18))

        section_title(root, "Run a stage").pack(anchor="w", pady=(0, 8))
        cols = ("Stage", "Engine", "Status", "Headline result")
        widths = (170, 80, 90, 620)
        rows = [
            ("1. Profile files", "pandas", "completed",
             "12 files profiled · 11/11 foreign keys resolve · all 4 eligibility conditions met", "done"),
            ("2. Load and join", "pandas", "completed",
             "order_items > orders > stores > products - 600,000 -> 600,000 rows, 14 columns", "done"),
            ("3. Partition strategy", "pandas", "completed",
             "category_id chosen: 30 groups, 1.22:1 skew - derived from 15 scored candidates", "done"),
            ("4. Sequential baseline", "pandas", "completed",
             "median 0.0100s over 5 runs · total revenue 3,827,746,136.00 across 30 categories", "done"),
            ("5. Parallel compute", "Spark", "not run",
             "PySpark unavailable in this sandbox - needs JDK 17/21 + pip install pyspark pyarrow", "pending"),
            ("6. Benchmark", "Spark", "not run",
             "Compares baseline against 2 / 4 / 8 partitions - depends on stage 5", "pending"),
            ("7. Partition balance", "Spark", "not run",
             "Key-level skew is measured; physical Spark-partition skew needs stage 5", "pending"),
            ("Render diagrams", "graphviz", "completed",
             "entity-model-session1.png + architecture-session1.png rendered", "done"),
        ]
        make_table(root, cols, widths, rows, tag_colors=PILL_TAGS).pack(
            fill="x", pady=(0, 20))

        section_title(root, "Artefacts in results/").pack(anchor="w", pady=(0, 8))
        cols2 = ("Artefact", "Written by", "Status", "Size")
        widths2 = (240, 340, 90, 90)
        rows2 = [
            ("file_profile.json", "profile_files.py", "written", "9.2 KB", "done"),
            ("working_dataset.pkl", "load_and_join.py (parquet -> pickle fallback)",
             "written", "60.6 MB", "done"),
            ("partition_strategy.json", "partition_strategy.py", "written", "6.0 KB", "done"),
            ("baseline_result.csv", "sequential_baseline.py", "written", "1.1 KB", "done"),
            ("category_revenue.parquet", "parallel_compute.py", "pending", "-", "pending"),
            ("validation_report.json", "parallel_compute.py", "pending", "-", "pending"),
            ("session1_benchmark.csv", "benchmark.py", "pending", "-", "pending"),
            ("partition_sizes.csv", "partition_analysis.py", "pending", "-", "pending"),
            ("docs/entity-model-session1.png", "render_diagrams.py", "written", "440 KB", "done"),
            ("architecture/architecture-session1.png", "render_diagrams.py", "written", "299 KB", "done"),
        ]
        make_table(root, cols2, widths2, rows2, tag_colors=PILL_TAGS).pack(fill="x")

    # ---------------- FILES & ELIGIBILITY ----------------
    def build_files(self, root):
        section_title(root, "12 input files").pack(anchor="w", pady=(0, 8))
        cols = ("File", "Role", "Rows", "Cols", "Size", "Candidate primary key(s)")
        widths = (170, 70, 90, 50, 90, 220)
        rows = [
            ("order_items.csv", "Event", "600,000", "5", "14,736 KB", "order_item_id"),
            ("orders.csv", "Event", "300,000", "5", "8,539 KB", "order_id"),
            ("payments.csv", "Event", "300,000", "3", "5,484 KB", "payment_id, order_id"),
            ("shipments.csv", "Event", "300,000", "3", "6,131 KB", "shipment_id, order_id"),
            ("returns.csv", "Event", "30,000", "3", "505 KB", "return_id"),
            ("customers.csv", "Entity", "50,000", "3", "1,161 KB", "customer_id"),
            ("employees.csv", "Entity", "1,000", "3", "12.5 KB", "employee_id"),
            ("products.csv", "Entity", "10,000", "4", "155 KB", "product_id"),
            ("stores.csv", "Entity", "100", "2", "1.0 KB", "store_id"),
            ("suppliers.csv", "Entity", "200", "2", "1.7 KB", "supplier_id"),
            ("categories.csv", "Lookup", "30", "2", "0.3 KB", "category_id, category_name"),
            ("promotions.csv", "Lookup", "50", "2", "0.3 KB", "promotion_id"),
        ]
        make_table(root, cols, widths, rows).pack(fill="x", pady=(0, 20))

        section_title(root, "Referential integrity - 11 foreign keys, 11/11 pass, 0 orphans"
                       ).pack(anchor="w", pady=(0, 8))
        cols2 = ("Foreign key", "Result")
        widths2 = (500, 90)
        fk_labels = [
            "order_items.order_id -> orders.order_id",
            "order_items.product_id -> products.product_id",
            "orders.customer_id -> customers.customer_id",
            "orders.store_id -> stores.store_id",
            "orders.promotion_id -> promotions.promotion_id",
            "products.category_id -> categories.category_id",
            "products.supplier_id -> suppliers.supplier_id",
            "employees.store_id -> stores.store_id",
            "payments.order_id -> orders.order_id",
            "shipments.order_id -> orders.order_id",
            "returns.order_item_id -> order_items.order_item_id",
        ]
        rows2 = [(label, "PASS", "pass") for label in fk_labels]
        make_table(root, cols2, widths2, rows2, tag_colors=PILL_TAGS).pack(
            fill="x", pady=(0, 20))

        section_title(root, "Dataset eligibility (Part 2) - all 4 conditions met"
                       ).pack(anchor="w", pady=(0, 8))
        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1, uniform="c")
        grid.grid_columnconfigure(1, weight=1, uniform="c")

        conditions = [
            ("Condition 1 - at least 3 qualifying files",
             "10 Event/Entity files qualify (Lookup files categories and "
             "promotions excluded)."),
            ("Condition 2 - genuine one-to-many association",
             "orders 1..* order_items (min 1, median 2, max 11 items/order) and "
             "customers 1..* orders (min 1, median 6, max 19 orders/customer). "
             "Note: payments.order_id and shipments.order_id are both unique -> "
             "1:1 extensions of Order, not second one-to-many associations."),
            ("Condition 3 - usable timestamp",
             "orders.order_date, 2020-01-01 -> 2024-01-01 (1,461-day span)."),
            ("Condition 4 - transactional volume",
             "1,530,000 combined Event rows (order_items + orders + payments + "
             "shipments + returns) >= 50,000 minimum."),
        ]
        for i, (title, body) in enumerate(conditions):
            outer, inner = card(grid)
            outer.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            tk.Label(inner, text="\u2713 " + title, font=FONT_BOLD, fg=NAVY2,
                      bg="white", anchor="w", justify="left"
                      ).pack(anchor="w", padx=14, pady=(12, 4))
            tk.Label(inner, text=body, font=("Segoe UI", 9), fg=INK, bg="white",
                      wraplength=460, justify="left", anchor="w"
                      ).pack(anchor="w", padx=14, pady=(0, 12))

    # ---------------- JOIN & PARTITION KEY ----------------
    def build_join(self, root):
        section_title(root, "Join path (Part 4)").pack(anchor="w", pady=(0, 8))
        flow = tk.Frame(root, bg="#0f1a2e")
        flow.pack(fill="x", pady=(0, 16))
        flow_text = (
            "order_items |> orders    on order_id    - NOT broadcast, 8.5 MB, expected shuffle\n"
            "order_items |> stores    on store_id    - broadcast, <1 KB\n"
            "order_items |> products  on product_id  - broadcast, 155 KB"
        )
        tk.Label(flow, text=flow_text, bg="#0f1a2e", fg="#dbe6f7", font=FONT_MONO,
                  justify="left", anchor="w").pack(padx=16, pady=14, anchor="w")

        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x", pady=(0, 20))
        grid.grid_columnconfigure(0, weight=6, uniform="g")
        grid.grid_columnconfigure(1, weight=4, uniform="g")

        outer1, inner1 = card(grid)
        outer1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(inner1, text="Row reconciliation", font=FONT_BOLD, fg=NAVY2,
                  bg="white").pack(anchor="w", padx=14, pady=(12, 6))
        kpis = [
            ("Rows before join", "600,000", INK),
            ("Rows after join", "600,000", INK),
            ("Difference", "0", GREEN),
            ("Columns after join", "14", INK),
            ("Join time (pandas)", "0.80s", INK),
        ]
        for label, value, color in kpis:
            row = tk.Frame(inner1, bg="white")
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text=label, bg="white", fg=INK, font=("Segoe UI", 10)
                      ).pack(side="left")
            tk.Label(row, text=value, bg="white", fg=color,
                      font=("Segoe UI", 9.5, "bold")).pack(side="right")
        tk.Frame(inner1, bg="white", height=8).pack()

        outer2, inner2 = card(grid)
        outer2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(inner2, text="Derived metric", font=FONT_BOLD, fg=NAVY2,
                  bg="white").pack(anchor="w", padx=14, pady=(12, 6))
        tk.Label(inner2, text="amount = qty x unit_price - line-item revenue "
                              "actually charged, not the product's catalog_price "
                              "(they can differ due to promotions).",
                  bg="white", fg=INK, font=("Segoe UI", 9), wraplength=340,
                  justify="left", anchor="w").pack(anchor="w", padx=14, pady=(0, 8))
        tk.Label(inner2, text="Column collisions handled: order_items.price -> "
                              "unit_price, products.price -> catalog_price, "
                              "stores.city -> store_city.",
                  bg="white", fg=GREY, font=("Segoe UI", 9), wraplength=340,
                  justify="left", anchor="w").pack(anchor="w", padx=14, pady=(0, 14))

        section_title(root, "Partition key candidates - measured, not asserted (Part 5)"
                       ).pack(anchor="w", pady=(0, 8))
        cols = ("Column", "Distinct", "Min", "Median", "Max", "Skew", "Verdict")
        widths = (110, 80, 90, 90, 90, 70, 340)
        rows = [
            ("customer_id", "49,751", "1", "11", "43", "43.00",
             "rejected - per-customer granularity, not a dimension", "rejected"),
            ("amount", "11,984", "9", "38", "153", "17.00",
             "rejected - the measure being aggregated", "rejected"),
            ("catalog_price", "4,268", "36", "123", "556", "15.44",
             "rejected - continuous financial value", "rejected"),
            ("order_id", "259,233", "1", "2", "11", "11.00",
             "rejected - foreign key, not a dimension", "rejected"),
            ("product_id", "10,000", "26", "60", "90", "3.46",
             "rejected - near-SKU granularity", "rejected"),
            ("supplier_id", "200", "1,915", "2,978", "4,086", "2.13",
             "viable - not chosen, a candidate for a future supplier-level session", "viable"),
            ("unit_price", "4,900", "84", "122", "160", "1.90",
             "rejected - continuous financial value", "rejected"),
            ("order_date", "1,462", "312", "409", "538", "1.72",
             "rejected - event timestamp", "rejected"),
            ("store_city", "4", "124,929", "144,394", "186,283", "1.49",
             "rejected - too coarse to fill 8 partitions", "rejected"),
            ("category_id", "30", "17,618", "20,066", "21,429", "1.22",
             "CHOSEN - real skew + genuine business dimension", "chosen"),
            ("store_id", "100", "5,644", "6,005", "6,299", "1.12",
             "viable - not chosen, less skew than category_id", "viable"),
            ("promotion_id", "50", "11,498", "11,972", "12,478", "1.09",
             "viable - not chosen, less skew than category_id", "viable"),
            ("qty", "4", "149,564", "149,972", "150,492", "1.01",
             "rejected - near-uniform, nothing to analyse", "rejected"),
            ("order_item_id", "600,000", "1", "1", "1", "1.00",
             "rejected - row identifier", "rejected"),
        ]
        tag_colors = {
            "rejected": (RED_BG, RED),
            "viable": (GREEN_BG, GREEN),
            "chosen": (GOLD_BG, GOLD_FG),
        }
        make_table(root, cols, widths, rows, tag_colors=tag_colors, height=14
                    ).pack(fill="x", pady=(0, 10))
        tk.Label(root, text="15 columns scored in the joined frame. category_id wins "
                            "on the combination of a real, measurable skew (1.22:1) "
                            "and being a genuine business dimension - supplier_id and "
                            "order_id/catalog_price show higher skew but are either "
                            "too fine-grained, an identifier, or a continuous price "
                            "rather than a grouping attribute.",
                  bg=BG, fg=GREY, font=("Segoe UI", 8.5), wraplength=1050,
                  justify="left", anchor="w").pack(anchor="w")

    # ---------------- BASELINE VS PARALLEL ----------------
    def build_baseline(self, root):
        banner(root, "Sequential baseline (pandas) - completed. 5 runs: 0.0117s, "
                      "0.0101s, 0.0100s, 0.0100s, 0.0098s -> median 0.0100s, mean "
                      "0.0103s, 30 groups.", kind="green").pack(fill="x", pady=(0, 10))
        banner(root, "Parallel conditions (Spark, 2/4/8 partitions) - not run. "
                      "benchmark.py is ready to execute the same workload under "
                      "bounded parallelism once PySpark + a compatible JDK are "
                      "installed (see Console tab). It will compare the median of "
                      "3 runs per setting against the 0.0100s baseline above."
                      ).pack(fill="x", pady=(0, 20))

        section_title(root, "Top 10 categories by revenue (pandas baseline)"
                       ).pack(anchor="w", pady=(0, 8))
        cols = ("category_id", "line_count", "revenue_total", "revenue_mean")
        widths = (100, 110, 150, 130)
        rows = [
            ("5", "21,429", "136,704,132", "6,379.40"),
            ("3", "21,177", "135,379,339", "6,392.75"),
            ("21", "21,066", "135,329,061", "6,424.05"),
            ("26", "21,129", "134,697,069", "6,374.99"),
            ("12", "21,080", "133,897,588", "6,351.88"),
            ("28", "20,957", "133,603,891", "6,375.14"),
            ("8", "20,950", "132,816,590", "6,339.69"),
            ("9", "20,909", "132,465,085", "6,335.31"),
            ("13", "20,746", "132,409,449", "6,382.41"),
            ("17", "20,763", "132,292,751", "6,371.56"),
        ]
        make_table(root, cols, widths, rows).pack(fill="x", pady=(0, 12))
        tk.Label(root, text="Total revenue across all 30 categories: 3,827,746,136.00",
                  bg=BG, fg=NAVY2, font=FONT_BOLD).pack(anchor="w")

    # ---------------- CORRECTNESS & OUTPUT ----------------
    def build_correctness(self, root):
        banner(root, "Not run yet. parallel_compute.py calls validate(), which will "
                      "compare the Spark aggregation against baseline_result.csv "
                      "above. Nothing here is fabricated - this tab shows what the "
                      "check does and what it will report once Spark runs."
                      ).pack(fill="x", pady=(0, 16))

        outer1, inner1 = card(root)
        outer1.pack(fill="x", pady=(0, 14))
        tk.Label(inner1, text="What validate() checks, in order", font=FONT_BOLD,
                  fg=NAVY2, bg="white").pack(anchor="w", padx=16, pady=(14, 6))
        checks = [
            "1. Group count match - parallel and baseline must produce the same "
            "30 groups.",
            "2. line_count difference - must be exactly 0. Any nonzero value "
            "means the join duplicated or dropped rows, independent of whether "
            "the averages look plausible.",
            "3. revenue_mean difference - must be under the tolerance 1e-6. "
            "Spark sums each partition independently then combines, so pandas "
            "and Spark can differ in the last few digits from floating-point "
            "summation order alone - both are correct.",
        ]
        for c in checks:
            tk.Label(inner1, text=c, bg="white", fg=INK, font=("Segoe UI", 10),
                      wraplength=1000, justify="left", anchor="w"
                      ).pack(anchor="w", padx=16, pady=(0, 8))
        tk.Frame(inner1, bg="white", height=6).pack()

        outer2, inner2 = card(root)
        outer2.pack(fill="x")
        tk.Label(inner2, text="Expected output schema", font=FONT_BOLD, fg=NAVY2,
                  bg="white").pack(anchor="w", padx=16, pady=(14, 8))
        cols = ("Column", "Type")
        widths = (200, 120)
        rows = [
            ("category_id", "int64"),
            ("line_count", "int64"),
            ("revenue_total", "double"),
            ("revenue_mean", "double"),
        ]
        tbl = make_table(inner2, cols, widths, rows)
        tbl.pack(anchor="w", padx=16, pady=(0, 16))

    # ---------------- PARTITION BALANCE ----------------
    def build_balance(self, root):
        section_title(root, "Key-level skew - category_id (measured, pandas)"
                       ).pack(anchor="w", pady=(0, 8))

        grid = tk.Frame(root, bg=BG)
        grid.pack(fill="x", pady=(0, 14))
        grid.grid_columnconfigure(0, weight=1, uniform="g")
        grid.grid_columnconfigure(1, weight=1, uniform="g")

        heavy = [("cat 5", 21429), ("cat 3", 21177), ("cat 26", 21129),
                 ("cat 12", 21080), ("cat 21", 21066)]
        light = [("cat 24", 18930), ("cat 1", 18718), ("cat 14", 18689),
                 ("cat 23", 18243), ("cat 2", 17618)]

        outer1, inner1 = card(grid)
        outer1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        tk.Label(inner1, text="Heaviest 5 categories", font=FONT_BOLD, fg=NAVY2,
                  bg="white").pack(anchor="w", padx=14, pady=(12, 8))
        self._draw_bars(inner1, heavy, max(v for _, v in heavy), BLUE)
        tk.Frame(inner1, bg="white", height=10).pack()

        outer2, inner2 = card(grid)
        outer2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(inner2, text="Lightest 5 categories", font=FONT_BOLD, fg=NAVY2,
                  bg="white").pack(anchor="w", padx=14, pady=(12, 8))
        self._draw_bars(inner2, light, max(v for _, v in heavy), "#9db8e0")
        tk.Frame(inner2, bg="white", height=10).pack()

        tk.Label(root, text="30 distinct categories, min 17,618 / median 20,066 / "
                            "max 21,429 records -> 1.22 : 1 skew ratio. This is "
                            "fixed by the data and does not change with partition "
                            "count.", bg=BG, fg=INK, font=("Segoe UI", 9.5),
                  wraplength=1050, justify="left", anchor="w"
                  ).pack(anchor="w", pady=(0, 18))

        section_title(root, "Rejected alternatives, for comparison"
                       ).pack(anchor="w", pady=(0, 8))
        cols = ("Key", "Distinct", "Skew ratio", "Why not chosen")
        widths = (110, 90, 100, 620)
        rows = [
            ("customer_id", "49,751", "43.00 : 1",
             "Skew is real, but 49,751 groups is per-customer granularity, not "
             "a dimensional rollup."),
            ("store_city", "4", "1.49 : 1",
             "Only 4 distinct values - can't fill 8 worker partitions without "
             "forcing shares."),
            ("supplier_id", "200", "2.13 : 1",
             "Numerically viable and more skewed than category_id - a good "
             "candidate for a future session focused on supply chain rather "
             "than product category."),
        ]
        make_table(root, cols, widths, rows).pack(fill="x", pady=(0, 16))

        banner(root, "Physical Spark-partition skew - not run. "
                      "partition_analysis.py will repartition into 2/4/8 physical "
                      "partitions with repartition(n, 'category_id') and measure "
                      "actual record counts per partition via "
                      "rdd.glom().map(len). That number is expected to diverge "
                      "from the 1.22:1 key-level ratio above - a hash partitioner "
                      "maps many keys onto few partitions, so an unlucky pairing "
                      "of two heavy categories in one partition isn't diluted at "
                      "higher partition counts. This needs Spark to observe."
                      ).pack(fill="x")

    def _draw_bars(self, parent, data, max_val, color):
        for label, value in data:
            row = tk.Frame(parent, bg="white")
            row.pack(fill="x", padx=14, pady=3)
            tk.Label(row, text=label, bg="white", fg=INK, font=("Segoe UI", 9),
                      width=8, anchor="w").pack(side="left")
            track = tk.Frame(row, bg="#eef1f6", height=14)
            track.pack(side="left", fill="x", expand=True, padx=6)
            frac = value / max_val
            bar = tk.Frame(track, bg=color, height=14)
            bar.place(relx=0, rely=0, relwidth=frac, relheight=1)
            tk.Label(row, text=f"{value:,}", bg="white", fg=INK,
                      font=("Segoe UI", 9), width=8, anchor="e").pack(side="left")

    # ---------------- CONSOLE ----------------
    def build_console(self, root):
        banner(root, "Why Spark hasn't run: this build machine has no internet "
                      "access, so pip install pyspark fails outright here. On your "
                      "own machine, the actual blocker reported was a JVM crash "
                      "inside cfg.build_spark() - ClassNotFoundException: "
                      "jdk.internal.ref.Cleaner - which means the installed JDK is "
                      "newer than your PySpark build supports. Fix: install JDK 17 "
                      "(safest, works with PySpark 3.5-4.1) or JDK 21 (PySpark "
                      "4.0+), point JAVA_HOME at it, and confirm with java "
                      "-version before re-running benchmark.py."
                      ).pack(fill="x", pady=(0, 14))

        text = scrolledtext.ScrolledText(root, height=28, bg="#0f1a2e",
                                          fg="#c9d6ea", font=FONT_MONO_SM,
                                          insertbackground="white", bd=0,
                                          padx=16, pady=14, wrap="word")
        text.pack(fill="both", expand=True)

        text.tag_configure("h", foreground="#7fd8ff")
        text.tag_configure("g", foreground="#8fdc8f")
        text.tag_configure("a", foreground="#ffcf8f")
        text.tag_configure("dim", foreground="#7c8aa3")

        log = [
            ("$ python profile_files.py\n", None),
            ("=" * 72 + "\n", "dim"),
            ("SESSION 1 - FILE PROFILING\n", "h"),
            ("=" * 72 + "\n", "dim"),
            ("FILE: order_items.csv       role=Event   rows=600,000 cols=5  size=14736.1 KB\n", None),
            ("FILE: orders.csv            role=Event   rows=300,000 cols=5  size= 8539.3 KB\n", None),
            ("FILE: payments.csv          role=Event   rows=300,000 cols=3  size= 5483.7 KB\n", None),
            ("FILE: shipments.csv         role=Event   rows=300,000 cols=3  size= 6130.8 KB\n", None),
            ("FILE: returns.csv           role=Event   rows= 30,000 cols=3  size=  505.3 KB\n", None),
            ("FILE: customers.csv         role=Entity  rows= 50,000 cols=3  size= 1160.9 KB\n", None),
            ("FILE: employees.csv         role=Entity  rows=  1,000 cols=3  size=   12.5 KB\n", None),
            ("FILE: products.csv          role=Entity  rows= 10,000 cols=4  size=  154.9 KB\n", None),
            ("FILE: stores.csv            role=Entity  rows=    100 cols=2  size=    1.0 KB\n", None),
            ("FILE: suppliers.csv         role=Entity  rows=    200 cols=2  size=    1.7 KB\n", None),
            ("FILE: categories.csv        role=Lookup  rows=     30 cols=2  size=    0.3 KB\n", None),
            ("FILE: promotions.csv        role=Lookup  rows=     50 cols=2  size=    0.3 KB\n", None),
            ("\n" + "=" * 72 + "\n", "dim"),
            ("REFERENTIAL INTEGRITY (11 foreign keys)\n", "h"),
            ("=" * 72 + "\n", "dim"),
        ]
        for label in [
            "order_items.order_id -> orders.order_id",
            "order_items.product_id -> products.product_id",
            "orders.customer_id -> customers.customer_id",
            "orders.store_id -> stores.store_id",
            "orders.promotion_id -> promotions.promotion_id",
            "products.category_id -> categories.category_id",
            "products.supplier_id -> suppliers.supplier_id",
            "employees.store_id -> stores.store_id",
            "payments.order_id -> orders.order_id",
            "shipments.order_id -> orders.order_id",
            "returns.order_item_id -> order_items.order_item_id",
        ]:
            log.append(("PASS", "g"))
            log.append((f"  {label}\n", None))
        log += [
            ("  orphan records: all zero\n", None),
            ("\n" + "=" * 72 + "\n", "dim"),
            ("DATASET ELIGIBILITY (Part 2)\n", "h"),
            ("=" * 72 + "\n", "dim"),
        ]
        for cond in ["condition_1_three_related_files", "condition_2_one_to_many",
                     "condition_3_timestamp", "condition_4_volume"]:
            log.append(("MET ", "g"))
            log.append((f"  {cond}\n", None))
        log += [
            ("\nAll eligibility conditions met. Proceed to load_and_join.py\n\n", None),
            ("$ python load_and_join.py\n", None),
            ("=" * 72 + "\n", "dim"),
            ("JOIN PATH RECONCILIATION\n", "h"),
            ("=" * 72 + "\n", "dim"),
            ("  join path        : order_items |> orders |> stores |> products\n", None),
            ("  rows before join : 600,000\n", None),
            ("  rows after join  : 600,000\n", None),
            ("  difference       : 0\n", None),
            ("  columns after    : 14\n", None),
            ("  join time        : 0.80 s\n", None),
            ("  (no pyarrow/fastparquet available - wrote working_dataset.pkl instead)\n", "a"),
            ("Wrote results/working_dataset.parquet (600,000 rows)\n\n", None),
            ("$ python sequential_baseline.py\n", None),
            ("=" * 72 + "\n", "dim"),
            ("SEQUENTIAL BASELINE\n", "h"),
            ("=" * 72 + "\n", "dim"),
            ("  run 1: 0.0117 s\n  run 2: 0.0101 s\n  run 3: 0.0100 s\n"
             "  run 4: 0.0100 s\n  run 5: 0.0098 s\n\n", None),
            ("  median : 0.0100 s\n  mean   : 0.0103 s\n  groups : 30\n", None),
            ("  total revenue across 30 categories: 3,827,746,136.00\n", None),
            ("Wrote results/baseline_result.csv\n\n", None),
            ("$ python benchmark.py\n", None),
            ("26/08/22 14:02:52 WARN NativeCodeLoader: Unable to load native-hadoop "
             "library...\n", "dim"),
            ("Traceback (most recent call last):\n  ...\n", None),
            ("py4j.protocol.Py4JJavaError: An error occurred while calling "
             "None.org.apache.spark.api.java.JavaSparkContext.\n", None),
            (": java.lang.ExceptionInInitializerError\n", None),
            ("Caused by: java.lang.IllegalStateException: java.lang."
             "ClassNotFoundException: jdk.internal.ref.Cleaner\n", None),
            ("        at org.apache.spark.unsafe.Platform.<clinit>(Platform.java:104)\n"
             "        ...\n", None),
            ("FIX: your installed JDK is newer than PySpark supports for this class.\n"
             "     Install JDK 17 (broadest) or JDK 21 (PySpark 4.0+), set JAVA_HOME\n"
             "     to point at it, reopen the terminal, confirm `java -version`,\n"
             "     then rerun.\n", "a"),
        ]

        for chunk, tag in log:
            if tag:
                text.insert("end", chunk, tag)
            else:
                text.insert("end", chunk)
        text.configure(state="disabled")


if __name__ == "__main__":
    app = ConsoleApp()
    app.mainloop()
