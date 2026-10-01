"""
partition_strategy.py - Session 1, Part 5.

Produces every row of the "Partitioning Strategy and Workload Definition"
table, and shows the evidence for rejecting the alternative keys.

The point of this script is that the partition key should be a *derived*
choice, not an asserted one. It evaluates every candidate key in the joined
dataset against three tests and reports which ones fail and why:

  1. Cardinality  - too few distinct values and you cannot fill the workers;
                    too many and per-partition work becomes trivial relative
                    to scheduling overhead.
  2. Variance     - a perfectly uniform key produces perfectly even partitions
                    and leaves the Part 10 skew analysis with nothing to say.
  3. Join survival- the key must exist in the joined frame, which means it
                    must come through the join rather than being dropped or
                    aggregated away.

A fourth, semantic test is applied by hand afterwards: a column can pass all
three numeric tests and still be a poor partition key if it is an identifier
or a continuous financial value rather than a business dimension (order_id,
unit_price, catalog_price). That judgment call is recorded alongside the
numeric evidence rather than folded silently into it.

Run:
    python partition_strategy.py
"""

import json
import sys

import pandas as pd

import config as cfg
from load_and_join import build_working_dataset, load_frames

# Columns that are identifiers of the event itself, or the measure being
# aggregated, and are therefore never sensible partition keys regardless of
# their statistics.
NEVER_PARTITION = {"order_item_id", cfg.METRIC_FIELD, "order_date"}

# Columns that pass the numeric tests below but are rejected on semantic
# grounds: foreign-key identifiers or continuous price fields rather than
# business dimensions. Recorded here, separately from NEVER_PARTITION, so
# the numeric verdict and the semantic verdict both stay visible.
SEMANTICALLY_WEAK = {
    "order_id": "foreign key into orders, not a grouping dimension",
    "unit_price": "continuous financial value, not a grouping dimension",
    "catalog_price": "continuous financial value, not a grouping dimension",
    "product_id": "near-SKU granularity (10,000 groups) - too fine for a "
                   "regional/category-style rollup",
    "customer_id": "49,751 groups is per-customer granularity, not a "
                    "dimensional rollup; skew is real (43:1) but reflects "
                    "individual purchase frequency, not a business segment",
    "store_city": "only 4 distinct values - cannot fill 8 worker partitions "
                   "without forcing multiple partitions to share one key",
}

MIN_DISTINCT = 2
MAX_DISTINCT_RATIO = 0.5  # distinct values must be < 50% of row count


# --------------------------------------------------------------------------
def owning_file(column: str, frames: dict[str, pd.DataFrame]) -> str:
    """Which input file a column originally came from."""
    owners = [name for name, df in frames.items() if column in df.columns]
    if not owners:
        # Column was renamed during the join (e.g. price -> unit_price /
        # catalog_price, city -> store_city), or derived (amount).
        return "derived in join"
    return " + ".join(owners)


def evaluate(working: pd.DataFrame,
             frames: dict[str, pd.DataFrame]) -> list[dict]:
    """Score every column in the joined frame as a partition-key candidate."""
    rows = len(working)
    candidates = []
    for col in working.columns:
        counts = working[col].value_counts()
        distinct = int(counts.size)
        rejects = []

        if col in NEVER_PARTITION:
            rejects.append("identifier, measure, or timestamp")
        if distinct < MIN_DISTINCT:
            rejects.append(f"only {distinct} distinct value")
        if distinct > rows * MAX_DISTINCT_RATIO:
            rejects.append(f"{distinct:,} distinct values is near-unique")

        skew = round(counts.max() / counts.min(), 2) if distinct else 0.0
        if not rejects and skew == 1.0:
            rejects.append("perfectly uniform - no skew to analyse")

        numerically_viable = not rejects
        if numerically_viable and col in SEMANTICALLY_WEAK:
            rejects.append(SEMANTICALLY_WEAK[col])

        candidates.append({
            "column": col,
            "source_file": owning_file(col, frames),
            "distinct": distinct,
            "min": int(counts.min()) if distinct else 0,
            "median": int(counts.median()) if distinct else 0,
            "max": int(counts.max()) if distinct else 0,
            "skew_ratio": skew,
            "numerically_viable": numerically_viable,
            "viable": not rejects,
            "rejected_because": "; ".join(rejects),
        })
    return candidates


# --------------------------------------------------------------------------
def survives_join(key: str, frames: dict[str, pd.DataFrame],
                   working: pd.DataFrame) -> dict:
    """
    Confirm the chosen key is present after the join and trace where it
    entered from. A key that exists only in a file dropped or aggregated
    away during the join is not acceptable.
    """
    present = key in working.columns
    origin = owning_file(key, frames)
    nulls = int(working[key].isna().sum()) if present else None
    return {
        "key": key,
        "present_after_join": present,
        "entered_from": origin,
        "nulls_after_join": nulls,
        "verdict": ("survives the join intact" if present and nulls == 0
                    else "DOES NOT survive the join"),
    }


# --------------------------------------------------------------------------
def main() -> int:
    cfg.banner("SESSION 1 - PARTITIONING STRATEGY (Part 5)")
    frames = load_frames()
    working, join_report = build_working_dataset(frames, verbose=False)
    print(f"  joined dataset: {len(working):,} rows x "
          f"{len(working.columns)} columns")

    # ---------------- candidate evaluation ----------------
    cfg.banner("CANDIDATE PARTITION KEYS")
    candidates = evaluate(working, frames)
    header = (f"  {'column':<16}{'distinct':>9}{'min':>8}{'median':>8}"
              f"{'max':>8}{'skew':>7} verdict")
    print(header)
    print("  " + "-" * (len(header) + 25))
    for c in sorted(candidates, key=lambda x: (not x["viable"], -x["skew_ratio"])):
        verdict = "VIABLE" if c["viable"] else c["rejected_because"]
        print(f"  {c['column']:<16}{c['distinct']:>9,}{c['min']:>8,}"
              f"{c['median']:>8,}{c['max']:>8,}{c['skew_ratio']:>7.2f}"
              f"  {verdict}")

    viable = [c for c in candidates if c["viable"]]
    print(f"\n  {len(viable)} viable candidate(s) of {len(candidates)} columns")

    # ---------------- the chosen key ----------------
    chosen = next(c for c in candidates if c["column"] == cfg.PARTITION_KEY)
    survival = survives_join(cfg.PARTITION_KEY, frames, working)
    cfg.banner(f"CHOSEN KEY: {cfg.PARTITION_KEY}")
    print(f"  entity that owns the key    : {survival['entered_from']}")
    print(f"  distinct key values         : {chosen['distinct']}")
    print(f"  survives the join           : {survival['verdict']}")
    print(f"  nulls after join            : {survival['nulls_after_join']}")
    print(f"  predicted records/partition : min={chosen['min']:,} "
          f"median={chosen['median']:,} max={chosen['max']:,}")
    print(f"  predicted skew ratio        : {chosen['skew_ratio']} : 1")

    # ---------------- the rejected alternatives ----------------
    for alt_key in ("customer_id", "store_city"):
        alt = next(c for c in candidates if c["column"] == alt_key)
        cfg.banner(f"REJECTED ALTERNATIVE: {alt_key}")
        print(f"  distinct values  : {alt['distinct']:,}")
        print(f"  records per key  : min={alt['min']} median={alt['median']} "
              f"max={alt['max']}")
        print(f"  skew ratio       : {alt['skew_ratio']} : 1")
        print(f"  rejected because : {alt['rejected_because'] or '(numerically viable)'}")

    # ---------------- workload definition ----------------
    cfg.banner("WORKLOAD DEFINITION")
    workload = (f"Compute line-item count, total {cfg.METRIC_FIELD}, and "
                f"mean {cfg.METRIC_FIELD} per {cfg.PARTITION_KEY} across the "
                f"joined {len(working):,}-row dataset.")
    print(f"  {workload}")
    schema = {
        cfg.PARTITION_KEY: "int64",
        "line_count": "int64",
        "revenue_total": "double",
        "revenue_mean": "double",
    }
    print("\n  expected output schema:")
    for col, dtype in schema.items():
        print(f"    {col:<16} {dtype}")
    print("\n  independence check: revenue per category requires no data from")
    print("  any other category, so each partition can be computed alone and")
    print("  the partial results combined afterwards.")

    # ---------------- persist ----------------
    out = cfg.RESULTS_DIR / "partition_strategy.json"
    out.write_text(json.dumps({
        "chosen_key": cfg.PARTITION_KEY,
        "owned_by": survival["entered_from"],
        "join_survival": survival,
        "prediction": {
            "distinct": chosen["distinct"],
            "min": chosen["min"],
            "median": chosen["median"],
            "max": chosen["max"],
            "skew_ratio": chosen["skew_ratio"],
        },
        "rejected_alternatives": [
            c for c in candidates if c["column"] in ("customer_id", "store_city")
        ],
        "all_candidates": candidates,
        "workload": workload,
        "output_schema": schema,
        "join": join_report,
    }, indent=2))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
