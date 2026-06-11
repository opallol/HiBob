# Codex vs DeepSeek — Head-to-Head Comparison

## Database State Comparison (as of 2026-06-07)

### Row Counts (diverifikasi DB 2026-06-11)

| Table | Codex | DeepSeek | Winner |
|-------|-------|----------|--------|
| documents | 17 | 17 | TIE |
| pages | 4,478 | 4,478 | TIE |
| chunks | 1,444 | 1,001 (990 cleaned) | **DS** (smarter) |
| nodes | 5,334 | 963 (connected) | **DS** |
| tables | 199 | 0 (script ada, belum run) | Codex |
| table_rows | 2,197 | 0 | Codex |
| **edges** | **0** | **857** | **DS** |
| **embeddings** | **0** | **0 (e5-small runtime)** | **DS** |
| **kl_assignments** | **N/A** | **604 (72 K/L)** | **DS** |

### Quality Comparison

| Metric | Codex | DeepSeek |
|--------|-------|----------|
| OCR quality | Raw (garbled: "FengeEbangan") | AI-cleaned |
| AI cleaning applied | 0% (all NULL) | 100% |
| Hierarchy connected | No (0 edges) | Yes |
| Semantic search ready | No (0 embeddings) | Yes (e5-small runtime) |
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
