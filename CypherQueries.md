Here are my Cypher queries. Also, I went ahead and sent both of you my parquet files 

🧠 Cypher Query Library (Formatted)
🔍 Basic Exploration / Debugging
Transactions Over 100,000
MATCH (a:Account)-[t:TRANSACTION]->(b:Account)
WHERE t.high_value_flag = 1
RETURN t, a, b
LIMIT 100
Check Indexes
SHOW INDEXES;
List Property Keys
CALL db.propertyKeys;
Relationship Types
CALL db.relationshipTypes();
Count Accounts
MATCH (n:Account)
RETURN count(n);
Sample Relationships
MATCH ()-[r]->()
RETURN r
LIMIT 25;
Sample Accounts
MATCH (n:Account)
RETURN n
LIMIT 25;
🚨 #1 Unusual Fan-Out
Step 1 — Compute Out Degree
CALL gds.degree.write('transactionGraph', {
  writeProperty: 'outDegree',
  orientation: 'NATURAL'
})
YIELD nodePropertiesWritten, computeMillis;
Step 2 — Flag Statistical Outliers
MATCH (a:Account)
WITH avg(a.outDegree) AS mean,
     stdev(a.outDegree) AS sd,
     percentileCont(a.outDegree, 0.99) AS p99

MATCH (a:Account)
WHERE a.outDegree > p99 OR a.outDegree > (mean + 3 * sd)
SET a.unusual_fanout_flag = true;
Step 3 — Step-Based Fan-Out Spike
MATCH (a:Account)-[t:TRANSACTION]->(dest:Account)
WITH a, t.step AS step, count(DISTINCT dest) AS destCount
WITH a, max(destCount) AS maxDestsInAStep

WITH avg(maxDestsInAStep) AS mean,
     stdev(maxDestsInAStep) AS sd,
     percentileCont(maxDestsInAStep, 0.99) AS p99,
     collect({account: a, maxDests: maxDestsInAStep}) AS rows

UNWIND rows AS row
WITH row.account AS a,
     row.maxDests AS maxDests,
     mean, sd, p99
WHERE maxDests > p99 OR maxDests > (mean + 3 * sd)
SET a.unusual_fanout_step_flag = true;
Query Flagged Accounts
MATCH (a:Account)
WHERE a.unusual_fanout_flag = true
   OR a.unusual_fanout_step_flag = true
RETURN a.id, a.outDegree,
       a.unusual_fanout_flag,
       a.unusual_fanout_step_flag;
Visualization
MATCH (a:Account)-[t:TRANSACTION]->(dest:Account)
WHERE a.unusual_fanout_flag = true
   OR a.unusual_fanout_step_flag = true
RETURN a, t, dest;
📥 #2 Unusual Fan-In
Step 1 — Reverse Graph
CALL gds.graph.project(
  'transactionGraphReverse',
  'Account',
  { TRANSACTION: { orientation: 'REVERSE' } }
);
Step 2 — Compute In Degree
CALL gds.degree.write('transactionGraphReverse', {
  writeProperty: 'inDegree',
  orientation: 'REVERSE'
})
YIELD nodePropertiesWritten, computeMillis;
Step 3 — Flag Outliers
MATCH (a:Account)
WITH avg(a.inDegree) AS mean,
     stdev(a.inDegree) AS sd,
     percentileCont(a.inDegree, 0.99) AS p99

MATCH (a:Account)
WHERE a.inDegree > p99 OR a.inDegree > (mean + 3 * sd)
SET a.unusual_fanin_flag = true;
Optional Threshold (Simple Rule)
MATCH (a:Account)
WHERE a.inDegree > 2
SET a.unusual_fanin_flag = true;
Visualization
MATCH (src:Account)-[t:TRANSACTION]->(a:Account)
WHERE a.unusual_fanin_flag = true
   OR a.unusual_fanin_step_flag = true
RETURN src, t, a;
💧 #3 Drain Behavior
Step 1 — Detect Drain Pattern
MATCH (a:Account)-[t1:TRANSACTION]->(b:Account)-[t2:TRANSACTION]->(c:Account)
WHERE t2.step - t1.step <= 3
  AND t1.amount > 10000
  AND t2.newbalanceOrig < (t1.amount * 0.1)
SET b.drain_flag = true;
Step 2 — Visualize
MATCH (a:Account)-[t1:TRANSACTION]->(b:Account)-[t2:TRANSACTION]->(c:Account)
WHERE b.drain_flag = true
RETURN a, t1, b, t2, c;
💸 #4 Cash-Out Pattern
Step 1 — Flag Transfer → Cash-Out
MATCH (a:Account)-[t1:TRANSACTION]->(b:Account)-[t2:TRANSACTION]->(c:Account)
WHERE t1.type = 'TRANSFER'
  AND t2.type = 'CASH_OUT'
  AND t2.step - t1.step <= 2
  AND abs(t1.amount - t2.amount) / t1.amount < 0.1
SET t1.cashout_pair_flag = true,
    t2.cashout_pair_flag = true;
Step 2 — Visualize
MATCH (a:Account)-[t1:TRANSACTION]->(b:Account)-[t2:TRANSACTION]->(c:Account)
WHERE t1.cashout_pair_flag = true
  AND t2.cashout_pair_flag = true
RETURN a, t1, b, t2, c;
🧩 #5 Community Detection (Rings)
Project Graph
CALL gds.graph.project(
  'transactionGraph',
  'Account',
  { TRANSACTION: { orientation: 'NATURAL' } }
);
Run Louvain
CALL gds.louvain.write('transactionGraph', {
  writeProperty: 'community_id'
})
YIELD communityCount, modularity;
Detect Dense Communities
MATCH (a:Account)-[t:TRANSACTION]->(b:Account)
WITH a.community_id AS community,
     sum(CASE WHEN a.community_id = b.community_id THEN t.amount ELSE 0 END) AS internalVolume,
     sum(CASE WHEN a.community_id <> b.community_id THEN t.amount ELSE 0 END) AS externalVolume,
     count(DISTINCT a) AS memberCount
WHERE memberCount >= 3 AND memberCount <= 15
  AND internalVolume > 0
WITH community,
     internalVolume,
     externalVolume,
     memberCount,
     internalVolume / (internalVolume + externalVolume) AS internalRatio
WHERE internalRatio > 0.7
RETURN community, memberCount, internalVolume, externalVolume, internalRatio
ORDER BY internalVolume DESC;
🔁 #6 Cycles
MATCH path = (a:Account)-[rels:TRANSACTION*3..5]->(a)
WHERE all(i IN range(0, size(rels)-2)
      WHERE rels[i].step < rels[i+1].step)
  AND all(r IN rels WHERE r.amount > 1000)
RETURN path
LIMIT 50;
🧠 #7 Guilt by Association
Phase 1 — Consolidate Flags
MATCH (a:Account)
WHERE a.unusual_fanout_flag = true
   OR a.unusual_fanin_flag = true
   OR a.drain_flag = true
   OR a.ring_flag = true
   OR a.cycle_flag = true
SET a.flagged = true;
Phase 2 — Propagate Risk
MATCH (a:Account)-[:TRANSACTION]-(b:Account)
WHERE b.flagged = true
  AND (a.flagged IS NULL OR a.flagged = false)
WITH a, count(DISTINCT b) AS bad_neighbors
WHERE bad_neighbors >= 2
SET a.guilt_by_association_flag = true;
🔗 #8 Node Similarity
Project Graph
CALL gds.graph.project(
  'transactionGraphUndirected',
  'Account',
  { TRANSACTION: { orientation: 'UNDIRECTED' } }
);
Run Similarity
CALL gds.nodeSimilarity.write('flaggedOnly', {
  writeRelationshipType: 'SIMILAR_TO',
  writeProperty: 'similarity',
  topK: 5,
  similarityCutoff: 0.75
})
YIELD nodesCompared, relationshipsWritten;
📊 Risk Scoring
MATCH (a:Account)
CALL {
  WITH a
  SET a.risk_score =
    (10 * CASE WHEN a.unusual_fanout_flag THEN 1 ELSE 0 END) +
    (10 * CASE WHEN a.unusual_fanin_flag THEN 1 ELSE 0 END) +
    (15 * CASE WHEN a.drain_flag THEN 1 ELSE 0 END) +
    (15 * CASE WHEN a.transfer_cashout_flag THEN 1 ELSE 0 END) +
    (20 * CASE WHEN a.ring_flag THEN 1 ELSE 0 END) +
    (10 * CASE WHEN a.cycle_flag THEN 1 ELSE 0 END) +
    (10 * CASE WHEN a.guilt_by_association_flag THEN 1 ELSE 0 END) +
    (10 * CASE WHEN a.node_similarity_flag THEN 1 ELSE 0 END)
} IN TRANSACTIONS OF 10000 ROWS;
🏆 Top Risky Accounts
MATCH (a:Account)
WHERE a.risk_score > 0
RETURN a.id, a.risk_score
ORDER BY a.risk_score DESC
LIMIT 10;
📦 Export Queries (Star Schema)
fact_transaction
MATCH (src:Account)-[t:TRANSACTION]->(dst:Account)
RETURN
  id(t) AS transaction_sk,
  id(src) AS account_src_fk,
  id(dst) AS account_dst_fk,
  src.community_id AS ring_fk,
  t.step AS step_fk,
  t.amount AS amount,
  t.type AS type,
  COALESCE(t.cashout_pair_flag, false) AS cashout_pair_flag,
  CASE WHEN src.flagged OR dst.flagged THEN true ELSE false END AS is_flagged_volume;