"""
Shared configuration for MIT 261 Session 1 - retail-orders parallel compute.

Every script in this folder imports from here so that the dataset paths,
partition key, metric field, and benchmark settings are defined exactly
once. Changing a value here changes it for the baseline, the parallel
implementation, the benchmark, and the partition analysis together, which
is what keeps the benchmark conditions comparable.

Dataset : 12-file retail / e-commerce order dataset
 (categories, customers, employees, order_items, orders, payments,
 products, promotions, returns, shipments, stores, suppliers)
Course  : MIT 261 - Parallel and Distributed Systems
Session : 1 - Foundations in In-Memory Cluster Compute
"""

from pathlib import Path

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
# config.py lives in the session1_parallel_compute/ workspace directory.
REPO_ROOT = Path(__file__).resolve().parent
SESSION_DIR = REPO_ROOT
DATA_DIR = SESSION_DIR / "Datasets"
RESULTS_DIR = SESSION_DIR / "results"
DOCS_DIR = REPO_ROOT / "docs"
ARCH_DIR = REPO_ROOT / "architecture"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------
# Input files
# --------------------------------------------------------------------------
# Role classification follows the Session 1 activity sheet:
#   Event  - transactional or time-stamped records
#   Entity - master or dimension data
#   Lookup - small reference tables (do NOT count towards the 3-file minimum)
FILES = {
    "order_items": {"file": "order_items.csv", "role": "Event"},
    "orders":      {"file": "orders.csv",      "role": "Event"},
    "payments":    {"file": "payments.csv",    "role": "Event"},
    "shipments":   {"file": "shipments.csv",   "role": "Event"},
    "returns":     {"file": "returns.csv",     "role": "Event"},
    "customers":   {"file": "customers.csv",   "role": "Entity"},
    "employees":   {"file": "employees.csv",   "role": "Entity"},
    "products":    {"file": "products.csv",    "role": "Entity"},
    "stores":      {"file": "stores.csv",      "role": "Entity"},
    "suppliers":   {"file": "suppliers.csv",   "role": "Entity"},
    "categories":  {"file": "categories.csv",  "role": "Lookup"},
    "promotions":  {"file": "promotions.csv",  "role": "Lookup"},
}


def path_for(name: str) -> Path:
    """Absolute path of one of the input files."""
    return DATA_DIR / FILES[name]["file"]


# --------------------------------------------------------------------------
# Workload definition
# --------------------------------------------------------------------------
# The primary join path (mirrors the four-file join in the course template):
#
#   order_items  (Event, 600,000 rows - the fact table)
#     |> orders     on order_id     (many-to-one)  -- not hinted; Spark decides
#     |> stores     on store_id     (many-to-one)  -- broadcast (tiny)
#     |> products   on product_id   (many-to-one)  -- broadcast (small)
#
# category_id is chosen over store_city (only 4 distinct values - too coarse
# to fill 8 partitions evenly) and over customer_id (49,751 distinct values -
# skew is real at 43:1, but that is per-customer granularity, not a
# dimensional business metric; see partition_strategy.py for the full,
# measured comparison across every column in the joined frame).
PARTITION_KEY = "category_id"
METRIC_FIELD = "amount"          # derived: order_items.qty * order_items.unit_price
EVENT_TIME_FIELD = "order_date"  # lives on orders, carried through the join

# Join keys
ORDER_KEY = "order_id"
STORE_KEY = "store_id"
PRODUCT_KEY = "product_id"
CUSTOMER_KEY = "customer_id"
CATEGORY_KEY = "category_id"
SUPPLIER_KEY = "supplier_id"

# --------------------------------------------------------------------------
# Benchmark settings
# --------------------------------------------------------------------------
PARTITION_SETTINGS = (2, 4, 8)   # bounded parallelism conditions to compare
BENCHMARK_REPEATS = 3            # runs per condition; median is reported
BASELINE_REPEATS = 5
CHOSEN_PARTITIONS = 4            # setting used for the final output; benchmark.py
                                 # warns if a different setting measured fastest

# Numeric tolerance for the correctness check. Spark sums each partition
# independently and then combines, so the addition order differs from pandas
# and tiny floating-point residuals are expected and acceptable.
TOLERANCE = 1e-6

# --------------------------------------------------------------------------
# Spark settings
# --------------------------------------------------------------------------
SPARK_APP_NAME = "MIT261-Session1-RetailOrders"
SPARK_MASTER = "local[*]"
SPARK_DRIVER_MEMORY = "2g"
SPARK_SHUFFLE_PARTITIONS = "8"

# Files small enough to broadcast to every worker rather than shuffle.
# stores = 100 rows (<1 KB), products = 10,000 rows (~155 KB). orders is
# deliberately NOT in this list: at 300,000 rows / ~8.5 MB on disk it is
# comparable to Spark's default autoBroadcastJoinThreshold once loaded into
# JVM objects, so it is left un-hinted for Spark's planner to decide. On the
# real dataset Spark broadcast it anyway (0 SortMergeJoin). parallel_compute.py
# reads the physical plan to report what actually happened.
BROADCAST_FILES = ("stores", "products")

# --------------------------------------------------------------------------
# Output artifacts
# --------------------------------------------------------------------------
OUT_PROFILE = RESULTS_DIR / "file_profile.json"
OUT_JOINED = RESULTS_DIR / "working_dataset.parquet"
OUT_BASELINE = RESULTS_DIR / "baseline_result.csv"
OUT_BENCHMARK = RESULTS_DIR / "session1_benchmark.csv"
OUT_PARTITIONS = RESULTS_DIR / "partition_sizes.csv"
OUT_FINAL = RESULTS_DIR / "category_revenue.parquet"
OUT_VALIDATION = RESULTS_DIR / "validation_report.json"


def build_spark():
    """Create the SparkSession used by every parallel script."""
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder
        .appName(SPARK_APP_NAME)
        .master(SPARK_MASTER)
        .config("spark.driver.memory", SPARK_DRIVER_MEMORY)
        .config("spark.sql.shuffle.partitions", SPARK_SHUFFLE_PARTITIONS)
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")
    return spark


def banner(title: str) -> None:
    """Consistent section heading for console output."""
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)
