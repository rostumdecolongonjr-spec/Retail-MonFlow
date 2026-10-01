"""
load_and_join.py - Session 1, Part 4.

Assembles the working dataset from the four files on the primary join path,
and reconciles the row count before and after.

Join path (all inner, all many-to-one from the order_items side):

    order_items
      |> orders    on order_id
      |> stores    on store_id
      |> products  on product_id

Every merge passes validate="many_to_one". That argument is the cheapest
defence against a silent join error: if the parent key is not unique, pandas
raises instead of quietly multiplying rows. Without it a duplicated key
inflates the row count, every downstream measurement is wrong, and nothing
reports a failure.

Importable:
    from load_and_join import load_frames, build_working_dataset

Run:
    python load_and_join.py
"""

import sys
import time

import pandas as pd

import config as cfg

# Only the four files on the primary join path are needed for the working
# dataset. The other eight (customers, employees, suppliers, categories,
# promotions, payments, shipments, returns) are profiled in Part 2-3 and
# available for a later session, but are not part of this workload.
JOIN_FILES = ("order_items", "orders", "stores", "products")


# --------------------------------------------------------------------------
def load_frames() -> dict[str, pd.DataFrame]:
    """Read the four files on the join path into DataFrames."""
    return {name: pd.read_csv(cfg.path_for(name)) for name in JOIN_FILES}


# --------------------------------------------------------------------------
def build_working_dataset(
    frames: dict[str, pd.DataFrame] | None = None,
    verbose: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """
    Join order_items to orders, stores, and products.

    Returns the joined frame and a reconciliation report. Raises AssertionError
    if the join changed the row count, which would mean duplication or loss.
    """
    if frames is None:
        frames = load_frames()

    order_items = frames["order_items"]
    orders = frames["orders"]
    stores = frames["stores"]
    products = frames["products"]

    rows_before = len(order_items)

    # order_items.price and products.price collide, and stores.city could be
    # confused with a future customer.city, so both are renamed before the
    # merge to keep every surviving column self-explanatory.
    oi = order_items.rename(columns={"price": "unit_price"})
    st = stores.rename(columns={"city": "store_city"})
    pr = products.rename(columns={"price": "catalog_price"})

    start = time.perf_counter()
    working = (
        oi
        .merge(orders, on=cfg.ORDER_KEY, how="inner", validate="many_to_one")
        .merge(st, on=cfg.STORE_KEY, how="inner", validate="many_to_one")
        .merge(pr, on=cfg.PRODUCT_KEY, how="inner", validate="many_to_one")
    )
    join_seconds = time.perf_counter() - start

    # The metric is derived, not a raw column: line-item revenue is quantity
    # times the price actually charged on that order line (not the catalog
    # price on products, which can differ due to promotions/repricing).
    working[cfg.METRIC_FIELD] = working["qty"] * working["unit_price"]

    rows_after = len(working)

    report = {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "delta": rows_after - rows_before,
        "columns_after": len(working.columns),
        "join_seconds": round(join_seconds, 4),
        "join_path": "order_items |> orders |> stores |> products",
    }

    if verbose:
        cfg.banner("JOIN PATH RECONCILIATION")
        print(f"  join path        : {report['join_path']}")
        print(f"  rows before join  : {rows_before:,}")
        print(f"  rows after join   : {rows_after:,}")
        print(f"  difference        : {report['delta']}")
        print(f"  columns after     : {report['columns_after']}")
        print(f"  join time         : {report['join_seconds']} s")

    # An inner join on a many-to-one relationship must not increase the row
    # count. An increase means a parent key is not unique. A decrease means
    # unmatched keys were dropped - confirm that is intended before ignoring.
    assert rows_after == rows_before, (
        f"Join changed the row count: {rows_before} -> {rows_after}. "
        "Check key uniqueness on the parent side and unmatched foreign keys."
    )

    return working, report


# --------------------------------------------------------------------------
def main() -> int:
    cfg.banner("SESSION 1 - LOAD AND JOIN")
    frames = load_frames()
    for name, df in frames.items():
        print(f"  loaded {name:<14} {len(df):>7,} rows")

    working, report = build_working_dataset(frames)

    print("\n  working dataset columns:")
    for col in working.columns:
        print(f"    - {col}")

    # Persist so the baseline and validation steps use identical input.
    # Parquet preserves dtypes across the process boundary (see the docx
    # guide's discussion of why CSV round-trips are unsafe here); it needs
    # pyarrow or fastparquet installed. Environments without either engine
    # fall back to pickle, which also preserves dtypes exactly.
    try:
        working.to_parquet(cfg.OUT_JOINED, index=False)
    except ImportError:
        fallback = cfg.OUT_JOINED.with_suffix(".pkl")
        working.to_pickle(fallback)
        print(f"  (no pyarrow/fastparquet available - wrote {fallback.name} instead)")
    print(f"\nWrote {cfg.OUT_JOINED} ({len(working):,} rows)")

    # Quick distribution preview of the partition key.
    counts = working[cfg.PARTITION_KEY].value_counts()
    cfg.banner(f"PARTITION KEY PREVIEW - {cfg.PARTITION_KEY}")
    print(f"  distinct values : {counts.size}")
    print(f"  records per key : min={counts.min()} "
          f"median={int(counts.median())} max={counts.max()}")
    print(f"  skew ratio      : {counts.max() / counts.min():.2f} : 1")
    print(f"\n  heaviest 5:\n{counts.head(5).to_string()}")
    print(f"\n  lightest 5:\n{counts.tail(5).to_string()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
