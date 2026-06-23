"""
Phase 4: Node Extraction
Parses PN/PP/KP hierarchy from Lampiran II documents (matrix tables).
Uses smart text parsing with fuzzy matching for OCR-damaged text.

Strategy:
1. For Lampiran II: Parse the matrix table structure (PN header → PP rows → KP rows)
2. For Lampiran III: Parse K/L assignment tables
3. For Lampiran I: Extract PN/PP/KP from narrative (simpler)
"""
import os, sys, re, json, hashlib
import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common.config import DB_CONFIG  # noqa: E402

# === SMART PATTERNS FOR OCR-DAMAGED TEXT ===

# PN: "PRIORITAS NASIONAL 01" or "PRIORITAS IIAAIOITL 01" (OCR garbled)
# Look for: keyword variant + 1-2 digit number
PN_HEADER = re.compile(
    r'(?:PRIORITAS\s*(?:NASIONAL|IIAAIOITL|TASIONAL|NASIOIIAL))\s*(\d{1,2})',
    re.IGNORECASE
)

# PP: "PROGRAM PRIORITAS 01.01" or "PROGRAU PRIORNAA 01-01"
PP_HEADER = re.compile(
    r'(?:PROGRAM|PROGRA[UM]|PROGRA[MU]\s*)?\s*(?:PRIORITAS|PRIORNAA|PRIORITTS)\s*[\s:]*(\d{1,2})[\.\-\s]+(\d{1,2})',
    re.IGNORECASE
)

# KP: "KEGIATAN PRIORITAS 01.01.01" - more complex, 3-part code
KP_HEADER = re.compile(
    r'(?:KEGIATAN|KEGIATAII|IIFI}IATAII|K[EI]GIATAN)\s*(?:PRIORITAS|PRIORITTS|PRTORTTTA)\s*[\s:]*(\d{1,2})[\.\-\s]+(\d{1,2})[\.\-\s]+(\d{1,2})',
    re.IGNORECASE
)

# Generic code pattern: XX.XX.XX or XX-XX-XX
CODE_PATTERN = re.compile(r'\b(\d{1,2})[\.\-](\d{1,2})(?:[\.\-](\d{1,2}))?\b')

# K/L code pattern: 3-digit department code
KDEPT_PATTERN = re.compile(r'\b(\d{3})\s*[-–—]\s*([A-Z][A-Za-z\s,/\-]+?)(?:\s{2,}|\n|$)', re.IGNORECASE)

# Indicator patterns
INDICATOR_PATTERNS = [
    re.compile(r'(?:persen|orang|unit|km|hektar|indeks|nilai|juta|miliar|triliun|ribu)', re.IGNORECASE),
    re.compile(r'[\d,]+[\.\d]*\s*\(?\d{4}\)?', re.IGNORECASE),  # 1.234 (2023)
]

# Allocation pattern: number with Juta/Miliar
ALOKASI_PATTERN = re.compile(r'(?:Rp\.?\s*)?([\d,]+[\.\d]*)\s*(?:Juta|Miliar|Triliun)', re.IGNORECASE)


def extract_pn_pp_kp_from_text(text, initial_pn=None, initial_pp=None):
    """Extract PN/PP/KP from both inline (OCR) and matrix (clean) formats.

    Two formats handled:
      Inline OCR:  "KEGIATAN PRIORITAS 01.01.01 Nama Kegiatan"
      Matrix clean: code on one line, "KP: name" on next line(s)

    State (current_pn, current_pp) is passed between chunks via initial_* args
    so that PN declared in chunk N is still active for KP entries in chunk N+k.
    Returns (nodes, final_pn, final_pp).
    """
    nodes = []
    lines = text.split('\n')
    n = len(lines)

    current_pn = initial_pn
    current_pp = initial_pp

    def build_window(start, count=5):
        parts = []
        for j in range(start, min(start + count * 2, n)):
            p = lines[j].strip()
            if p:
                parts.append(p)
            if len(parts) >= count:
                break
        return ' '.join(parts)

    i = 0
    while i < n:
        stripped = lines[i].strip()
        window = build_window(i, 5)

        # ─── PN: inline or window ───────────────────────────────────────────
        pn_match = PN_HEADER.search(stripped) or PN_HEADER.search(window)
        if pn_match:
            pn_code = pn_match.group(1).zfill(2)
            context = build_window(max(0, i - 2), 8)
            nodes.append({
                'node_type': 'PN', 'node_code': pn_code,
                'node_name': _extract_name(pn_match.string, 'PN'),
                'raw_text': context[:500], 'confidence': 0.7
            })
            current_pn = pn_code
            current_pp = None
            i += 1
            continue

        # ─── PP: inline or window ───────────────────────────────────────────
        if current_pn:
            pp_match = PP_HEADER.search(stripped) or PP_HEADER.search(window)
            if pp_match:
                pp_code = f"{pp_match.group(1)}.{pp_match.group(2)}"
                nodes.append({
                    'node_type': 'PP', 'node_code': pp_code,
                    'node_name': _extract_name(pp_match.string, 'PP'),
                    'parent_code': current_pn,
                    'raw_text': pp_match.string[:500], 'confidence': 0.65
                })
                current_pp = pp_code
                i += 1
                continue

        # ─── KP: inline format ──────────────────────────────────────────────
        if current_pp:
            kp_match = KP_HEADER.search(stripped) or KP_HEADER.search(window)
            if kp_match:
                kp_code = f"{kp_match.group(1)}.{kp_match.group(2)}.{kp_match.group(3)}"
                nodes.append({
                    'node_type': 'KP', 'node_code': kp_code,
                    'node_name': _extract_name(kp_match.string, 'KP'),
                    'parent_code': current_pp,
                    'raw_text': kp_match.string[:500], 'confidence': 0.6
                })
                i += 1
                continue

        # ─── KP: matrix format "XX.XX.XX" near "KP: name" ───────────────────
        # Lampiran II matrix puts the code on its own line, "KP:" on the next.
        # Parent PN/PP are derived from the code itself so cross-chunk state
        # is not required — we only need current_pn for sanity-gating.
        code_m = CODE_PATTERN.match(stripped)
        if code_m and code_m.group(3) and current_pn:
            kp_code_cand = f"{code_m.group(1)}.{code_m.group(2)}.{code_m.group(3)}"
            pn_cand = code_m.group(1).zfill(2)
            pp_cand = f"{code_m.group(1)}.{code_m.group(2)}"
            # Require "KP:" label within next 5 non-empty lines
            if re.search(r'\bKP\s*:', window, re.IGNORECASE):
                # Ensure PP exists (implicit from code)
                if current_pp != pp_cand:
                    current_pp = pp_cand
                # Extract name after "KP:"
                kp_name_m = re.search(r'\bKP\s*:\s*(.+)', window, re.IGNORECASE)
                kp_name = kp_name_m.group(1).strip()[:250] if kp_name_m else kp_code_cand
                nodes.append({
                    'node_type': 'KP', 'node_code': kp_code_cand,
                    'node_name': _extract_name('KP: ' + kp_name, 'KP'),
                    'parent_code': pp_cand,
                    'raw_text': window[:500], 'confidence': 0.6
                })
                i += 1
                continue

        # ─── KP: matrix format "KP: name" then code on next line ────────────
        kp_label_m = re.search(r'\bKP\s*:\s*(.+)', stripped, re.IGNORECASE)
        if kp_label_m and current_pn:
            for j in range(i + 1, min(i + 4, n)):
                code_m2 = CODE_PATTERN.match(lines[j].strip())
                if code_m2 and code_m2.group(3):
                    kp_code_cand = f"{code_m2.group(1)}.{code_m2.group(2)}.{code_m2.group(3)}"
                    pp_cand = f"{code_m2.group(1)}.{code_m2.group(2)}"
                    if current_pp != pp_cand:
                        current_pp = pp_cand
                    kp_name = kp_label_m.group(1).strip()[:250]
                    nodes.append({
                        'node_type': 'KP', 'node_code': kp_code_cand,
                        'node_name': _extract_name('KP: ' + kp_name, 'KP'),
                        'parent_code': pp_cand,
                        'raw_text': window[:500], 'confidence': 0.55
                    })
                    break

        i += 1

    return nodes, current_pn, current_pp


def _extract_name(text, node_type):
    """Extract entity name from text (inline OCR or multi-line clean format)."""
    if not text:
        return ''
    # Remove the header prefix (code + keyword)
    if node_type == 'PN':
        text = PN_HEADER.sub('', text, count=1)
    elif node_type == 'PP':
        text = PP_HEADER.sub('', text, count=1)
    elif node_type == 'KP':
        text = KP_HEADER.sub('', text, count=1)

    # Strip "KP:", "PP:", "PN:", "PRO-P:" prefixes left by clean-text table format
    text = re.sub(r'^(?:KP|PP|PN|PRO-P|PROG)\s*:\s*', '', text.strip(), flags=re.IGNORECASE)
    text = text.strip(' -:,.|')
    text = re.sub(r'\s+', ' ', text)

    # Truncate at sasaran/indicator markers
    if len(text) > 300:
        for sep in ['Indikator', 'Sasaran', 'Target', 'Alokasi', 'TARGET', 'INDIKATOR']:
            idx = text.find(sep)
            if idx > 10:
                text = text[:idx].strip()
                break
        text = text[:300]

    return text.strip()



def process_document(conn, doc_id, doc_family, attachment, source_type):
    """Extract nodes from a single document."""
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, chunk_index, page_start, page_end,
               COALESCE(clean_text_ai, text) AS text,
               level_hint
        FROM deepseek_policy_chunks
        WHERE document_id = %s
        ORDER BY chunk_index
    """, (doc_id,))
    chunks = cur.fetchall()
    
    total_nodes = 0
    current_pn = None   # carry PN/PP state across chunks within this document
    current_pp = None

    for chunk_id, chunk_idx, page_start, page_end, text, level_hint in chunks:
        nodes, current_pn, current_pp = extract_pn_pp_kp_from_text(
            text, initial_pn=current_pn, initial_pp=current_pp
        )

        for node in nodes:
            cur.execute("""
                SELECT id FROM deepseek_policy_nodes
                WHERE document_id = %s AND node_type = %s AND node_code = %s
            """, (doc_id, node['node_type'], node['node_code']))
            existing = cur.fetchone()
            
            if existing:
                continue
            
            parent_code = node.get('parent_code', '')
            
            cur.execute("""
                INSERT INTO deepseek_policy_nodes
                (document_id, chunk_id, source_type, node_type, node_code, node_name,
                 parent_code, normalized_code, source_page, raw_text, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                doc_id, chunk_id, source_type, node['node_type'], node['node_code'],
                node['node_name'], parent_code,
                _normalize_code(node['node_type'], node['node_code']),
                page_start, node['raw_text'], node['confidence']
            ))
            total_nodes += 1
        
        if chunk_idx % 20 == 0:
            conn.commit()
    
    conn.commit()
    return total_nodes
def _normalize_code(node_type, code):
    """Normalize code to standard format: PN-01, PP-01-01, etc."""
    prefix = {'PN': 'PN', 'PP': 'PP', 'KP': 'KP', 'PROGRAM': 'PROG', 'KEGIATAN': 'KEG'}
    p = prefix.get(node_type, node_type)
    return f"{p}-{code}"


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Focus on Lampiran II documents (primary matrix)
    cur.execute("""
        SELECT id, doc_family, doc_year, attachment
        FROM deepseek_policy_documents
        WHERE extraction_status = 'done'
        AND attachment LIKE '%Lampiran II%'
        ORDER BY doc_family, id
    """)
    docs = cur.fetchall()
    
    total_nodes = 0
    
    for doc_id, family, year, attach in docs:
        source_type = family
        
        # Check existing
        cur.execute("SELECT COUNT(*) FROM deepseek_policy_nodes WHERE document_id = %s", (doc_id,))
        existing = cur.fetchone()[0]
        if existing > 0:
            print(f"[SKIP] {family} {attach} — {existing} nodes exist")
            total_nodes += existing
            continue
        
        print(f"[EXTRACT] {family} {attach} (doc_id={doc_id})...")
        count = process_document(conn, doc_id, family, attach, source_type)
        print(f"  → {count} nodes extracted")
        total_nodes += count
    
    # Also process Lampiran I for narrative context
    cur.execute("""
        SELECT id, doc_family, doc_year, attachment
        FROM deepseek_policy_documents
        WHERE extraction_status = 'done'
        AND attachment LIKE '%Lampiran I%'
        ORDER BY doc_family, id
    """)
    docs = cur.fetchall()
    
    for doc_id, family, year, attach in docs:
        source_type = family
        
        cur.execute("SELECT COUNT(*) FROM deepseek_policy_nodes WHERE document_id = %s", (doc_id,))
        existing = cur.fetchone()[0]
        if existing > 0:
            print(f"[SKIP] {family} {attach} — {existing} nodes exist")
            total_nodes += existing
            continue
        
        print(f"[EXTRACT] {family} {attach} (doc_id={doc_id})...")
        count = process_document(conn, doc_id, family, attach, source_type)
        print(f"  → {count} nodes extracted")
        total_nodes += count
    
    # Summary
    cur.execute("""
        SELECT source_type, node_type, COUNT(*) as cnt
        FROM deepseek_policy_nodes
        GROUP BY source_type, node_type
        ORDER BY source_type, 
            CASE node_type WHEN 'PN' THEN 1 WHEN 'PP' THEN 2 WHEN 'KP' THEN 3 ELSE 4 END
    """)
    print(f"\n{'='*60}")
    print(f"NODE EXTRACTION SUMMARY: {total_nodes} total nodes")
    print(f"{'='*60}")
    for row in cur.fetchall():
        print(f"  {row[0]:12s} {row[1]:8s}: {row[2]:,}")
    
    conn.close()


if __name__ == "__main__":
    main()
