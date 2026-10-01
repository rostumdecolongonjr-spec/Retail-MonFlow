
"""
render_diagrams.py - renders the Session 1 and Session 2 diagrams to PNG
with Graphviz.

Outputs:
    docs/entity-model-session1.png
    architecture/architecture-session1.png
    docs/entity-model-session2.png
    architecture/architecture-session2.png

Run:
    python render_diagrams.py
"""

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
ARCH = ROOT / "architecture"

DOCS.mkdir(exist_ok=True)
ARCH.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Graphviz colors
# ---------------------------------------------------------------------------

NAVY = "#1F3864"
BLUE = "#2E74B5"
LIGHT = "#D9EAF7"
AMBER = "#C55A11"
GREY = "#767171"
GREEN = "#548235"


# ---------------------------------------------------------------------------
# 1. Entity model
# ---------------------------------------------------------------------------

ENTITY = f"""
digraph EntityModel {{
    rankdir=TB;
    bgcolor="white";
    splines=polyline;
    nodesep=0.7;
    ranksep=0.9;
    fontname="Helvetica";
    labelloc="t";
    fontsize=17;

    label=<
        <b>Retail-Orders — Session 1 Entity Model</b><br/>
        <font point-size="11">
            12-file order dataset ·
            multiplicity shown at both ends ·
            join path highlighted
        </font>
    >;

    node [
        shape=plaintext
        fontname="Helvetica"
    ];

    edge [
        color="{BLUE}"
        fontname="Helvetica"
        fontsize=9
        penwidth=1.4
    ];


    OrderItem [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>OrderItem</b><br/>
                <font point-size="9">Event · 600,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>order_item_id : Int «PK»</b></td></tr>
        <tr><td align="left">order_id : Int «FK»</td></tr>
        <tr><td align="left">product_id : Int «FK»</td></tr>
        <tr><td align="left">qty : Int</td></tr>
        <tr><td align="left">price : Int (renamed unit_price)</td></tr>
        </table>
    >];


    Order [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Order</b><br/>
                <font point-size="9">Event · 300,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>order_id : Int «PK»</b></td></tr>
        <tr><td align="left">customer_id : Int «FK»</td></tr>
        <tr><td align="left">store_id : Int «FK»</td></tr>
        <tr>
            <td align="left" bgcolor="#FFF2CC">
                order_date : Date <b>«eventTime»</b>
            </td>
        </tr>
        <tr><td align="left">promotion_id : Int «FK»</td></tr>
        </table>
    >];


    Store [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Store</b><br/>
                <font point-size="9">Entity · 100 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>store_id : Int «PK»</b></td></tr>
        <tr><td align="left">city : String (4 distinct)</td></tr>
        </table>
    >];


    Product [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Product</b><br/>
                <font point-size="9">Entity · 10,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>product_id : Int «PK»</b></td></tr>
        <tr>
            <td align="left" bgcolor="#FFF2CC">
                category_id : Int «FK» <b>«partitionKey»</b>
            </td>
        </tr>
        <tr><td align="left">supplier_id : Int «FK»</td></tr>
        <tr><td align="left">price : Int (renamed catalog_price)</td></tr>
        </table>
    >];


    Customer [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Customer</b><br/>
                <font point-size="9">Entity · 50,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>customer_id «PK»</b></td></tr>
        <tr><td align="left">city, signup_date</td></tr>
        </table>
    >];


    Employee [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Employee</b><br/>
                <font point-size="9">Entity · 1,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>employee_id «PK»</b></td></tr>
        <tr><td align="left">store_id «FK», salary</td></tr>
        </table>
    >];


    Supplier [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Supplier</b><br/>
                <font point-size="9">Entity · 200 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>supplier_id «PK»</b></td></tr>
        <tr><td align="left">country</td></tr>
        </table>
    >];


    Category [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="#F2F2F2">
                <b>Category</b><br/>
                <font point-size="9">Lookup · 30 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>category_id «PK»</b></td></tr>
        <tr><td align="left">category_name</td></tr>
        </table>
    >];


    Promotion [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="#F2F2F2">
                <b>Promotion</b><br/>
                <font point-size="9">Lookup · 50 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>promotion_id «PK»</b></td></tr>
        <tr><td align="left">discount</td></tr>
        </table>
    >];


    Payment [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Payment</b><br/>
                <font point-size="9">Event · 300,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>payment_id «PK»</b></td></tr>
        <tr><td align="left">order_id «FK, unique»</td></tr>
        <tr><td align="left">amount</td></tr>
        </table>
    >];


    Shipment [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Shipment</b><br/>
                <font point-size="9">Event · 300,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>shipment_id «PK»</b></td></tr>
        <tr><td align="left">order_id «FK, unique»</td></tr>
        <tr><td align="left">status</td></tr>
        </table>
    >];


    Return [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Return</b><br/>
                <font point-size="9">Event · 30,000 rows</font>
            </td>
        </tr>
        <tr><td align="left"><b>return_id «PK»</b></td></tr>
        <tr><td align="left">order_item_id «FK»</td></tr>
        <tr><td align="left">refund</td></tr>
        </table>
    >];


    // -----------------------------------------------------------------------
    // Four-file join path used by Session 1
    // -----------------------------------------------------------------------

    Order -> OrderItem [
        taillabel="1"
        headlabel="0..*"   // 40,767 of 300,000 orders have no order_items
        label="contains"
        penwidth=2.4
        color="{AMBER}"
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    Store -> Order [
        taillabel="1"
        headlabel="0..*"
        label="fulfils"
        penwidth=2.0
        color="{AMBER}"
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    Product -> OrderItem [
        taillabel="1"
        headlabel="0..*"
        label="sold as"
        penwidth=2.0
        color="{AMBER}"
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];


    // -----------------------------------------------------------------------
    // Remaining relationships
    // -----------------------------------------------------------------------

    Customer -> Order [
        taillabel="1"
        headlabel="0..*"
        label="places"
        style=dashed
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    Store -> Employee [
        taillabel="1"
        headlabel="0..*"
        label="employs"
        style=dashed
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    Category -> Product [
        taillabel="1"
        headlabel="0..*"
        label="classifies"
        style=dashed
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    Supplier -> Product [
        taillabel="1"
        headlabel="0..*"
        label="supplies"
        style=dashed
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    Promotion -> Order [
        taillabel="1"
        headlabel="0..*"
        label="discounts"
        style=dashed
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    // Payment and Shipment are unique on order_id: 1:1 extensions.

    Order -> Payment [
        taillabel="1"
        headlabel="1"
        label="settled by"
        style=dotted
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    Order -> Shipment [
        taillabel="1"
        headlabel="1"
        label="fulfilled via"
        style=dotted
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];

    OrderItem -> Return [
        taillabel="1"
        headlabel="0..*"
        label="may generate"
        style=dotted
        labeldistance=2.0
        labelangle=15
        arrowhead=none
    ];


    // -----------------------------------------------------------------------
    // Notes
    // -----------------------------------------------------------------------

    note1 [
        shape=note
        style=filled
        fillcolor="#FFF9E6"
        color="{AMBER}"
        fontsize=10
        align=left
        label=<
            <b>Partition key: category_id</b><br align="left"/>
            30 distinct values<br align="left"/>
            17,618 / 20,066 / 21,429 records<br align="left"/>
            skew ratio 1.22 : 1<br align="left"/>
            <br align="left"/>
            <b>customer_id rejected:</b><br align="left"/>
            49,751 groups - per-customer<br align="left"/>
            granularity, not a dimension.<br align="left"/>
            <b>store_city rejected:</b><br align="left"/>
            only 4 distinct values - too<br align="left"/>
            coarse to fill 8 partitions.<br align="left"/>
        >
    ];

    note2 [
        shape=note
        style=filled
        fillcolor="#F2F2F2"
        color="{GREY}"
        fontsize=10
        align=left
        label=<
            <b>Lookups (Category, Promotion)</b><br align="left"/>
            Do not count towards the<br align="left"/>
            three-file minimum.<br align="left"/>
            Broadcast at join time when used.<br align="left"/>
        >
    ];

    note1 -> Product [style=invis];
    note2 -> Category [style=invis];

    {{ rank=same; note1; Product; }}
    {{ rank=same; note2; Category; }}
}}
"""


# ---------------------------------------------------------------------------
# 2. Session 1 architecture
# ---------------------------------------------------------------------------

ARCHITECTURE = f"""
digraph Architecture {{
    rankdir=LR;
    bgcolor="white";
    compound=true;
    nodesep=0.35;
    ranksep=0.85;
    fontname="Helvetica";
    labelloc="t";
    fontsize=17;

    label=<
        <b>Retail-Orders — Session 1 Ingestion and Parallel-Compute Layer</b><br/>
        <font point-size="11">
            actual repository file names ·
            PySpark local mode · bounded parallelism = 4
        </font>
    >;

    node [
        shape=box
        style="rounded,filled"
        fontname="Helvetica"
        fontsize=10
        penwidth=1.3
        margin="0.16,0.10"
    ];

    edge [
        color="{BLUE}"
        penwidth=1.4
        fontname="Helvetica"
        fontsize=9
    ];


    subgraph cluster_source {{
        label=<
            <b>Source Files</b><br/>
            <font point-size="9">Datasets/</font>
        >;

        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        oi [
            label="order_items.csv\\n600,000 rows · Event"
            fillcolor="{LIGHT}"
            color="{BLUE}"
        ];

        ord [
            label="orders.csv\\n300,000 rows · Event"
            fillcolor="{LIGHT}"
            color="{BLUE}"
        ];

        st [
            label="stores.csv\\n100 rows · Entity"
            fillcolor="{LIGHT}"
            color="{BLUE}"
        ];

        pr [
            label="products.csv\\n10,000 rows · Entity"
            fillcolor="{LIGHT}"
            color="{BLUE}"
        ];

        other [
            label="customers, employees,\\nsuppliers, categories,\\npromotions, payments,\\nshipments, returns"
            fillcolor="#F2F2F2"
            color="{GREY}"
            fontsize=9
        ];
    }}


    subgraph cluster_ingest {{
        label=<
            <b>Ingestion</b><br/>
            <font point-size="9">session1_parallel_compute/</font>
        >;

        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        profile [
            label="profile_files.py\\neligibility + inventory\\n(11 FK checks)"
            fillcolor="#FFF2CC"
            color="{AMBER}"
        ];

        join [
            label="load_and_join.py\\nbroadcast + shuffle joins\\n600,000 -> 600,000"
            fillcolor="#FFF2CC"
            color="{AMBER}"
        ];
    }}


    subgraph cluster_compute {{
        label=<
            <b>Parallel Compute</b><br/>
            <font point-size="9">PySpark · local mode</font>
        >;

        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        repart [
            label="repartition(4, 'category_id')\\nbounded parallelism"
            fillcolor="#E2EFDA"
            color="{GREEN}"
        ];

        agg [
            label="parallel_compute.py\\ngroupBy(category_id)\\ncount · sum · avg"
            fillcolor="#E2EFDA"
            color="{GREEN}"
        ];

        base [
            label="sequential_baseline.py\\npandas reference"
            fillcolor="#FCE4D6"
            color="{AMBER}"
        ];

        valid [
            label="validate()\\n30 groups · delta < 1e-6"
            fillcolor="#FCE4D6"
            color="{AMBER}"
        ];
    }}


    subgraph cluster_out {{
        label=<
            <b>Session 1 Output</b><br/>
            <font point-size="9">results/</font>
        >;

        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        parquet [
            label="category_revenue.parquet\\n30 rows · category_id,\\nline_count,\\nrevenue_total, revenue_mean"
            fillcolor="{LIGHT}"
            color="{NAVY}"
            penwidth=2.2
        ];

        bench [
            label="session1_benchmark.csv"
            fillcolor="white"
            color="{GREY}"
        ];

        parts [
            label="partition_sizes.csv"
            fillcolor="white"
            color="{GREY}"
        ];
    }}


    s2 [
        label="Session 2\\n(reconciles against\\nbaseline_result.csv)"
        shape=box
        style="rounded,dashed,filled"
        fillcolor="white"
        color="{NAVY}"
        fontsize=10
    ];


    oi -> profile [style=dotted];
    ord -> profile [style=dotted];
    st -> profile [style=dotted];
    pr -> profile [style=dotted];
    other -> profile [style=dotted];

    profile -> join [label="eligible"];
    join -> repart;
    join -> base [label="same joined data"];

    repart -> agg;

    agg -> valid;
    base -> valid [label="reference"];

    valid -> parquet [
        label="passed"
        color="{GREEN}"
        penwidth=2.0
    ];

    agg -> bench [style=dotted];
    repart -> parts [style=dotted];

    parquet -> s2 [
        style=dashed
        color="{NAVY}"
        penwidth=1.8
    ];
}}
"""


# ---------------------------------------------------------------------------
# 3. Session 2 entity / event model
# ---------------------------------------------------------------------------

SESSION2_ENTITY = f"""
digraph Session2EntityModel {{
    rankdir=TB;
    bgcolor="white";
    splines=polyline;
    nodesep=0.6;
    ranksep=0.85;
    fontname="Helvetica";
    labelloc="t";
    fontsize=17;

    label=<
        <b>Retail-MonFlow — Session 2 Event &amp; Log Model</b><br/>
        <font point-size="11">
            topic order_item.recorded ·
            4 partitions keyed on category_id ·
            3 independent consumer groups
        </font>
    >;

    node [
        shape=plaintext
        fontname="Helvetica"
    ];

    edge [
        color="{BLUE}"
        fontname="Helvetica"
        fontsize=9
        penwidth=1.4
    ];


    subgraph cluster_source {{
        label=<<font point-size="10"><b>Session 1 source tables (joined)</b></font>>;
        fontsize=10;
        color="{GREY}";
        style=dashed;

        OrderItem [label=<
            <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
            <tr><td bgcolor="{LIGHT}"><b>OrderItem</b></td></tr>
            <tr><td align="left">order_item_id «PK»</td></tr>
            <tr><td align="left">order_id, product_id «FK»</td></tr>
            <tr><td align="left">qty, unit_price</td></tr>
            </table>
        >];

        Order [label=<
            <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
            <tr><td bgcolor="{LIGHT}"><b>Order</b></td></tr>
            <tr><td align="left">order_id «PK»</td></tr>
            <tr><td align="left">store_id «FK»</td></tr>
            <tr><td align="left">order_date «eventTime»</td></tr>
            </table>
        >];

        Store [label=<
            <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
            <tr><td bgcolor="{LIGHT}"><b>Store</b></td></tr>
            <tr><td align="left">store_id «PK»</td></tr>
            <tr><td align="left">city</td></tr>
            </table>
        >];

        Product [label=<
            <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
            <tr><td bgcolor="{LIGHT}"><b>Product</b></td></tr>
            <tr><td align="left">product_id «PK»</td></tr>
            <tr>
                <td align="left" bgcolor="#FFF2CC">
                    category_id «FK» <b>«partitionKey»</b>
                </td>
            </tr>
            </table>
        >];
    }}


    OrderItemRecorded [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="#FFF2CC">
                <b>order_item.recorded</b> «event»<br/>
                <font point-size="9">joined line item · one per OrderItem row</font>
            </td>
        </tr>
        <tr><td align="left"><b>event_id : String «PK»</b></td></tr>
        <tr><td align="left">order_item_id, order_id, product_id : Int</td></tr>
        <tr>
            <td align="left" bgcolor="#FFF2CC">
                category_id : Int <b>«partitionKey»</b>
            </td>
        </tr>
        <tr><td align="left">store_id : Int, store_city : String</td></tr>
        <tr><td align="left">qty : Int, unit_price : Float</td></tr>
        <tr>
            <td align="left" bgcolor="#E2EFDA">
                amount : Float <b>«metric» = qty * unit_price</b>
            </td>
        </tr>
        <tr>
            <td align="left" bgcolor="#E2EFDA">
                order_date : Date <b>«eventTime»</b>
            </td>
        </tr>
        <tr><td align="left">schema_version : String</td></tr>
        </table>
    >];


    Partition [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>Partition</b><br/>
                <font point-size="9">stream_log/partition-N.jsonl · 4 files</font>
            </td>
        </tr>
        <tr><td align="left"><b>partition_index : Int «PK» (0..3)</b></td></tr>
        <tr><td align="left">routing : md5(category_id) mod 4</td></tr>
        <tr><td align="left">append_only log of events, in event-time order</td></tr>
        </table>
    >];


    ConsumerGroup [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="{LIGHT}">
                <b>ConsumerGroup</b><br/>
                <font point-size="9">revenue-projector · audit-writer · high-value-alerter</font>
            </td>
        </tr>
        <tr><td align="left"><b>group_name : String «PK»</b></td></tr>
        <tr><td align="left">reads all 4 partitions independently</td></tr>
        </table>
    >];


    Offset [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="5">
        <tr>
            <td bgcolor="#F2F2F2">
                <b>Offset</b><br/>
                <font point-size="9">stream_log/offsets/&lt;group&gt;.json</font>
            </td>
        </tr>
        <tr><td align="left"><b>group_name «PK, FK»</b></td></tr>
        <tr><td align="left"><b>partition_index «PK, FK»</b></td></tr>
        <tr><td align="left">committed_position : Int (every 5 batches of 1,000)</td></tr>
        </table>
    >];


    StreamedCategoryRevenue [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr><td bgcolor="{LIGHT}"><b>streamed_category_revenue</b><br/>
            <font point-size="9">written by revenue-projector · 30 rows</font></td></tr>
        <tr><td align="left">category_id «PK»</td></tr>
        <tr><td align="left">line_count, revenue_total, revenue_mean</td></tr>
        </table>
    >];

    AuditLog [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr><td bgcolor="{LIGHT}"><b>audit_log.jsonl</b><br/>
            <font point-size="9">written by audit-writer · 1 line / event</font></td></tr>
        <tr><td align="left">event_id, order_item_id</td></tr>
        <tr><td align="left">category_id, amount</td></tr>
        </table>
    >];

    HighValueAlerts [label=<
        <table border="0" cellborder="1" cellspacing="0" cellpadding="4">
        <tr><td bgcolor="{LIGHT}"><b>high_value_alerts</b><br/>
            <font point-size="9">written by high-value-alerter · amount &gt;= 15,000</font></td></tr>
        <tr><td align="left">event_id, order_item_id, category_id</td></tr>
        <tr><td align="left">qty, unit_price, amount</td></tr>
        </table>
    >];


    OrderItem -> OrderItemRecorded [label="enriches" penwidth=2.0 color="{AMBER}" arrowhead=none];
    Order -> OrderItemRecorded [label="join order_id" style=dashed arrowhead=none];
    Store -> OrderItemRecorded [label="join store_id" style=dashed arrowhead=none];
    Product -> OrderItemRecorded [label="join product_id" penwidth=2.0 color="{AMBER}" arrowhead=none];

    OrderItemRecorded -> Partition [
        taillabel="1"
        headlabel="1"
        label="partition_of(category_id)"
        penwidth=2.2
        color="{NAVY}"
    ];

    Partition -> ConsumerGroup [
        taillabel="1"
        headlabel="0..*"
        label="read (non-destructive)"
        style=dotted
    ];

    ConsumerGroup -> Offset [
        taillabel="1"
        headlabel="4"      // one committed offset per partition, always all 4
        label="commits"
    ];

    Partition -> Offset [
        taillabel="1"
        headlabel="0..*"
        style=dotted
        arrowhead=none
    ];

    ConsumerGroup -> StreamedCategoryRevenue [style=dashed color="{GREEN}" label="revenue-projector"];
    ConsumerGroup -> AuditLog [style=dashed color="{GREY}" label="audit-writer"];
    ConsumerGroup -> HighValueAlerts [style=dashed color="{AMBER}" label="high-value-alerter"];


    note1 [
        shape=note
        style=filled
        fillcolor="#FFF9E6"
        color="{AMBER}"
        fontsize=10
        align=left
        label=<
            <b>Same partition key as Session 1: category_id</b><br align="left"/>
            30 values onto 4 partitions - skew measured,<br align="left"/>
            not assumed (3.66 : 1 on the full 600,000-row run).<br align="left"/>
            <br align="left"/>
            <b>Offset is a composite key</b><br align="left"/>
            (group_name, partition_index): group isolation<br align="left"/>
            means each group's progress cannot hide<br align="left"/>
            events from another group.
        >
    ];

    note1 -> Offset [style=invis];
    {{ rank=same; note1; Offset; }}
}}
"""


# ---------------------------------------------------------------------------
# 4. Session 2 architecture
# ---------------------------------------------------------------------------

SESSION2_ARCHITECTURE = f"""
digraph Session2Architecture {{
    rankdir=LR;
    bgcolor="white";
    compound=true;
    nodesep=0.35;
    ranksep=0.8;
    fontname="Helvetica";
    labelloc="t";
    fontsize=17;

    label=<
        <b>Retail-MonFlow — Session 2 Event-Streaming Console</b><br/>
        <font point-size="11">
            actual repository file names ·
            topic order_item.recorded · 4 partitions · at-least-once delivery
        </font>
    >;

    node [
        shape=box
        style="rounded,filled"
        fontname="Helvetica"
        fontsize=10
        penwidth=1.3
        margin="0.16,0.10"
    ];

    edge [
        color="{BLUE}"
        penwidth=1.4
        fontname="Helvetica"
        fontsize=9
    ];


    s1 [
        label="Session 1\\n(category_revenue.parquet,\\nbaseline_result.csv)"
        shape=box
        style="rounded,dashed,filled"
        fillcolor="white"
        color="{NAVY}"
        fontsize=10
    ];


    subgraph cluster_source {{
        label=<
            <b>Source Files</b><br/>
            <font point-size="9">Datasets/ (copied or symlinked from Session 1)</font>
        >;
        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        oi [label="order_items.csv" fillcolor="{LIGHT}" color="{BLUE}"];
        ord [label="orders.csv" fillcolor="{LIGHT}" color="{BLUE}"];
        st [label="stores.csv" fillcolor="{LIGHT}" color="{BLUE}"];
        pr [label="products.csv" fillcolor="{LIGHT}" color="{BLUE}"];
    }}


    subgraph cluster_produce {{
        label=<
            <b>Producer</b><br/>
            <font point-size="9">stream_core.py - load_events() + produce()</font>
        >;
        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        load [
            label="load_events()\\njoin order_items|>orders|>stores|>products\\namount = qty * unit_price"
            fillcolor="#FFF2CC"
            color="{AMBER}"
        ];

        route [
            label="partition_of()\\nmd5(category_id) mod 4\\nstable key routing"
            fillcolor="#FFF2CC"
            color="{AMBER}"
        ];
    }}


    subgraph cluster_log {{
        label=<
            <b>Durable Log</b><br/>
            <font point-size="9">stream_log/ · append-only JSONL</font>
        >;
        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        p0 [label="partition-0.jsonl" fillcolor="{LIGHT}" color="{NAVY}"];
        p1 [label="partition-1.jsonl" fillcolor="{LIGHT}" color="{NAVY}"];
        p2 [label="partition-2.jsonl" fillcolor="{LIGHT}" color="{NAVY}"];
        p3 [label="partition-3.jsonl" fillcolor="{LIGHT}" color="{NAVY}"];
        offsets [
            label="offsets/\\n<group>.json\\ncommitted every 5 batches"
            fillcolor="white"
            color="{GREY}"
        ];
    }}


    subgraph cluster_consume {{
        label=<
            <b>Consumer Groups</b><br/>
            <font point-size="9">independent, isolated offsets - read is non-destructive</font>
        >;
        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        revproj [
            label="revenue-projector\\nincremental category revenue"
            fillcolor="#E2EFDA"
            color="{GREEN}"
        ];

        audit [
            label="audit-writer\\nappend-only audit trail\\n(I/O bound, slowest)"
            fillcolor="#E2EFDA"
            color="{GREEN}"
        ];

        alert [
            label="high-value-alerter\\nflags amount >= 15,000"
            fillcolor="#E2EFDA"
            color="{GREEN}"
        ];
    }}


    subgraph cluster_out {{
        label=<
            <b>Session 2 Results</b><br/>
            <font point-size="9">results/</font>
        >;
        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        rev_csv [label="streamed_category_revenue.csv" fillcolor="{LIGHT}" color="{NAVY}"];
        audit_log [label="audit_log.jsonl" fillcolor="white" color="{GREY}"];
        alert_csv [label="high_value_alerts.csv" fillcolor="white" color="{GREY}"];
        recon [
            label="reconcile()\\nbatch vs stream\\ndiff 0.0, tol 1e-6"
            fillcolor="{LIGHT}"
            color="{NAVY}"
            penwidth=2.2
        ];
    }}


    subgraph cluster_resilience {{
        label=<
            <b>Failure, Recovery &amp; Replay</b><br/>
            <font point-size="9">demonstrated, not asserted in prose</font>
        >;
        fontsize=11;
        color="{GREY}";
        style=dashed;
        fontname="Helvetica";

        crash [
            label="failure_and_recovery()\\ncrash after N events,\\nresume from committed offset"
            fillcolor="#FCE4D6"
            color="{AMBER}"
        ];

        replay [
            label="replay()\\nnew group from offset 0,\\npartial replay by date"
            fillcolor="#FCE4D6"
            color="{AMBER}"
        ];
    }}


    oi -> load [style=dotted];
    ord -> load [style=dotted];
    st -> load [style=dotted];
    pr -> load [style=dotted];

    load -> route [label="joined events"];
    route -> p0;
    route -> p1;
    route -> p2;
    route -> p3;

    p0 -> revproj [style=dotted];
    p1 -> revproj [style=dotted];
    p2 -> revproj [style=dotted];
    p3 -> revproj [style=dotted];

    p0 -> audit [style=dotted];
    p1 -> audit [style=dotted];
    p2 -> audit [style=dotted];
    p3 -> audit [style=dotted];

    p0 -> alert [style=dotted];
    p1 -> alert [style=dotted];
    p2 -> alert [style=dotted];
    p3 -> alert [style=dotted];

    revproj -> offsets [style=dashed arrowhead=none];
    audit -> offsets [style=dashed arrowhead=none];
    alert -> offsets [style=dashed arrowhead=none];

    revproj -> rev_csv;
    audit -> audit_log;
    alert -> alert_csv;

    rev_csv -> recon;
    s1 -> recon [style=dashed color="{NAVY}" label="baseline_result.csv"];

    audit -> crash [style=dashed color="{AMBER}" label="crash + resume demo"];
    revproj -> replay [style=dashed color="{AMBER}" label="rewind + partial-date demo"];
}}
"""


# ---------------------------------------------------------------------------
# Graphviz renderer
# ---------------------------------------------------------------------------

def find_graphviz() -> str:
    """
    Find the Graphviz 'dot' executable.

    Returns:
        Full path to dot.exe.

    Raises:
        RuntimeError if Graphviz cannot be found.
    """

    dot = shutil.which("dot")

    if dot:
        return dot

    # Common Windows installation locations.
    candidates = [
        Path(r"C:\Program Files\Graphviz\bin\dot.exe"),
        Path(r"C:\Program Files (x86)\Graphviz\bin\dot.exe"),
        Path(r"C:\Program Files\Graphviz2.38\bin\dot.exe"),
        Path(r"C:\Program Files (x86)\Graphviz2.38\bin\dot.exe"),
    ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    raise RuntimeError(
        "Graphviz 'dot.exe' was not found.\n"
        "Install Graphviz or add its bin folder to PATH.\n"
        "Test with: dot -V"
    )


def render(dot_source: str, out_png: Path) -> None:
    """
    Render a Graphviz DOT document into a PNG file.
    """

    dot = find_graphviz()

    dot_file = out_png.with_suffix(".dot")

    # Always use UTF-8 because the entity diagram contains
    # Unicode characters such as «PK», «FK», and ·.
    dot_file.write_text(
        dot_source,
        encoding="utf-8",
        newline="\n",
    )

    print(f"Rendering: {dot_file.name}")
    print(f"Graphviz : {dot}")

    try:
        result = subprocess.run(
            [
                dot,
                "-Tpng",
                "-Gdpi=150",
                str(dot_file),
                "-o",
                str(out_png),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        if result.returncode != 0:
            print("\nGraphviz failed.")
            print("--------------------------------------------------")

            if result.stdout:
                print("STDOUT:")
                print(result.stdout)

            if result.stderr:
                print("STDERR:")
                print(result.stderr)

            print("--------------------------------------------------")
            print(f"The DOT file was preserved for inspection:")
            print(dot_file)

            raise RuntimeError(
                f"Graphviz returned exit status {result.returncode}."
            )

        if not out_png.exists():
            raise RuntimeError(
                f"Graphviz reported success, but output was not created:\n"
                f"{out_png}"
            )

        print(f"Wrote {out_png}")

    finally:
        # Only delete the DOT file after successful rendering.
        if out_png.exists() and dot_file.exists():
            dot_file.unlink()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 72)
    print("SESSION 1 & 2 - RENDER DIAGRAMS")
    print("=" * 72)

    try:
        render(
            ENTITY,
            DOCS / "entity-model-session1.png",
        )

        render(
            ARCHITECTURE,
            ARCH / "architecture-session1.png",
        )

        render(
            SESSION2_ENTITY,
            DOCS / "entity-model-session2.png",
        )

        render(
            SESSION2_ARCHITECTURE,
            ARCH / "architecture-session2.png",
        )

    except Exception as exc:
        print()
        print("=" * 72)
        print("ERROR")
        print("=" * 72)
        print(str(exc))
        return 1

    print()
    print("=" * 72)
    print("DIAGRAM RENDERING COMPLETE")
    print("=" * 72)

    return 0


if __name__ == "__main__":
    sys.exit(main())