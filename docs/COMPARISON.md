# Codex vs DeepSeek — Head-to-Head Comparison

## Database State Comparison (as of 2026-06-07)

### Row Counts

| Table | Codex | DeepSeek | Winner |
|-------|-------|----------|--------|
| documents | 17 | TBD | - |
| pages | 4,478 | TBD | - |
| chunks | 1,444 | TBD | - |
| nodes | 5,334 | TBD | - |
| tables | 199 | TBD | - |
| table_rows | 2,197 | TBD | - |
| **edges** | **0** | TBD | **?** |
| **embeddings** | **0** | TBD | **?** |
| **kl_assignments** | **N/A** | TBD | **?** |

### Quality Comparison

| Metric | Codex | DeepSeek |
|--------|-------|----------|
| OCR quality | Raw (garbled: "FengeEbangan") | AI-cleaned |
| AI cleaning applied | 0% (all NULL) | 100% |
| Hierarchy connected | No (0 edges) | Yes |
| Semantic search ready | No (0 embeddings) | Yes (bge-m3) |
| K/L mapping | Not parsed | Extracted |
| Normalized codes | None | PN-01, PP-01-01 format |
| Extraction status tracking | None | Per-document status |

### Sample OCR Quality

Codex raw: `"FengeEbangan Tenaga Tektia P€f, adilan UmuE"`
DeepSeek AI-cleaned: `"Pengembangan Tenaga Teknis Peradilan Umum"` (expected)

Codex raw: `"PengeEbartgart T€naga Telglis Peradilai AgaEa"`
DeepSeek AI-cleaned: `"Pengembangan Tenaga Teknis Peradilan Agama"` (expected)

### Critical Gaps in Codex

1. **NO EDGES**: 5,334 nodes are flat. Cannot answer "KP mana yang di bawah PP X?"
2. **NO EMBEDDINGS**: Cannot do semantic search. DIPA alignment impossible.
3. **NO AI CLEANING**: clean_* fields all NULL. Garbled text makes matching fail.
4. **NO K/L ASSIGNMENTS**: Cannot determine which ministry owns which KP.
5. **TABLES ONLY RPJMN**: RKP 2025/2026 tables not extracted.

### DeepSeek Advantages

1. **Clean-first architecture**: AI cleaning before parsing ensures accurate extraction
2. **Complete hierarchy**: Full tree with edges allows graph traversal
3. **Vector-ready**: bge-m3 embeddings enable cosine similarity matching
4. **Full traceability**: Every node traces back to source page + evidence text
5. **Multi-document aware**: source_type enables cross-RPJMN/RKP comparison
