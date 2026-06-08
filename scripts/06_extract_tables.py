"""
Phase 6: Table Extraction
Extracts structured tables from PDF using PyMuPDF table detection.
Parses PN/PP/KP hierarchy from table structure.
"""
import os, sys, json, hashlib, re
import pymysql
import pymupdf

DB_CONFIG = {
    "host": "172.16.2.153", "user": "ddac26", "password": "p4ssw0rd!",
    "database": "ddac2026", "port": 3306, "charset": "utf8mb4"
}

# Table header patterns to identify matrix tables
MATRIX_HEADERS = [
    'PRIORITAS NASIONAL', 'PROGRAM PRIORITAS', 'KEGIATAN PRIORITAS',
    'BASELINE', 'TARGET', 'ALOKASI', 'INDIKATOR', 'PENGAMPU',
    'PRTORTTAS', 'PROGRA', 'KEGIATAN',
]


def extract_tables_from_document(conn, doc_id, source_path):
    """Extract tables from a single PDF."""
    if not os.path.exists(source_path):
        return 0
    
    pdf = pymupdf.open(source_path)
    cur = conn.cursor()
    tables_found = 0
    
    for page_num in range(len(pdf)):
        page = pdf[page_num]
        
        # Try table detection
        tables = page.find_tables()
        if not tables.tables:
            continue
        
        for t_idx, table in enumerate(tables.tables):
            rows = table.extract()
            if not rows or len(rows) < 3:
                continue
            
            # Check if this looks like a planning matrix table
            header_row = ' '.join([str(c or '') for c in rows[0]])
            is_matrix = any(h in header_row.upper() for h in MATRIX_HEADERS)
            
            if not is_matrix:
                continue
            
            # Save table
            columns = [str(c or '') for c in rows[0]]
            markdown = '| ' + ' | '.join(columns) + ' |\n'
            markdown += '|' + '|'.join(['---' for _ in columns]) + '|\n'
            
            for row in rows[1:]:
                cells = [str(c or '') for c in row]
                markdown += '| ' + ' | '.join(cells) + ' |\n'
            
            cur.execute("""
                INSERT INTO deepseek_policy_tables
                (document_id, table_index, page_start, page_end, caption, markdown, 
                 columns_json, row_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                doc_id, tables_found, page_num, page_num,
                f"Page {page_num} Table {t_idx}",
                markdown, json.dumps(columns), len(rows)
            ))
            table_id = cur.lastrowid
            tables_found += 1
            
            # Save rows
            for r_idx, row in enumerate(rows):
                row_text = ' | '.join([str(c or '') for c in row])
                cur.execute("""
                    INSERT INTO deepseek_policy_table_rows
                    (table_id, row_index, row_json, row_text)
                    VALUES (%s, %s, %s, %s)
                """, (table_id, r_idx, json.dumps(row), row_text))
    
    pdf.close()
    conn.commit()
    return tables_found


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Focus on Lampiran II and III (matrix documents)
    cur.execute("""
        SELECT id, source_path, doc_family, attachment
        FROM deepseek_policy_documents
        WHERE extraction_status = 'done'
        AND (attachment LIKE '%Lampiran II%' OR attachment LIKE '%Lampiran III%')
        ORDER BY doc_family, id
    """)
    docs = cur.fetchall()
    
    total_tables = 0
    for doc_id, path, family, attach in docs:
        print(f"[TABLES] {family} {attach}...")
        count = extract_tables_from_document(conn, doc_id, path)
        print(f"  → {count} tables found")
        total_tables += count
    
    print(f"\nTotal: {total_tables} tables extracted")
    conn.close()


if __name__ == "__main__":
    main()
