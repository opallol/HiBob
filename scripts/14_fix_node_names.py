#!/usr/bin/env python3
"""
14_fix_node_names.py
--------------------
Repairs `deepseek_policy_nodes.node_name`, which currently stores a long
PDF-extraction blob (name + sasaran + indicators + numbers + ministry, avg ~250
chars) with words glued together where line-break spaces were lost
("Persdan", "massayang", "Pembelajarandengan").

Strategy (deterministic, reversible -> writes only to clean_node_name_ai):
  1. Truncate the blob to the real entity name: the prefix before the first
     sasaran marker " NN - " / " NN- " (e.g. " 01 - Terwujudnya...").
  2. Un-glue camel-case boundaries: "HakAsasi" -> "Hak Asasi".
  3. Un-glue common Indonesian connector words stuck to the previous word due to
     lost line breaks: "Persdan" -> "Pers dan", "massayang" -> "massa yang".
  4. Collapse whitespace, trim trailing punctuation.

Only writes when the cleaned value differs from node_name. Idempotent.

Usage:
  python scripts/14_fix_node_names.py            # apply
  python scripts/14_fix_node_names.py --dry-run  # preview only
"""
import re
import sys
import argparse

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0])
from common.db import get_connection  # noqa: E402

MODEL_TAG = "regex_unglue_v1"

# Sasaran/indicator marker that follows the real name, e.g. " 01 - Terwujudnya".
# Require it to be followed by an uppercase letter so we don't cut on year ranges.
MARKER = re.compile(r"\s+\d{2}\s*[-\u2013]\s*(?=[A-Z])")

# Camel-case glue (also covers accented latin just in case).
CASE_RE = re.compile(r"([a-z\u00e0-\u00ff])([A-Z\u00c0-\u00de])")

# Common Indonesian connector / function words frequently glued to the previous
# word when a PDF line break dropped the space. We only split when the connector
# is a trailing token (followed by whitespace) to limit false positives.
CONNECTORS = [
    "dengan", "untuk", "dalam", "serta", "yang", "oleh", "atas", "dari",
    "pada", "dan", "sebagai", "melalui", "secara", "maupun", "antara", "guna",
    "agar", "tentang", "terhadap", "menuju", "berbasis",
]
CONN_RE = re.compile(r"([a-z]{3})(" + "|".join(sorted(CONNECTORS, key=len, reverse=True)) + r")(?=\s)")


def clean_name(raw: str) -> str:
    if not raw:
        return raw
    m = MARKER.search(raw)
    name = raw[: m.start()] if m else raw
    name = CASE_RE.sub(r"\1 \2", name)
    # Apply connector splitting twice to catch chains like "massayangberwawasan".
    name = CONN_RE.sub(r"\1 \2", name)
    name = CONN_RE.sub(r"\1 \2", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(" ,.;:-\u2013")
    return name


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="preview changes without writing")
    ap.add_argument("--limit", type=int, default=0, help="limit preview rows (0 = all)")
    args = ap.parse_args()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, node_type, node_code, node_name FROM deepseek_policy_nodes")
    rows = cur.fetchall()

    changed = 0
    samples = []
    updates = []
    for nid, ntype, code, raw in rows:
        cleaned = clean_name(raw)
        if cleaned and cleaned != raw:
            changed += 1
            updates.append((cleaned, nid))
            if len(samples) < 15:
                samples.append((ntype, code, raw, cleaned))

    print(f"Total nodes        : {len(rows)}")
    print(f"Names to clean     : {changed}")
    print("\n-- sample transformations --")
    for ntype, code, raw, cleaned in samples:
        print(f"[{ntype} {code}]")
        print(f"  raw  : {raw[:110]!r}")
        print(f"  clean: {cleaned!r}")

    if args.dry_run:
        print("\nDRY RUN: no changes written.")
        conn.close()
        return

    cur.executemany(
        "UPDATE deepseek_policy_nodes "
        "SET clean_node_name_ai=%s, oc_name=1, model_used=%s WHERE id=%s",
        [(c, MODEL_TAG, i) for (c, i) in updates],
    )
    conn.commit()
    print(f"\nUpdated {cur.rowcount if cur.rowcount != -1 else changed} rows -> clean_node_name_ai.")
    conn.close()


if __name__ == "__main__":
    main()
