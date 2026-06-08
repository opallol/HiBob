"""
Phase 2: PDF Text Extraction
Extracts text from all 17 PDF files into deepseek_policy_documents + deepseek_policy_pages
"""
import os
import sys
import hashlib
import pymysql
import pymupdf

# === CONFIG ===
DB_CONFIG = {
    "host": "172.16.2.153",
    "user": "ddac26",
    "password": "p4ssw0rd!",
    "database": "ddac2026",
    "port": 3306,
    "charset": "utf8mb4"
}

PDF_ROOT = r"D:\Project\RPJM dan RKP"
MANDATE_ROOT = r"D:\Project\DIPA\Tusi KL"

# === DOCUMENT REGISTRY ===
# Mapped from actual files in the directory
DOCUMENTS = [
    # RPJMN 2025-2029 (Perpres 12/2025)
    {"family": "RPJMN", "year": 2025, "reg": "Perpres 12/2025",
     "title": "Rencana Pembangunan Jangka Menengah Nasional Tahun 2025-2029",
     "attach": "salinan", "file": "Perpres Nomor 12 Tahun 2025.pdf"},
    {"family": "RPJMN", "year": 2025, "reg": "Perpres 12/2025",
     "title": "Narasi RPJMN Tahun 2025-2029",
     "attach": "Lampiran I", "file": "Perpres Nomor 12 Tahun 2025 - Lampiran I.pdf"},
    {"family": "RPJMN", "year": 2025, "reg": "Perpres 12/2025",
     "title": "Matriks Pembangunan RPJMN Tahun 2025-2029",
     "attach": "Lampiran II", "file": "Perpres Nomor 12 Tahun 2025 - Lampiran II.pdf"},
    {"family": "RPJMN", "year": 2025, "reg": "Perpres 12/2025",
     "title": "Matriks K/L RPJMN Tahun 2025-2029 (Bagian 1)",
     "attach": "Lampiran III (1)", "file": "Perpres Nomor 12 Tahun 2025 - Lampiran III.pdf"},
    {"family": "RPJMN", "year": 2025, "reg": "Perpres 12/2025",
     "title": "Matriks K/L RPJMN Tahun 2025-2029 (Bagian 2)",
     "attach": "Lampiran III (2)", "file": "Perpres Nomor 12 Tahun 2025 - Lampiran III..pdf"},
    {"family": "RPJMN", "year": 2025, "reg": "Perpres 12/2025",
     "title": "Arah Pembangunan Kewilayahan RPJMN (Bagian 1)",
     "attach": "Lampiran IV (1)", "file": "Perpres Nomor 12 Tahun 2025 - Lampiran IV.pdf"},
    {"family": "RPJMN", "year": 2025, "reg": "Perpres 12/2025",
     "title": "Arah Pembangunan Kewilayahan RPJMN (Bagian 2)",
     "attach": "Lampiran IV (2)", "file": "Perpres Nomor 12 Tahun 2025 - Lampiran IV..pdf"},
    
    # RKP 2025 (Perpres 109/2024)
    {"family": "RKP_2025", "year": 2025, "reg": "Perpres 109/2024",
     "title": "Rencana Kerja Pemerintah Tahun 2025",
     "attach": "salinan", "file": "Perpres Nomor 109 Tahun 2024.pdf"},
    {"family": "RKP_2025", "year": 2025, "reg": "Perpres 109/2024",
     "title": "Narasi RKP Tahun 2025",
     "attach": "Lampiran I", "file": "Perpres Nomor 109 Tahun 2024 - Lampiran I..pdf"},
    {"family": "RKP_2025", "year": 2025, "reg": "Perpres 109/2024",
     "title": "Matriks Pembangunan RKP Tahun 2025",
     "attach": "Lampiran II", "file": "Perpres Nomor 109 Tahun 2024 - Lampiran II.pdf"},
    
    # RKP 2026 (Perpres 117/2025)
    {"family": "RKP_2026", "year": 2026, "reg": "Perpres 117/2025",
     "title": "Rencana Kerja Pemerintah Tahun 2026",
     "attach": "salinan", "file": "1. Salinan Perpres Nomor 117 Tahun 2025.pdf"},
    {"family": "RKP_2026", "year": 2026, "reg": "Perpres 117/2025",
     "title": "Narasi RKP Tahun 2026",
     "attach": "Lampiran I", "file": "2. Lampiran I Perpres Nomor 117 Tahun 2025.pdf"},
    {"family": "RKP_2026", "year": 2026, "reg": "Perpres 117/2025",
     "title": "Matriks Pembangunan RKP Tahun 2026",
     "attach": "Lampiran II", "file": "3. Lampiran II Perpres Nomor 117 Tahun 2025.pdf"},
    {"family": "RKP_2026", "year": 2026, "reg": "Perpres 117/2025",
     "title": "Matriks K/L RKP Tahun 2026",
     "attach": "Lampiran III", "file": "4. Lampiran III Perpres Nomor 117 Tahun 2025.pdf"},
    {"family": "RKP_2026", "year": 2026, "reg": "Perpres 117/2025",
     "title": "Arah Pembangunan Kewilayahan RKP 2026 (hal 1-322)",
     "attach": "Lampiran IV (1)", "file": "5. Lampiran IV Perpres Nomor 117 Tahun 2025 (hal 1-322).pdf"},
    {"family": "RKP_2026", "year": 2026, "reg": "Perpres 117/2025",
     "title": "Arah Pembangunan Kewilayahan RKP 2026 (hal 323-643)",
     "attach": "Lampiran IV (2)", "file": "6. Lampiran IV Perpres Nomor 117 Tahun 2025 (hal 323-643).pdf"},
    
    # Mandate (Perpres 139/2024)
    {"family": "MANDATE", "year": 2024, "reg": "Perpres 139/2024",
     "title": "Penataan Tugas dan Fungsi Kementerian Negara Kabinet Merah Putih",
     "attach": "salinan", "file": "Perpres Nomor 139 Tahun 2024.pdf",
     "root_override": MANDATE_ROOT},
]


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    total_pages = 0
    total_errors = 0
    
    for i, doc in enumerate(DOCUMENTS):
        root = doc.get("root_override", PDF_ROOT)
        filepath = os.path.join(root, doc["file"])
        
        if not os.path.exists(filepath):
            print(f"[SKIP] {doc['file']} — file not found at {filepath}")
            continue
        
        # Check if already registered
        cur.execute(
            "SELECT id, extraction_status FROM deepseek_policy_documents WHERE doc_family=%s AND doc_year=%s AND attachment=%s",
            (doc["family"], doc["year"], doc["attach"])
        )
        existing = cur.fetchone()
        
        if existing and existing[1] == 'done':
            print(f"[SKIP] {doc['family']} {doc['attach']} — already extracted (id={existing[0]})")
            continue
        
        # Register document
        if existing:
            doc_id = existing[0]
            cur.execute("UPDATE deepseek_policy_documents SET extraction_status='extracting' WHERE id=%s", (doc_id,))
        else:
            cur.execute(
                """INSERT INTO deepseek_policy_documents 
                   (doc_family, doc_year, regulation_no, title, attachment, source_file, source_path)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (doc["family"], doc["year"], doc["reg"], doc["title"], doc["attach"], doc["file"], filepath)
            )
            doc_id = cur.lastrowid
        conn.commit()
        
        print(f"\n[{i+1}/{len(DOCUMENTS)}] {doc['family']} {doc['attach']}")
        print(f"  File: {doc['file']}")
        
        try:
            # Extract pages
            pdf = pymupdf.open(filepath)
            page_count = len(pdf)
            pages_extracted = 0
            
            for page_idx in range(page_count):
                page = pdf[page_idx]
                raw_text = page.get_text("text")
                
                # Detect printed page number
                printed = ""
                # Try to find page number in first/last lines
                lines = raw_text.strip().split('\n')
                for line in lines[-5:]:  # Check last 5 lines
                    stripped = line.strip()
                    if stripped.isdigit() and 1 <= int(stripped) <= 2000:
                        printed = stripped
                        break
                
                word_count = len(raw_text.split())
                has_text = 1 if word_count > 10 else 0
                page_kind = "text" if word_count > 50 else ("mixed" if word_count > 10 else "blank")
                text_hash = hashlib.sha256(raw_text.encode()).hexdigest()
                
                # Check if page already exists
                cur.execute(
                    "SELECT id FROM deepseek_policy_pages WHERE document_id=%s AND page_number=%s",
                    (doc_id, page_idx)
                )
                if cur.fetchone():
                    continue  # Skip existing
                
                cur.execute(
                    """INSERT INTO deepseek_policy_pages
                       (document_id, page_number, printed_page_number, page_kind, has_text_layer, word_count, raw_text, text_hash)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (doc_id, page_idx, printed, page_kind, has_text, word_count, raw_text, text_hash)
                )
                pages_extracted += 1
                
                if (page_idx + 1) % 50 == 0:
                    print(f"  ... {page_idx + 1}/{page_count} pages")
                    conn.commit()
            
            pdf.close()
            
            # Update document
            cur.execute(
                "UPDATE deepseek_policy_documents SET page_count=%s, extraction_status='done' WHERE id=%s",
                (page_count, doc_id)
            )
            conn.commit()
            
            total_pages += pages_extracted
            print(f"  OK  {pages_extracted} pages extracted (total {page_count} in PDF)")
            
        except Exception as e:
            total_errors += 1
            err_msg = str(e)[:2000]
            cur.execute(
                "UPDATE deepseek_policy_documents SET extraction_status='error', extraction_error=%s WHERE id=%s",
                (err_msg, doc_id)
            )
            conn.commit()
            print(f"  ERROR: {e}")
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"EXTRACTION COMPLETE")
    print(f"  Documents: {len(DOCUMENTS)}")
    print(f"  Total pages extracted: {total_pages}")
    print(f"  Errors: {total_errors}")


if __name__ == "__main__":
    main()
