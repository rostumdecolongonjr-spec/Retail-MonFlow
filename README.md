# Session 1 — Retail-Orders Parallel Compute Pipeline

MIT 261 Parallel and Distributed Systems · Session 1 (Foundations in In-Memory Cluster Compute)
Project: **Retail-MonFlow** · Student: Rostum D. Decolongon Jr.

Adapted from the MIT 261 Session 1 (CMA-Flow) code guide to run against the
12-file Kaggle "Retail Data Warehouse – 12 Table 1M+ Rows" dataset
(categories, customers, employees, order_items, orders, payments, products,
promotions, returns, shipments, stores, suppliers).

## What changed from the course template

| Original (CMA-Flow) | This version (Retail-Orders) |
|---|---|
| 4 files (transactions, customers, entitlements, monetization_configs) | 12 files, 4 on the primary join path (order_items, orders, stores, products) |
| 60,000 event rows | 1,530,000 event rows (600,000 in `order_items`, the fact table) |
| Partition key `region` (50 values, 1.82:1 skew) | Partition key `category_id` (30 values, 1.22:1 skew) |
| Rejected `customer_id` (perfectly uniform) | Rejected `customer_id` (43:1 skew but per-customer granularity) and `store_city` (only 4 values) |
| Metric `amount` (raw column) | Metric `amount` = `qty * unit_price` (derived) |
| All parent files broadcast | `stores` + `products` broadcast by hint; `orders` left to Spark's planner, which also broadcast it |
| 1:1 relation found: `entitlements` | 1:1 relations found: `payments` and `shipments` (both unique on `order_id`) |

## Requirements

- Python 3 with `pandas`, `pyspark`, `pyarrow` (`pip install pandas pyspark pyarrow`)
- Java JDK 17 with `JAVA_HOME` pointing at it (a newer JDK crashed this PySpark build)
- Graphviz (`dot`) for `render_diagrams.py`
- The 12 CSV files in `Datasets/`

On Windows, Spark warns that `winutils.exe` / `HADOOP_HOME` are missing and that
PySpark does not yet fully support pandas >= 3.0. Both warnings are harmless here.

## Running the pipeline

Run from inside this folder, in this order:

```bash
python profile_files.py        # Parts 2-3: inventory, 11 FK checks, 4 eligibility conditions
python load_and_join.py        # Part 4: join path + row reconciliation
python partition_strategy.py   # Part 5: every column scored as a partition-key candidate
python sequential_baseline.py  # Part 6: pandas reference result
python parallel_compute.py     # Parts 7, 9: Spark join + aggregation + correctness check
python benchmark.py            # Part 8: baseline vs 2/4/8 partitions
python partition_analysis.py   # Part 10: key-level vs physical-partition skew
python render_diagrams.py      # Parts 4, 11: entity model + architecture diagrams
```

Or open the desktop console, which runs the same scripts and shows every table
read straight from `results/`:

```bash
python retail_orders_console.py
```

## Results (measured October 1, 2026 on the benchmarking machine:
Intel Core i5 11th Gen @ 2.40 GHz, 12 GB RAM, Windows 11 Home)

**Dataset and join**
- 12 files profiled; 11/11 foreign keys resolve with 0 orphans; all 4 eligibility conditions met
- Join `order_items |> orders |> stores |> products`: 600,000 → 600,000 rows, 14 columns
- `orders.order_date`: 2020-01-01 → 2024-01-01 (1,461 days), 0 unparseable values

**Partition key**
- `category_id`: 30 values, 17,618 / 20,066 / 21,429 records (min / median / max), skew 1.22:1
- 14 columns scored, 5 numerically and semantically viable

**Baseline vs parallel (`results/session1_benchmark.csv`)**

| Run | Median (s) | vs pandas |
|---|---|---|
| Sequential baseline (pandas, 5 runs) | 0.0168 | 1.00 |
| Spark, 2 partitions (3 runs) | 0.3614 | 21.5x slower |
| Spark, **4 partitions** (3 runs) | **0.2319** | 13.8x slower — fastest Spark setting |
| Spark, 8 partitions (3 runs) | 0.2557 | 15.2x slower |

At 600,000 rows the data fits in memory, so Spark's fixed costs (JVM start-up,
task scheduling, serialisation, the Python–JVM boundary) dominate. That is the
finding, not a defect. The final physical plan shows BroadcastHashJoin = 3 and
SortMergeJoin = 0: every join was broadcast, so no join shuffled.

**Correctness (`results/validation_report.json`)** — PASSED: 30 vs 30 groups,
max `line_count` difference 0, max `revenue_mean` difference 9.09e-13
(tolerance 1e-6). Total revenue 3,827,746,136.00 across 30 categories.

**Partition balance (`results/partition_sizes.csv`)** — key-level skew is fixed
at 1.22:1, but physical-partition skew grows with the partition count:
1.73:1 at 2, 2.00:1 at 4, 6.05:1 at 8 (largest partition 120,010 records,
1.60x the even share), because hashing 30 categories onto more partitions
stops diluting heavy pairs.

## Final choice

- Partition key: **`category_id`**
- Partition count: **4** (`CHOSEN_PARTITIONS` in `config.py`) — the fastest
  Spark setting in the final benchmark *and* far better balanced than 8
  partitions (2.00:1 vs 6.05:1). In an earlier run 8 partitions was ahead by
  only 0.0016 s, so the 4-vs-8 timing gap is near run-to-run noise; the balance
  difference is not.

## Data notes for later sessions

- 40,767 of 300,000 orders have no line items, and 114 of 50,000 customers have
  no orders, so both associations are 0..*, not 1..*.
- `payments.amount` equals the order's line-item total (sum of qty × price) for
  only 10 of 259,233 orders. Revenue is therefore reconciled against
  `order_items`, never against `payments`.

## Outputs (`results/`)

| File | Written by |
|---|---|
| `file_profile.json` | `profile_files.py` |
| `working_dataset.parquet` | `load_and_join.py` |
| `partition_strategy.json` | `partition_strategy.py` |
| `baseline_result.csv` | `sequential_baseline.py` — the reference Session 2 reconciles against |
| `category_revenue.parquet`, `validation_report.json` | `parallel_compute.py` |
| `session1_benchmark.csv` | `benchmark.py` |
| `partition_sizes.csv` | `partition_analysis.py` |

Diagrams: `docs/entity-model-session1.png`, `architecture/architecture-session1.png`.
