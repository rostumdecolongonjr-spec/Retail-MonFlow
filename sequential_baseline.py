"""
sequential_baseline.py - Session 1, Part 6.

Computes the reference result with pandas, single-threaded and in-process.

The baseline exists for two reasons. First, without it there is no way to
tell whether parallel processing actually improved anything. Second, it is
the correctness reference: the parallel implementation must reproduce these
numbers, or the speed measurement is meaningless.

The baseline performs the SAME joins and the SAME aggregation as the parallel
version, so any difference in output is a defect rather than a difference in
definition.

Importable:
    from sequential_baseline import run_baseline

Run:
    python sequential_baseline.py
"""

import statistics
import sys
import time

import pandas as pd

import config as cfg
from load_and_join import build_working_dataset

# --------------------------------------------------------------------------
def compute(working: pd.DataFrame) -> pd.DataFrame:
    """
    The workload: line-item count, total revenue, and mean revenue per
    category. Deterministic, so repeated runs are comparable.
    """
    result = (
        working
        .groupby(cfg.PARTITION_KEY)[cfg.METRIC_FIELD]
        .agg(["count", "sum", "mean"])
        .reset_index()
    )
    result.columns = [cfg.PARTITION_KEY, "line_count",
                       "revenue_total", "revenue_mean"]
    return result


# --------------------------------------------------------------------------
def run_baseline(
    working: pd.DataFrame | None = None,
    repeats: int = cfg.BASELINE_REPEATS,
    verbose: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """Run the baseline `repeats` times and report the median."""
    if working is None:
        working, _ = build_working_dataset(verbose=False)

    times, result = [], None
    for _ in range(repeats):
        start = time.perf_counter()
        result = compute(working)
        times.append(time.perf_counter() - start)

    report = {
        "runs": [round(t, 4) for t in times],
        "median_seconds": round(statistics.median(times), 4),
        "mean_seconds": round(statistics.fmean(times), 4),
        "groups": int(len(result)),
        "repeats": repeats,
    }

    if verbose:
        cfg.banner("SEQUENTIAL BASELINE")
        for i, t in enumerate(times, 1):
            print(f"  run {i}: {t:.4f} s")
        print(f"\n  median : {report['median_seconds']:.4f} s")
        print(f"  mean   : {report['mean_seconds']:.4f} s")
        print(f"  groups : {report['groups']}")

    return result, report


# --------------------------------------------------------------------------
def main() -> int:
    cfg.banner("SESSION 1 - SEQUENTIAL BASELINE")
    working, _ = build_working_dataset()
    result, report = run_baseline(working)

    result = result.sort_values("revenue_total", ascending=False)
    print("\n  top 10 categories by revenue:")
    print(result.head(10).to_string(index=False))

    total = result["revenue_total"].sum()
    print(f"\n  total revenue across {len(result)} categories: {total:,.2f}")

    # Saved because the correctness check in parallel_compute.py compares
    # against exactly this result.
    result.sort_values(cfg.PARTITION_KEY).to_csv(cfg.OUT_BASELINE, index=False)
    print(f"\nWrote {cfg.OUT_BASELINE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
