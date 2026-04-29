# Graph-Based Fraud Detection

A fraud detection pipeline built on the [PaySim synthetic financial dataset](https://www.kaggle.com/datasets/ealaxi/paysim1). Transactions are modeled as a graph in Neo4j, fraud signals are detected using Cypher queries and GDS algorithms, results are exported to a star schema via Python, and findings are presented through a PowerBI dashboard.

---

## Tech Stack

- **Neo4j** — graph database and detection engine
- **Neo4j Graph Data Science (GDS)** — degree centrality, Louvain community detection, node similarity
- **Python** — data export pipeline (Neo4j driver + pandas/PySpark + pyarrow)
- **PowerBI Desktop** — reporting and dashboard
- **PaySim** — synthetic financial transaction dataset

---

## Setup

### Prerequisites
- Neo4j Desktop with GDS plugin installed
- Python 3.9+
- PowerBI Desktop

### Install Python dependencies
```bash
pip install -r requirements.txt
```

### Neo4j
1. Create a new database in Neo4j Desktop
2. Install the Graph Data Science plugin via the Plugins tab
3. Load the PaySim dataset — model accounts as nodes and transactions as relationships
4. Run the detection queries (see Detection Signals below)

### Export
Update the connection details in `export.py`:
```python
URI = "neo4j://127.0.0.1:7687"
AUTH = ("your_username", "your_password")
DATABASE = "your_database_name"
```

Then run:
```bash
py export.py
```

This generates four Parquet files: `fact_transaction.parquet`, `dim_account.parquet`, `dim_ring.parquet`, `dim_step.parquet`.

### PowerBI
1. Load each Parquet file via **Get Data → Parquet**
2. Set up relationships in Model view:
   - `fact_transactions[nameOrig]` → `dim_account[account_id]` (active)
   - `fact_transactions[step]` → `dim_step[step]` (active)
   - `fact_transactions[ring_fk]` → `dim_ring[community_id]` (active)
3. Open `dashboard.pbix`

---

## Detection Signals

Fraud signals are written back as node and relationship properties in Neo4j. See CypherQueries.md for full explanation and actual queries. 

### First-Pass Signals
| Signal | Property | Method |
|---|---|---|
| Unusual fan-out | `unusual_fanout_flag` | GDS degree (NATURAL) + step-level Cypher |
| Unusual fan-in | `unusual_fanin_flag` | GDS degree (REVERSE) + step-level Cypher |
| Drain behavior | `drain_flag` | Cypher pattern match on balance drop |
| Transfer → Cash-out | `transfer_cashout_flag` | Cypher pattern match on transaction type sequence |
| Dense community (ring) | `ring_flag` | Louvain community detection + internal volume ratio |
| Cycles | `cycle_flag` | Variable-length Cypher path matching |

### Second-Pass Signals
| Signal | Property | Method |
|---|---|---|
| Guilt by association | `guilt_by_association_flag` | Cypher — unflagged accounts with 2+ flagged neighbors |
| Node similarity | `node_similarity_flag` | GDS node similarity (Jaccard) |

### Risk Score
Each account receives a `risk_score` on a 0–100 scale:

```
risk_score =
    (10 × unusual_fanout_flag) +
    (10 × unusual_fanin_flag) +
    (15 × drain_flag) +
    (15 × transfer_cashout_flag) +
    (20 × ring_flag) +
    (10 × cycle_flag) +
    (10 × guilt_by_association_flag) +
    (10 × node_similarity_flag)
```

---

## Star Schema

See `starschema.png` for the full schema design. Summary:
1. Account Schema (ACCOUNT_SCHEMA)
Role: Dimension Table (dim_account).
Fields: account_id (plus space for derived properties like fraud_score).
2. Transaction Batch Schema (TRANSACTION_BATCH_SCHEMA)
Role: Raw Fact Table data.
Fields: Includes the cursor (for Neo4j pagination) and all the raw transaction metrics like amount, oldbalanceOrg, etc.
Note: The cursor is dropped before the final write, but the schema is required to materialize the batch from Neo4j.
3. Transaction Type Schema (Defined in write_dim_transaction_type)
Role: Dimension Table (dim_transaction_type).
Fields: type_key and type_name.
This maps the string types (like "PAYMENT" or "TRANSFER") to integer IDs.
4. Date Schema (Defined in write_dim_date)
Role: Dimension Table (dim_date).
Fields: date_key, datetime, date, hour, and day_of_week.
This is used to expand the PaySim "step" (hours) into human-readable time attributes.

---

## Dashboard

The PowerBI dashboard answers the following questions:

- How many transactions, accounts, flagged accounts, and rings were detected?
- What is the total flagged transaction volume?
- How did flagged volume change over time?
- Which transaction types have the highest fraud rate?
- Which accounts have the highest risk scores?
- Which rings moved the most money internally?

---

## Known Limitations

- **Node similarity** on the full PaySim graph exceeds available memory on a local machine (~2GB required). The signal was partially implemented on the flagged-account subgraph only.
- **Louvain community detection** produces near-singleton communities on PaySim due to the sparse transaction graph (median out-degree = 1). Ring detection was supplemented with a Cypher-based internal volume ratio approach.
- **Cycles** were not found in the PaySim dataset — the synthetic transaction generator does not produce circular money flows.

---

## Dataset

[PaySim — Synthetic Financial Dataset for Fraud Detection](https://www.kaggle.com/datasets/ealaxi/paysim1)

PaySim simulates mobile money transactions based on a sample of real transactions. It is designed for fraud detection research and contains labeled fraudulent transactions.
