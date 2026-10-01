"""
benchmark.py - Session 1, Part 8.

Benchmarks the sequential baseline against several bounded-parallelism
settings and writes results/session1_benchmark.csv.

Method notes that keep the comparison honest:
  - The same input files, join path, workload, and output calculation are
    used for every condition. Only the partition count varies.
  - Each condition runs BENCHMARK_REPEATS times and the median is reported,
    because the first run of any Spark series is inflated by JVM warm-up and
    lazy cache materialisation.
  - Every condition is verified to produce the same group count, so a fast
    result that computed the wrong thing cannot be reported as a win.

Run:
    python benchmark.py
"""

import csv
import statistics
import sys
import time

import config as cfg
from parallel_compute import build_joined, compute_parallel
from sequential_baseline import run_baseline
from load_and_join import build_working_dataset


# --------------------------------------------------------------------------
def bench_one(joined, partitions: int, repeats: int) -> dict:
    """Time one bounded-parallelism condition."""
    times, groups = [], None
    for _ in range(repeats):
        start = time.perf_counter()
        _, result = compute_parallel(joined, partitions)
        groups = result.count()  # force evaluation
        times.append(time.perf_counter() - start)
    return {
        "partitions": partitions,
        "runs": [round(t, 4) for t in times],
        "median": round(statistics.median(times), 4),
        "min": round(min(times), 4),
        "max": round(max(times), 4),
        "groups": groups,
    }


# --------------------------------------------------------------------------
def main() -> int:
    cfg.banner("SESSION 1 - BENCHMARK")

    # ---------------- sequential baseline ----------------
    working, join_report = build_working_dataset(verbose=False)
    baseline_result, baseline_report = run_baseline(working, verbose=False)
    print(f"  join time (pandas) : {join_report['join_seconds']} s")
    print(f"  baseline median    : {baseline_report['median_seconds']} s "
          f"over {baseline_report['repeats']} runs")
    print(f"  baseline groups    : {baseline_report['groups']}")

    # ---------------- parallel conditions ----------------
    spark = cfg.build_spark()
    rows = []
    try:
        joined, spark_join = build_joined(spark, verbose=False)
        print(f"  spark joined rows  : {joined.count():,}")
        print(f"  BroadcastHashJoin  : {spark_join['broadcast_hash_joins']}")
        print(f"  SortMergeJoin      : {spark_join['sort_merge_joins']}")

        cfg.banner("BOUNDED PARALLELISM CONDITIONS")
        results = []
        for partitions in cfg.PARTITION_SETTINGS:
            r = bench_one(joined, partitions, cfg.BENCHMARK_REPEATS)
            results.append(r)
            runs = ", ".join(f"{t:.4f}" for t in r["runs"])
            print(f"  partitions={partitions:>2} | median={r['median']:.4f} s "
                  f"| groups={r['groups']} | runs=[{runs}]")

        # Every condition must produce the same group count.
        group_counts = {r["groups"] for r in results}
        group_counts.add(baseline_report["groups"])
        assert len(group_counts) == 1, (
            f"Conditions disagree on group count: {group_counts}. "
            "A benchmark is not comparable if the runs computed different things."
        )

        # ---------------- assemble the table ----------------
        base_median = baseline_report["median_seconds"]
        rows.append({
            "run": "Sequential baseline",
            "parallelism_partitions": "1 / non-parallel",
            "execution_time_s": f"{base_median:.4f}",
            "groups": baseline_report["groups"],
            "correct": "Yes",
            "speedup_vs_baseline": "1.00",
            "observation": "pandas, in-process, no serialisation",
        })

        best = min(results, key=lambda r: r["median"])
        for r in results:
            speedup = base_median / r["median"]
            if r is best:
                note = "fastest parallel setting"
            elif r["median"] > best["median"]:
                note = "slower than the best setting"
            else:
                note = ""
            rows.append({
                "run": f"Parallel ({r['partitions']} partitions)",
                "parallelism_partitions": r["partitions"],
                "execution_time_s": f"{r['median']:.4f}",
                "groups": r["groups"],
                "correct": "Yes",
                "speedup_vs_baseline": f"{speedup:.4f}",
                "observation": note,
            })

        # ---------------- interpretation ----------------
        cfg.banner("INTERPRETATION")
        print(f"  best parallel setting : {best['partitions']} partitions "
              f"at {best['median']:.4f} s")
        if best["partitions"] != cfg.CHOSEN_PARTITIONS:
            chosen = next((r for r in results
                           if r["partitions"] == cfg.CHOSEN_PARTITIONS), None)
            gap = (f" ({chosen['median']:.4f} s, "
                   f"{chosen['median'] / best['median'] - 1:.0%} slower)" if chosen else "")
            print(f"  NOTE: config.CHOSEN_PARTITIONS = {cfg.CHOSEN_PARTITIONS}{gap} is not")
            print(f"  the fastest setting in this run. If {best['partitions']} wins on repeat")
            print("  runs, update CHOSEN_PARTITIONS; if the winner changes between runs,")
            print("  the settings are within noise and the choice does not matter.")
        ratio = best["median"] / base_median
        if ratio > 1:
            print(f"  Spark is {ratio:.1f}x SLOWER than the pandas baseline.")
            print("  At this data volume the dataset fits comfortably in memory,")
            print("  so JVM start-up, task scheduling, serialisation, and the")
            print("  Python-JVM boundary dominate the computation. This is a")
            print("  valid finding: parallelism is not free and is not always")
            print("  warranted. Re-run on a larger dataset and a multi-core")
            print("  machine before drawing scalability conclusions.")
        else:
            print(f"  Spark is {1 / ratio:.2f}x faster than the baseline.")

        if spark_join["sort_merge_joins"] == 0:
            print("\n  All three joins broadcast: no shuffle cost anywhere in the")
            print("  pipeline. Differences between partition counts are scheduling")
            print("  overhead only.")
        else:
            print("\n  The order_items |> orders join shuffled (stores and products")
            print("  still broadcast). Part of the runtime at every partition count")
            print("  is shuffle cost, not just scheduling overhead - unlike the")
            print("  course template dataset where every join was small enough to")
            print("  broadcast.")
    finally:
        spark.stop()

    # ---------------- write the table ----------------
    fields = ["run", "parallelism_partitions", "execution_time_s", "groups",
              "correct", "speedup_vs_baseline", "observation"]
    with open(cfg.OUT_BENCHMARK, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {cfg.OUT_BENCHMARK}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
