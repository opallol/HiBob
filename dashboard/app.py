"""
DeepSeek KMS Dashboard - FastAPI backend.

Menyajikan API JSON di atas database ddac2026:
  - /api/summary           KPI ringkas (nodes, edges, anomali, coherence, K/L)
  - /api/kl-list           daftar K/L untuk filter
  - /api/anomalies         anomali alignment DIPA vs RPJMN/RKP (+verdict TreasurAI)
  - /api/coherence         anomali struktur internal DIPA (jenis komponen)
  - /api/kl-assignments    penugasan KP -> K/L pelaksana
  - /api/graph             knowledge graph PN -> PP -> KP
Frontend statis disajikan di "/".
"""
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

# Reuse the shared DB/config module from scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from common.db import get_connection  # noqa: E402

from fastapi import FastAPI, Query  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

app = FastAPI(title="DeepSeek KMS Dashboard")
STATIC_DIR = Path(__file__).resolve().parent / "static"


def _jsonable(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def query(sql, params=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or ())
        cols = [d[0] for d in cur.description]
        out = []
        for row in cur.fetchall():
            out.append({c: _jsonable(v) for c, v in zip(cols, row)})
        return out
    finally:
        conn.close()


@app.get("/api/summary")
def summary():
    nodes = query("SELECT node_type, COUNT(*) AS n FROM deepseek_policy_nodes GROUP BY node_type")
    edges = query("SELECT COUNT(*) AS n FROM deepseek_policy_edges")[0]["n"]
    anomaly_types = query(
        """SELECT anomaly_type, COUNT(*) AS n, CAST(SUM(total_pagu) AS DOUBLE) AS pagu
           FROM ddac_anomaly_2026 GROUP BY anomaly_type ORDER BY n DESC""")
    verdicts = query(
        """SELECT treasurai_verdict AS verdict, COUNT(*) AS n, CAST(SUM(total_pagu) AS DOUBLE) AS pagu
           FROM ddac_anomaly_2026 WHERE treasurai_verdict IS NOT NULL
           GROUP BY treasurai_verdict ORDER BY n DESC""")
    coherence = query(
        """SELECT jenis_anomaly, COUNT(*) AS n, CAST(SUM(total_pagu) AS DOUBLE) AS pagu
           FROM ddac_coherence_2026 GROUP BY jenis_anomaly ORDER BY n DESC""")
    kl = query("SELECT COUNT(*) AS n FROM deepseek_policy_kl_assignments")[0]["n"]
    return {
        "nodes": {r["node_type"]: r["n"] for r in nodes},
        "edges": edges,
        "anomaly_types": anomaly_types,
        "verdicts": verdicts,
        "coherence": coherence,
        "kl_assignments": kl,
    }


@app.get("/api/kl-list")
def kl_list():
    return query(
        """SELECT DISTINCT kementerian_kode AS kode, kementerian_uraian AS nama
           FROM ddac_anomaly_2026 WHERE kementerian_kode IS NOT NULL
           ORDER BY kementerian_kode""")


@app.get("/api/anomalies")
def anomalies(
    kl: str = Query(default=""),
    verdict: str = Query(default=""),
    status: str = Query(default=""),
    atype: str = Query(default=""),
    min_priority: float = Query(default=0.0),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    where, params = ["1=1"], []
    if kl:
        where.append("kementerian_kode = %s"); params.append(kl)
    if verdict:
        where.append("treasurai_verdict = %s"); params.append(verdict)
    if status:
        where.append("review_status = %s"); params.append(status)
    if atype:
        where.append("anomaly_type = %s"); params.append(atype)
    if min_priority:
        where.append("review_priority >= %s"); params.append(min_priority)
    sql = (
        """SELECT id, kementerian_kode, kementerian_uraian, program_kode,
                  CAST(total_pagu AS DOUBLE) AS total_pagu, alignment_score,
                  anomaly_type, anomaly_score, review_priority,
                  treasurai_verdict, review_status,
                  best_match_code, best_match_name, llm_reasoning
           FROM ddac_anomaly_2026 WHERE """ + " AND ".join(where) +
        " ORDER BY review_priority DESC LIMIT %s OFFSET %s")
    params += [limit, offset]
    return query(sql, params)


@app.get("/api/coherence")
def coherence(
    kl: str = Query(default=""),
    jenis: str = Query(default=""),
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
):
    where = ["jenis_anomaly IN ('pendukung_dominan','utama_kecil')"]
    params = []
    if jenis:
        where = ["jenis_anomaly = %s"]; params = [jenis]
    if kl:
        where.append("kementerian_kode = %s"); params.append(kl)
    sql = (
        """SELECT id, kementerian_kode, kementerian_uraian, program_uraian,
                  outputkro_uraian, komponen_uraian, jenis_komponen, jenis_anomaly,
                  jenis_anomaly_score, CAST(total_pagu AS DOUBLE) AS total_pagu
           FROM ddac_coherence_2026 WHERE """ + " AND ".join(where) +
        " ORDER BY total_pagu DESC LIMIT %s OFFSET %s")
    params += [limit, offset]
    return query(sql, params)


@app.get("/api/kl-assignments")
def kl_assignments(
    kl: str = Query(default=""),
    limit: int = Query(default=200, le=2000),
):
    where, params = ["1=1"], []
    if kl:
        where.append("a.kddept = %s"); params.append(kl)
    sql = (
        """SELECT a.id, n.node_code, n.node_name, a.kddept,
                  a.nmdept_normalized, a.role, a.confidence, a.source_page, a.document_id
           FROM deepseek_policy_kl_assignments a
           JOIN deepseek_policy_nodes n ON a.node_id = n.id
           WHERE """ + " AND ".join(where) +
        " ORDER BY n.node_code LIMIT %s")
    params.append(limit)
    return query(sql, params)


@app.get("/api/graph")
def graph(
    source_type: str = Query(default="RPJMN"),
    include_kp: int = Query(default=0),
    pn: str = Query(default=""),
):
    node_where = ["source_type = %s"]
    params = [source_type]
    types = ["PN", "PP"] + (["KP"] if include_kp else [])
    node_where.append("node_type IN (%s)" % ",".join(["%s"] * len(types)))
    params += types
    if pn:
        # restrict to one PN subtree by code prefix (PN.PP.KP share prefix)
        node_where.append("node_code LIKE %s")
        params.append(pn + "%")
    nodes = query(
        """SELECT id, node_type, node_code, node_name FROM deepseek_policy_nodes
           WHERE """ + " AND ".join(node_where) + " LIMIT 2000", params)
    ids = [n["id"] for n in nodes]
    edges = []
    if ids:
        ph = ",".join(["%s"] * len(ids))
        edges = query(
            """SELECT parent_node_id AS source, child_node_id AS target, edge_type
               FROM deepseek_policy_edges
               WHERE parent_node_id IN (%s) AND child_node_id IN (%s)""" % (ph, ph),
            ids + ids)
    return {"nodes": nodes, "edges": edges}


app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
