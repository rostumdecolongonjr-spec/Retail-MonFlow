"""
parallel_compute.py - Session 1, Parts 7 and 9.

Partitioned parallel implementation in PySpark local mode, plus the
correctness check against the sequential baseline.

Two design decisions are worth stating explicitly.

Mixed broadcast strategy. stores (100 rows) and products (10,000 rows,
~155 KB) are small enough to replicate to every worker, so both joins that
use them are hinted with F.broadcast(). orders (300,000 rows, ~8.5 MB on
disk) is deliberately NOT broadcast - it is large enough to be a realistic
shuffle candidate, so the order_items |> orders join is left to Spark's
join planner. Which strategy it picks depends on the size estimate and
spark.sql.autoBroadcastJoinThreshold, so it is read from the physical plan
rather than assumed. On the real 600,000-row dataset Spark broadcast the
orders join as well (0 SortMergeJoin), so no join shuffled.

Bounded parallelism. repartition(n, key) is called with an explicit n rather
than relying on the default. local[*] uses whatever cores are available,
which is not a documented, tuned, or reproducible setting.

Importable:
    from parallel_compute import build_joined, compute_parallel, validate

Run:
    python parallel_compute.py
"""

import json
import sys
import time

import pandas as pd  # type: ignore
from pyspark.sql import functions as F

import config as cfg

# --------------------------------------------------------------------------
def load_spark_frames(spark):
    """Read each input file on the join path into a Spark DataFrame."""
    def read(name):
        return (
            spark.read
            .option("header", True)
            .option("inferSchema", True)
            .csv(str(cfg.path_for(name)))
        )

    order_items = read("order_items").withColumnRenamed("price", "unit_price")
    orders = read("orders")
    stores = read("stores").withColumnRenamed("city", "store_city")
    products = read("products").withColumnRenamed("price", "catalog_price")
    return order_items, orders, stores, products


# --------------------------------------------------------------------------
def count_join_nodes(plan: str) -> tuple[int, int]:
    """
    Count BroadcastHashJoin / SortMergeJoin operators in a physical plan string.

    With adaptive query execution (on by default since Spark 3.2) a finished
    plan prints the same tree twice, under "== Final Plan ==" and
    "== Initial Plan ==", so a plain str.count() reported 6 joins for a 3-join
    query. Only the final plan is counted, and only operator lines (lines
    whose operator name follows the tree prefix), not mentions in arguments.
    """
    if "== Initial Plan ==" in plan:
        plan = plan.split("== Initial Plan ==")[0]
    bhj = smj = 0
    for line in plan.splitlines():
        op = line.lstrip(" :+-*()0123456789")
        if op.startswith("BroadcastHashJoin"):
            bhj += 1
        elif op.startswith("SortMergeJoin"):
            smj += 1
    return bhj, smj


# --------------------------------------------------------------------------
def build_joined(spark, verbose: bool = True):
    """Join order_items to orders, stores, and products in Spark."""
    from pyspark.sql import functions as F

    order_items, orders, stores, products = load_spark_frames(spark)

    rows_before = order_items.count()
    input_partitions = order_items.rdd.getNumPartitions()

    joined = (
        order_items
        # orders is NOT broadcast - it is the one join in this pipeline
        # large enough to plausibly shuffle.
        .join(orders, on=cfg.ORDER_KEY, how="inner")
        .join(F.broadcast(stores), on=cfg.STORE_KEY, how="inner")
        .join(F.broadcast(products), on=cfg.PRODUCT_KEY, how="inner")
        .withColumn(cfg.METRIC_FIELD, F.col("qty") * F.col("unit_price"))
    )
    joined.cache()
    rows_after = joined.count()

    # Inspect the physical plan to confirm the join strategy actually chosen,
    # rather than assuming the broadcast hints were honoured and rather than
    # assuming the un-hinted orders join shuffled.
    plan = joined._jdf.queryExecution().executedPlan().toString()
    broadcast_nodes, sortmerge_nodes = count_join_nodes(plan)

    report = {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "delta": rows_after - rows_before,
        "input_partitions": input_partitions,
        "broadcast_hash_joins": broadcast_nodes,
        "sort_merge_joins": sortmerge_nodes,
    }

    if verbose:
        cfg.banner("SPARK JOIN")
        print(f"  rows before join   : {rows_before:,}")
        print(f"  rows after join    : {rows_after:,}")
        print(f"  difference         : {report['delta']}")
        print(f"  input partitions   : {input_partitions}")
        print(f"  BroadcastHashJoin  : {broadcast_nodes}")
        print(f"  SortMergeJoin      : {sortmerge_nodes}")
        if sortmerge_nodes == 0:
            print("  -> Spark broadcast the orders join too (it fit under")
            print("     spark.sql.autoBroadcastJoinThreshold); no shuffle occurred")
        else:
            print("  -> order_items |> orders shuffled as expected; stores and")
            print("     products still broadcast, so only one join pays the shuffle cost")

    assert rows_after == rows_before, "Spark join changed the row count"
    return joined, report


# --------------------------------------------------------------------------
def compute_parallel(joined, partitions: int):
    """
    Repartition with an explicit bound, then aggregate.

    repartition() is what makes the parallelism bounded and documented rather
    than whatever the framework happens to choose.
    """
    from pyspark.sql import functions as F

    partitioned = joined.repartition(partitions, cfg.PARTITION_KEY)
    result = (
        partitioned
        .groupBy(cfg.PARTITION_KEY)
        .agg(
            F.count(cfg.METRIC_FIELD).alias("line_count"),
            F.sum(cfg.METRIC_FIELD).alias("revenue_total"),
            F.avg(cfg.METRIC_FIELD).alias("revenue_mean"),
        )
    )
    return partitioned, result


# --------------------------------------------------------------------------
def validate(parallel_pd: pd.DataFrame,
             baseline_pd: pd.DataFrame,
             verbose: bool = True) -> dict:
    """
    Compare parallel output against the sequential baseline.

    Row counts are checked before values. With multi-file joins an incorrect
    join duplicates records without raising an error and still produces
    plausible-looking averages, so a values-only check can pass on data that
    is wrong.
    """
    parallel_pd = parallel_pd.sort_values(cfg.PARTITION_KEY).reset_index(drop=True)
    baseline_pd = baseline_pd.sort_values(cfg.PARTITION_KEY).reset_index(drop=True)

    group_match = len(parallel_pd) == len(baseline_pd)
    merged = parallel_pd.merge(
        baseline_pd, on=cfg.PARTITION_KEY, suffixes=("_par", "_base")
    )
    count_diff = int((merged["line_count_par"] - merged["line_count_base"]).abs().max())
    total_diff = float((merged["revenue_total_par"] -
                         merged["revenue_total_base"]).abs().max())
    mean_diff = float((merged["revenue_mean_par"] -
                        merged["revenue_mean_base"]).abs().max())

    passed = group_match and count_diff == 0 and mean_diff < cfg.TOLERANCE

    report = {
        "parallel_groups": int(len(parallel_pd)),
        "baseline_groups": int(len(baseline_pd)),
        "group_count_match": group_match,
        "max_line_count_difference": count_diff,
        "max_revenue_total_difference": total_diff,
        "max_revenue_mean_difference": mean_diff,
        "tolerance": cfg.TOLERANCE,
        "passed": bool(passed),
    }

    if verbose:
        cfg.banner("CORRECTNESS VALIDATION")
        print(f"  parallel groups           : {report['parallel_groups']}")
        print(f"  baseline groups           : {report['baseline_groups']}")
        print(f"  max line_count difference : {count_diff}")
        print(f"  max revenue_total diff    : {total_diff:.6e}")
        print(f"  max revenue_mean diff     : {mean_diff:.6e}")
        print(f"  tolerance                 : {cfg.TOLERANCE:.0e}")
        print(f"\n  {'PASSED' if passed else 'FAILED'}")
        if passed and mean_diff > 0:
            print("  Residual is floating-point summation order: Spark sums each")
            print("  partition independently, then combines. Both are correct to")
            print("  double precision.")

    if not passed:
        raise AssertionError(
            "Correctness check FAILED. Investigate in this order: join keys "
            "and their uniqueness, join type, rows dropped by an inner join, "
            "data types across files, nulls, duplicates, then aggregation "
            "logic. In a multi-file workload the fault is far more often in "
            "the join than in the aggregation."
        )
    return report


# --------------------------------------------------------------------------
def main() -> int:
    cfg.banner("SESSION 1 - PARALLEL COMPUTE")
    spark = cfg.build_spark()
    try:
        joined, join_report = build_joined(spark)

        cfg.banner(f"PARALLEL AGGREGATION - {cfg.CHOSEN_PARTITIONS} PARTITIONS")
        start = time.perf_counter()
        partitioned, result = compute_parallel(joined, cfg.CHOSEN_PARTITIONS)
        groups = result.count()  # materialise for timing
        elapsed = time.perf_counter() - start
        print(f"  configured partitions : {partitioned.rdd.getNumPartitions()}")
        print(f"  result groups         : {groups}")
        print(f"  execution time        : {elapsed:.4f} s")
        result.orderBy("revenue_total", ascending=False).show(10, truncate=False)

        # ---------------- correctness ----------------
        parallel_pd = result.toPandas()
        if cfg.OUT_BASELINE.exists():
            baseline_pd = pd.read_csv(cfg.OUT_BASELINE)
        else:
            print("\n  baseline file not found; computing it now")
            from sequential_baseline import run_baseline
            baseline_pd, _ = run_baseline(verbose=False)

        validation = validate(parallel_pd, baseline_pd)

        # ---------------- persist Session 1 output ----------------
        final = parallel_pd.sort_values(cfg.PARTITION_KEY).reset_index(drop=True)
        try:
            final.to_parquet(cfg.OUT_FINAL, index=False)
        except ImportError:
            fallback = cfg.OUT_FINAL.with_suffix(".pkl")
            final.to_pickle(fallback)
            print(f"  (no pyarrow/fastparquet available - wrote {fallback.name} instead)")
        print(f"\nWrote {cfg.OUT_FINAL} ({len(final)} rows)")

        cfg.OUT_VALIDATION.write_text(json.dumps(
            {"join": join_report,
             "aggregation": {"partitions": cfg.CHOSEN_PARTITIONS,
                              "groups": groups,
                              "seconds": round(elapsed, 4)},
             "validation": validation},
            indent=2))
        print(f"Wrote {cfg.OUT_VALIDATION}")
    finally:
        spark.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
