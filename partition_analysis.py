"""
partition_analysis.py - Session 1, Part 10.

Measures partition balance at two levels and compares both against the
prediction made in partition_strategy.py.

    Key level      - records per distinct partition-key value (category_id).
                     This is what the product/category dimension predicts,
                     because it follows directly from how line items are
                     distributed across the 30 categories.
    Partition level- records per physical Spark partition. This is what
                     actually determines execution time, and it can differ
                     from the key level because a hash partitioner maps many
                     keys onto few partitions, and an unlucky pairing of two
                     heavy keys in one partition is not diluted when the
                     partition count is high.

The gap between the two is the finding worth reporting: a model can predict
key-level skew accurately and still say nothing about the skew the scheduler
actually sees.

Run:
    python partition_analysis.py
"""

import csv
import sys

import config as cfg
from parallel_compute import build_joined
from load_and_join import build_working_dataset


# --------------------------------------------------------------------------
def key_level(working) -> dict:
    """Records per distinct partition-key value."""
    counts = working[cfg.PARTITION_KEY].value_counts()
    return {
        "distinct_keys": int(counts.size),
        "min": int(counts.min()),
        "median": int(counts.median()),
        "max": int(counts.max()),
        "skew_ratio": round(counts.max() / counts.min(), 2),
        "heaviest": counts.head(5).to_dict(),
        "lightest": counts.tail(5).to_dict(),
        "counts": counts,
    }


# --------------------------------------------------------------------------
def partition_level(joined, partitions: int) -> dict:
    """Records per physical Spark partition after repartitioning."""
    sizes = (
        joined
        .repartition(partitions, cfg.PARTITION_KEY)
        .rdd
        .glom()
        .map(len)
        .collect()
    )
    total = sum(sizes)
    even = total / partitions
    return {
        "partitions": partitions,
        "sizes": sizes,
        "min": min(sizes),
        "max": max(sizes),
        "even_share": round(even, 1),
        "skew_ratio": round(max(sizes) / min(sizes), 2) if min(sizes) else float("inf"),
        "worst_vs_even": round(max(sizes) / even, 2),
    }


# --------------------------------------------------------------------------
def main() -> int:
    cfg.banner("SESSION 1 - PARTITION ANALYSIS")
    working, _ = build_working_dataset(verbose=False)

    # ---------------- key level ----------------
    kl = key_level(working)
    cfg.banner(f"KEY LEVEL - {cfg.PARTITION_KEY}")
    print(f"  distinct keys : {kl['distinct_keys']}")
    print(f"  records/key   : min={kl['min']} median={kl['median']} "
          f"max={kl['max']}")
    print(f"  skew ratio    : {kl['skew_ratio']} : 1")
    print("\n  heaviest 5:")
    for k, v in kl["heaviest"].items():
        print(f"    category {k:<6} {v:>7,}")
    print("  lightest 5:")
    for k, v in kl["lightest"].items():
        print(f"    category {k:<6} {v:>7,}")

    # Compare against the rejected alternatives.
    for alt_key in ("customer_id", "store_city"):
        alt = working[alt_key].value_counts()
        print(f"\n  rejected key '{alt_key}': "
              f"{alt.size:,} distinct, "
              f"min={alt.min()} median={int(alt.median())} max={alt.max()} "
              f"-> ratio {alt.max() / alt.min():.2f}:1")

    # ---------------- partition level ----------------
    spark = cfg.build_spark()
    rows = []
    try:
        joined, _ = build_joined(spark, verbose=False)

        cfg.banner("PARTITION LEVEL")
        header = f"  {'n':>3} {'even':>9} {'min':>8} {'max':>8} {'ratio':>7}"
        print(header)
        print("  " + "-" * (len(header) - 2))
        pls = []
        for partitions in cfg.PARTITION_SETTINGS:
            pl = partition_level(joined, partitions)
            pls.append(pl)
            print(f"  {pl['partitions']:>3} {pl['even_share']:>9,.1f} "
                  f"{pl['min']:>8,} {pl['max']:>8,} {pl['skew_ratio']:>7.2f}")
            for idx, size in enumerate(pl["sizes"]):
                rows.append({
                    "level": "spark_partition",
                    "setting": pl["partitions"],
                    "identifier": f"partition_{idx}",
                    "record_count": size,
                    "even_share": pl["even_share"],
                    "vs_even": round(size / pl["even_share"], 3),
                })

        # ---------------- interpretation ----------------
        cfg.banner("INTERPRETATION")
        print(f"  Key-level skew is fixed at {kl['skew_ratio']}:1 regardless of")
        print("  partition count, because it is a property of the data.")

        first, last = pls[0], pls[-1]
        if last["skew_ratio"] > first["skew_ratio"]:
            print(f"\n  Partition-level skew WORSENS from "
                  f"{first['skew_ratio']}:1 at {first['partitions']} partitions "
                  f"to {last['skew_ratio']}:1 at {last['partitions']}.")
            print("  Cause: hash collision. With few partitions each holds many")
            print("  categories and imbalances average out. With more partitions")
            print("  each holds fewer categories, so an unlucky pairing of two")
            print("  heavy categories in one partition is no longer diluted.")
            print("\n  Mitigation: range partitioning on cumulative volume, or")
            print("  grouping categories into balanced buckets before repartitioning.")
            print("  Salting is unnecessary at this skew level.")
        else:
            print("\n  Partition-level skew does not worsen with partition count.")

        print(f"\n  The slowest task determines elapsed time, so the partition")
        print(f"  holding {last['max']:,} records "
              f"({last['worst_vs_even']}x the even share) bounds the job.")
    finally:
        spark.stop()

    # ---------------- key-level rows ----------------
    for key, count in kl["counts"].items():
        rows.append({
            "level": "partition_key",
            "setting": cfg.PARTITION_KEY,
            "identifier": key,
            "record_count": int(count),
            "even_share": round(len(working) / kl["distinct_keys"], 1),
            "vs_even": round(count / (len(working) / kl["distinct_keys"]), 3),
        })

    fields = ["level", "setting", "identifier", "record_count",
              "even_share", "vs_even"]
    with open(cfg.OUT_PARTITIONS, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {cfg.OUT_PARTITIONS} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
