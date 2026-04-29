# This method uses pandas.
# Pandas is a powerful data manipulation library in Python that provides data structures and functions for working with structured data. It is commonly used for data analysis, cleaning, and transformation tasks. In this code, we use pandas to create DataFrames from the results of Neo4j queries and then export those DataFrames to Parquet files for efficient storage and further analysis.

import pandas as pd
from neo4j import GraphDatabase

URI = "neo4j://127.0.0.1:7687"
AUTH = ("your-username", "your-password")  # Replace with your Neo4j credentials
DATABASE = "your-database-name"  # Replace with your Neo4j database name

driver = GraphDatabase.driver(URI, auth=AUTH)

queries = {
"fact_transaction": """
    MATCH (src:Account)-[t:TRANSACTION]->(dst:Account)
    RETURN
        elementId(t)                             AS transaction_sk,
        elementId(src)                           AS account_src_fk,
        elementId(dst)                           AS account_dst_fk,
        src.community_id                         AS ring_fk,
        t.step                                   AS step_fk,
        t.amount                                 AS amount,
        t.type                                   AS type,
        COALESCE(t.cashout_pair_flag, false)     AS cashout_pair_flag,
        CASE WHEN src.flagged = true
                  OR dst.flagged = true
             THEN true ELSE false END            AS is_flagged_volume
""",
"dim_account": """
    MATCH (a:Account)
    RETURN
        elementId(a)                                             AS account_sk,
        a.id                                                     AS account_id,
        COALESCE(a.risk_score, 0)                                AS risk_score,
        a.community_id                                           AS community_id,
        COALESCE(a.flagged, false)                               AS flagged,
        COALESCE(a.unusual_fanout_flag, false)                   AS unusual_fanout_flag,
        COALESCE(a.unusual_fanout_step_flag, false)              AS unusual_fanout_step_flag,
        COALESCE(a.unusual_fanin_flag, false)                    AS unusual_fanin_flag,
        COALESCE(a.unusual_fanin_step_flag, false)               AS unusual_fanin_step_flag,
        COALESCE(a.drain_flag, false)                            AS drain_flag,
        COALESCE(a.transfer_cashout_flag, false)                 AS transfer_cashout_flag,
        COALESCE(a.ring_flag, false)                             AS ring_flag,
        COALESCE(a.cycle_flag, false)                            AS cycle_flag,
        COALESCE(a.guilt_by_association_flag, false)             AS guilt_by_association_flag,
        COALESCE(a.node_similarity_flag, false)                  AS node_similarity_flag
""",
    "dim_ring": """
        MATCH (src:Account)-[t:TRANSACTION]->(dst:Account)
        WHERE src.community_id IS NOT NULL
          AND src.community_id = dst.community_id
        WITH src.community_id AS community_id,
             count(DISTINCT src) AS member_count,
             sum(t.amount) AS total_internal_volume
        RETURN
            community_id                         AS ring_sk,
            community_id                         AS community_id,
            member_count                         AS member_count,
            total_internal_volume                AS total_internal_volume
    """,
    "dim_step": """
        MATCH ()-[t:TRANSACTION]->()
        WITH DISTINCT t.step AS step
        RETURN
            step AS step_sk,
            step AS step
        ORDER BY step
    """
}

with driver.session(database=DATABASE) as session:
    for table_name, query in queries.items():
        print(f"Exporting {table_name}...")
        result = session.run(query)
        df = pd.DataFrame([r.data() for r in result])
        df.to_parquet(f"{table_name}.parquet", index=False)
        print(f"  -> {len(df)} rows written to {table_name}.parquet")

driver.close()
print("Export complete.")