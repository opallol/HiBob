"""
Phase 3: Chunking + AI Cleaning
Groups pages into chunks, detects section/level hints, cleans garbled OCR text.

Strategy:
- Lampiran II (matrix): chunk by PN/PP/KP table boundaries  
- Lampiran I (narasi): chunk by section headings
- Lampiran III (K/L matrix): chunk by K/L sections
- Others: sliding window chunks (~2000 tokens)

The AI cleaning step uses the Hermes agent's LLM to fix garbled text.
"""
import os
import sys
import hashlib
import json
import pymysql

# === CONFIG ===
DB_CONFIG = {
    "host": "172.16.2.153",
    "user": "ddac26",
    "password": "p4ssw0rd!",
    "database": "ddac2026",
    "port": 3306,
    "charset": "utf8mb4"
}

# Regex patterns for detecting planning entity codes
import re
PN_PATTERN = re.compile(r'Prioritas\s*Nasional\s*(\d{1,2})', re.IGNORECASE)
PP_PATTERN = re.compile(r'Program\s*Prioritas\s*[\s:]*(\d{1,2}[\.-]\d{1,2})', re.IGNORECASE)
KP_PATTERN = re.compile(r'Kegiatan\s*Prioritas\s*[\s:]*(\d{1,2}[\.-]\d{1,2}[\.-]\d{1,2})', re.IGNORECASE)
SECTION_PATTERN = re.compile(r'^(?:BAB|BAGIAN|PRIORITAS NASIONAL|PROGRAM PRIORITAS|KEGIATAN PRIORITAS)\s', re.IGNORECASE)
KL_PATTERN = re.compile(r'KEMENTERIAN|BADAN|LEMBAGA|MAHKAMAH|KEPOLISIAN|KEJAKSAAN|SEKRETARIAT', re.IGNORECASE)

# Level hints for Lampiran II
LEVEL_MARKERS = [
    (re.compile(r'PRIORITAS\s+NASIONAL\s+\d{1,2}\b', re.IGNORECASE), 'PN'),
    (re.compile(r'PROGRAM\s+PRIORITAS\s+\d{1,2}[\.-]\d{1,2}', re.IGNORECASE), 'PP'),
    (re.compile(r'KEGIATAN\s+PRIORITAS\s+\d{1,2}[\.-]\d{1,2}[\.-]\d{1,2}', re.IGNORECASE), 'KP'),
]


def detect_level_hint(text):
    """Detect planning entity level from text content."""
    # Check for PN/PP/KP markers
    for pattern, level in LEVEL_MARKERS:
        if pattern.search(text):
            return level
    # Check for K/L matrix
    if KL_PATTERN.search(text) and ('KODE' in text or 'LOKASI' in text or 'ALOKASI' in text):
        return 'KL_MATRIX'
    return 'TEXT'


def detect_section_hint(text):
    """Extract a short section heading from text."""
    lines = text.strip().split('\n')
    for line in lines[:10]:  # Check first 10 lines
        stripped = line.strip()
        if len(stripped) > 10 and len(stripped) < 200:
            # Check if looks like a heading
            if SECTION_PATTERN.match(stripped) or re.match(r'^[A-Z][A-Z\s]{10,}', stripped):
                return stripped[:200]
    return ''


def chunk_pages(conn, doc_id, doc_family, attachment):
    """Chunk pages from a single document."""
    cur = conn.cursor()
    
    # Get all text pages for this document
    cur.execute("""
        SELECT id, page_number, raw_text
        FROM deepseek_policy_pages
        WHERE document_id = %s AND has_text_layer = 1
        ORDER BY page_number
    """, (doc_id,))
    pages = cur.fetchall()
    
    if not pages:
        return 0
    
    chunks_created = 0
    current_chunk = []
    current_start = 0
    current_text = []
    current_words = 0
    
    for page_id, page_num, text in pages:
        words = len(text.split())
        
        # Decide whether to start new chunk
        new_section = detect_level_hint(text)
        is_boundary = new_section != 'TEXT'
        
        should_split = (
            (current_words + words > 2000) or  # Max ~2000 words per chunk
            (len(current_chunk) >= 5) or  # Max 5 pages per chunk
            (is_boundary and current_chunk)  # Split at PN/PP/KP boundaries
        )
        
        if should_split and current_chunk:
            # Save current chunk
            save_chunk(conn, doc_id, chunks_created, current_start, 
                      current_chunk[-1], current_text)
            chunks_created += 1
            current_chunk = []
            current_text = []
            current_words = 0
            current_start = page_num
        
        if not current_chunk:
            current_start = page_num
        
        current_chunk.append(page_num)
        current_text.append(text)
        current_words += words
    
    # Save final chunk
    if current_chunk:
        save_chunk(conn, doc_id, chunks_created, current_start,
                  current_chunk[-1], current_text)
        chunks_created += 1
    
    return chunks_created


def save_chunk(conn, doc_id, chunk_idx, page_start, page_end, text_parts):
    """Save a chunk to database."""
    full_text = '\n\n--- PAGE BREAK ---\n\n'.join(text_parts)
    level_hint = detect_level_hint(full_text)
    section_hint = detect_section_hint(full_text)
    token_estimate = len(full_text.split())  # rough estimate
    text_hash = hashlib.sha256(full_text.encode()).hexdigest()
    
    cur = conn.cursor()
    cur.execute("""
        INSERT IGNORE INTO deepseek_policy_chunks
        (document_id, chunk_index, page_start, page_end, section_hint, 
         level_hint, text, token_estimate, text_hash)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (doc_id, chunk_idx, page_start, page_end, section_hint,
          level_hint, full_text, token_estimate, text_hash))
    conn.commit()


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Get all extracted documents
    cur.execute("""
        SELECT id, doc_family, doc_year, attachment 
        FROM deepseek_policy_documents 
        WHERE extraction_status = 'done'
        ORDER BY doc_family, id
    """)
    docs = cur.fetchall()
    
    total_chunks = 0
    
    for doc_id, family, year, attach in docs:
        # Check if already chunked
        cur.execute("SELECT COUNT(*) FROM deepseek_policy_chunks WHERE document_id = %s", (doc_id,))
        existing = cur.fetchone()[0]
        if existing > 0:
            print(f"[SKIP] {family} {attach} — {existing} chunks already exist")
            total_chunks += existing
            continue
        
        print(f"[CHUNKING] {family} {attach} (doc_id={doc_id})...")
        count = chunk_pages(conn, doc_id, family, attach)
        print(f"  → {count} chunks created")
        total_chunks += count
    
    # Print summary
    cur.execute("""
        SELECT d.doc_family, d.attachment, COUNT(c.id) as chunks,
               SUM(c.token_estimate) as tokens
        FROM deepseek_policy_chunks c
        JOIN deepseek_policy_documents d ON c.document_id = d.id
        GROUP BY d.id
        ORDER BY d.doc_family, d.id
    """)
    print(f"\n{'='*60}")
    print(f"CHUNKING SUMMARY: {total_chunks} total chunks")
    print(f"{'='*60}")
    for row in cur.fetchall():
        print(f"  {row[0]:12s} {row[1]:20s} | chunks={row[2]:4d} tokens={row[3]:,}")
    
    # Level hint distribution
    cur.execute("""
        SELECT level_hint, COUNT(*) as cnt
        FROM deepseek_policy_chunks
        GROUP BY level_hint
        ORDER BY cnt DESC
    """)
    print(f"\n--- Level Hint Distribution ---")
    for row in cur.fetchall():
        print(f"  {row[0]:12s}: {row[1]:,}")
    
    conn.close()


if __name__ == "__main__":
    main()
