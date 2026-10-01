"""
profile_files.py - Session 1, Parts 2 and 3.

Profiles every input file individually, detects candidate primary keys by
testing column uniqueness, verifies referential integrity across all eleven
foreign-key relationships in the dataset, and evaluates the four dataset
eligibility conditions from the activity sheet.

Writes results/file_profile.json for use by the other scripts and by the
submission document.

Run:
    python profile_files.py
"""

import json
import sys

import pandas as pd

import config as cfg

# --------------------------------------------------------------------------
# Every foreign key in the dataset, as (child_file, child_col, parent_file,
# parent_col). Declaring these once means check_integrity() and the
# eligibility check both draw from the same list rather than two hand-typed
# copies drifting apart.
FOREIGN_KEYS = [
    ("order_items", "order_id",     "orders",     "order_id"),
    ("order_items", "product_id",   "products",   "product_id"),
    ("orders",      "customer_id",  "customers",  "customer_id"),
    ("orders",      "store_id",     "stores",     "store_id"),
    ("orders",      "promotion_id", "promotions", "promotion_id"),
    ("products",    "category_id",  "categories", "category_id"),
    ("products",    "supplier_id",  "suppliers",  "supplier_id"),
    ("employees",   "store_id",     "stores",     "store_id"),
    ("payments",    "order_id",     "orders",     "order_id"),
    ("shipments",   "order_id",     "orders",     "order_id"),
    ("returns",     "order_item_id", "order_items", "order_item_id"),
]


# --------------------------------------------------------------------------
def profile_one(name: str) -> tuple[pd.DataFrame, dict]:
    """Profile a single input file and return the frame plus its profile."""
    path = cfg.path_for(name)
    df = pd.read_csv(path)

    # A column is a candidate primary key if every value is unique and
    # non-null. Several columns can qualify; the semantically correct one is
    # chosen by hand in the file inventory.
    candidate_pks = [
        c for c in df.columns
        if df[c].notna().all() and df[c].is_unique
    ]

    # Columns with a single distinct value carry no information and are worth
    # flagging, because they silently break downstream analytics.
    constant_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]

    prof = {
        "file": path.name,
        "role": cfg.FILES[name]["role"],
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": df.columns.tolist(),
        "size_kb": round(path.stat().st_size / 1024, 1),
        "candidate_primary_keys": candidate_pks,
        "constant_columns": constant_cols,
        "null_counts": {c: int(df[c].isna().sum()) for c in df.columns},
        "distinct_counts": {c: int(df[c].nunique(dropna=True)) for c in df.columns},
    }
    return df, prof


# --------------------------------------------------------------------------
def check_integrity(frames: dict[str, pd.DataFrame]) -> dict:
    """Confirm that every one of the eleven foreign keys resolves to a parent row."""
    checks = {}
    orphans = {}
    for child, ckey, parent, pkey in FOREIGN_KEYS:
        parent_ids = set(frames[parent][pkey])
        resolves = frames[child][ckey].isin(parent_ids)
        label = f"{child}.{ckey} -> {parent}.{pkey}"
        checks[label] = bool(resolves.all())
        orphans[f"{child}_without_{parent}"] = int((~resolves).sum())
    return {"foreign_keys_resolve": checks, "orphan_counts": orphans}


# --------------------------------------------------------------------------
def check_eligibility(frames: dict[str, pd.DataFrame], prof: dict) -> dict:
    """Evaluate the four Part 2 eligibility conditions."""
    # Condition 1 - at least three qualifying (non-Lookup) files.
    qualifying = [n for n, p in prof.items() if p["role"] in ("Event", "Entity")]

    # Condition 2 - at least one genuine one-to-many association. A child
    # whose foreign key is unique is a 1:1 extension, not a 1..* relation.
    order_items = frames["order_items"]
    orders = frames["orders"]
    payments = frames["payments"]
    shipments = frames["shipments"]

    one_to_many = []
    if not order_items[cfg.ORDER_KEY].is_unique:
        per_parent = order_items[cfg.ORDER_KEY].value_counts()
        one_to_many.append({
            "parent": "orders", "child": "order_items", "key": cfg.ORDER_KEY,
            # value_counts() only sees parents that HAVE children, so its min is
            # never 0. Count the childless parents explicitly: they make the real
            # multiplicity 0..*, not 1..*.
            "parents_total": int(len(orders)),
            "parents_without_children": int(len(orders) - per_parent.size),
            "children_min": int(per_parent.min()),
            "children_median": int(per_parent.median()),
            "children_max": int(per_parent.max()),
        })
    if not orders[cfg.CUSTOMER_KEY].is_unique:
        per_parent = orders[cfg.CUSTOMER_KEY].value_counts()
        one_to_many.append({
            "parent": "customers", "child": "orders", "key": cfg.CUSTOMER_KEY,
            "parents_total": int(len(frames["customers"])),
            "parents_without_children": int(len(frames["customers"]) - per_parent.size),
            "children_min": int(per_parent.min()),
            "children_median": int(per_parent.median()),
            "children_max": int(per_parent.max()),
        })

    payments_is_1to1 = bool(payments[cfg.ORDER_KEY].is_unique)
    shipments_is_1to1 = bool(shipments[cfg.ORDER_KEY].is_unique)

    # Condition 3 - a usable timestamp (lives on orders).
    ts = pd.to_datetime(orders[cfg.EVENT_TIME_FIELD], format="mixed", utc=True,
                        errors="coerce")

    # Condition 4 - transactional volume.
    event_rows = sum(p["rows"] for p in prof.values() if p["role"] == "Event")

    return {
        "condition_1_three_related_files": {
            "met": len(qualifying) >= 3,
            "qualifying_files": qualifying,
            "lookup_files_excluded":
                [n for n, p in prof.items() if p["role"] == "Lookup"],
        },
        "condition_2_one_to_many": {
            "met": len(one_to_many) >= 1,
            "associations": one_to_many,
            "payments_is_one_to_one": payments_is_1to1,
            "shipments_is_one_to_one": shipments_is_1to1,
        },
        "condition_3_timestamp": {
            # Usable = every value parses and the range is not a single instant.
            "met": bool(ts.notna().all() and (ts.max() - ts.min()).days > 0),
            "unparseable": int(ts.isna().sum()),
            "field": f"orders.{cfg.EVENT_TIME_FIELD}",
            "min": str(ts.min()),
            "max": str(ts.max()),
            "span_days": int((ts.max() - ts.min()).days),
        },
        "condition_4_volume": {
            "met": event_rows >= 50_000,
            "event_rows": event_rows,
        },
    }


# --------------------------------------------------------------------------
def main() -> int:
    cfg.banner("SESSION 1 - FILE PROFILING")
    frames, prof = {}, {}
    for name in cfg.FILES:
        df, p = profile_one(name)
        frames[name], prof[name] = df, p
        print(f"\nFILE: {p['file']:<22} role={p['role']:<7} "
              f"rows={p['rows']:>7,} cols={p['columns']} "
              f"size={p['size_kb']:>9} KB")
        print(f"  columns: {', '.join(p['column_names'])}")
        print(f"  candidate primary keys: {p['candidate_primary_keys']}")
        if p["constant_columns"]:
            print(f"  WARNING constant columns (no variance): "
                  f"{p['constant_columns']}")

    cfg.banner("REFERENTIAL INTEGRITY (11 foreign keys)")
    integrity = check_integrity(frames)
    for label, ok in integrity["foreign_keys_resolve"].items():
        print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print(f"  orphan records: {integrity['orphan_counts']}")

    cfg.banner("DATASET ELIGIBILITY (Part 2)")
    elig = check_eligibility(frames, prof)
    for key, result in elig.items():
        print(f"  {'MET ' if result['met'] else 'NOT MET'}  {key}")
    for assoc in elig["condition_2_one_to_many"]["associations"]:
        print(f"    {assoc['parent']} 1..* {assoc['child']} on {assoc['key']}: "
              f"min={assoc['children_min']} "
              f"median={assoc['children_median']} "
              f"max={assoc['children_max']}")
        if assoc.get("parents_without_children"):
            print(f"      {assoc['parents_without_children']:,} of "
                  f"{assoc['parents_total']:,} {assoc['parent']} have no "
                  f"{assoc['child']} -> multiplicity is 0..*, not 1..*")
    if elig["condition_2_one_to_many"]["payments_is_one_to_one"]:
        print("    NOTE payments.order_id is unique -> 1:1 extension "
              "of Order, not a second 1..* association")
    if elig["condition_2_one_to_many"]["shipments_is_one_to_one"]:
        print("    NOTE shipments.order_id is unique -> 1:1 extension "
              "of Order, not a second 1..* association")

    report = {"profiles": prof, "integrity": integrity, "eligibility": elig}
    cfg.OUT_PROFILE.write_text(json.dumps(report, indent=2))
    print(f"\nWrote {cfg.OUT_PROFILE}")

    all_met = all(v["met"] for v in elig.values())
    all_fk = all(integrity["foreign_keys_resolve"].values())
    if not (all_met and all_fk):
        print("\nDATASET NOT ELIGIBLE - select a different dataset.")
        return 1

    print("\nAll eligibility conditions met. Proceed to load_and_join.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
