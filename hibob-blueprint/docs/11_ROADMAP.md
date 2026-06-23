# Hibob Roadmap

Status: Draft matang v0.1 - eksekusi berjalan (Phase 0-2.5 selesai)

**Legenda status:** ✅ selesai (kode + unit test) · 🚧 sedang dikerjakan · ⏳ planned.
Catatan: gate eval berbasis DeepEval (kriteria exit yang menyebut "eval pass") baru punya
harness penuh di Phase 6 - sampai saat itu, fase ditandai ✅ atas dasar implementasi + unit test,
dengan eval formalnya menyusul.

> Re-sequenced setelah ADR 0005-0013 (accepted overpower recommendations) diterima ke blueprint. Aturan emas dari review tetap berlaku: jangan kerjakan satu pun dari ADR baru ini sebelum Phase 0-2 (Core + Memory + Eval baseline) berdiri - semuanya pengali, dan pengali dari nol tetap nol. Penempatan tiap ADR ke fase mengikuti peta prioritas review (🔴 cepat, 🟠 investasi inti, 🟡 pembeda jiwa, 🟢 pengeras keamanan).

## Phase 0 - Blueprint Foundation ✅

Goal: repo tidak kosong secara arah; keputusan besar terdokumentasi.

Deliverables:

- PRD,
- architecture,
- ERD,
- memory design,
- tool policy,
- security/privacy policy,
- evaluation plan,
- repo structure,
- ADRs.

Exit criteria:

- Bob setuju arah besar.
- Scope v0.1 jelas.
- Stack core vs sandbox jelas.

## Phase 1 - Hibob Core Minimal ✅

Goal: Hibob punya backend core, model router, dan conversation management.

Deliverables:

- FastAPI skeleton,
- DB schema/migrations,
- `/chat` endpoint,
- model adapter Ollama,
- optional cloud adapter,
- conversation/message persistence,
- basic persona prompt,
- cost circuit breaker minimal: `budget_ceilings` + `cost_ledger`, pause cloud call on breach (ADR 0012, 🔴 jangan ditunda - murah dan menyelamatkan dompet sejak cloud call pertama).

Exit criteria:

- Bob bisa chat via API/UI.
- Pesan tersimpan.
- Model local/cloud bisa dipilih.
- Tidak ada satu pun cloud call yang lolos tanpa cek ceiling.

## Phase 2 - Memory Core ✅

Goal: Hibob mulai mengingat secara sehat.

Deliverables:

- memory tables,
- candidate extraction,
- approval workflow,
- memory search,
- Qdrant memory collection,
- memory conflict minimal,
- session summary,
- skema `memory_edges` dan `memory_usage_feedback` dibuat, belum diaktifkan penuh (ADR 0006, ADR 0007 - 🟠 investasi inti, desain dulu sebelum aktivasi).

Exit criteria:

- Kandidat memory bisa dibuat dan disetujui.
- Hibob bisa recall keputusan lama.
- DeepEval memory suite awal pass.

## Phase 2.5 - Memory Graph & Calibration Ringan ✅

Goal: memory mulai punya relasi dan belajar dari pemakaiannya, tanpa menunggu Phase 8.

Deliverables:

- `memory_edges` aktif untuk relasi dasar (`supersedes`, `contradicts`) - ADR 0006,
- traversal sederhana via recursive CTE (tanpa graph DB terpisah),
- `memory_usage_feedback` mulai dicatat dari sesi chat,
- update confidence Bayesian ringan aktif, dibatasi tidak pernah mempromosikan `status` (ADR 0007).

Exit criteria:

- Hibob bisa jawab "kenapa kita pindah dari keputusan X ke Y?" lewat traversal edge.
- Memory yang berulang dikoreksi mulai turun confidence-nya secara terukur.
- `memory_graph_calibration_eval` (doc 09 §5) pass.

## Phase 3 - Knowledge Base/RAG ⏳

Goal: Hibob bisa membaca dokumen dan web.

Deliverables:

- document upload/register,
- Unstructured parser,
- Crawl4AI crawler,
- chunking,
- embedding,
- Qdrant document collection,
- source-based answers.

Exit criteria:

- Minimal 1 PDF/DOCX dan 1 web source indexed.
- Hibob menjawab dengan source reference.
- RAG eval awal pass.

## Phase 3.5 - Reflective Sibling ⏳

Goal: Hibob mulai proaktif, bukan cuma reaktif - realisasi langsung identitas "saudara digital" (Executive Blueprint §2), tidak perlu menunggu Phase 8.

Deliverables:

- scheduled reflection job (harian/mingguan, local model, read-only) - ADR 0010,
- scan konflik di memory graph (Phase 2.5), asumsi belum diuji, sumber RAG stale,
- `reflections` table dan output yang Bob baca async.

Exit criteria:

- Reflection job menghasilkan minimal satu temuan relevan dalam uji coba seminggu.
- Reflection tidak pernah menulis durable memory atau memanggil tool langsung - hanya mengusulkan kandidat lewat pipeline approval yang sudah ada.
- `reflection signal precision` (doc 09 §7) terlacak.

## Phase 4 - Tool Gateway ⏳

Goal: Hibob bisa memakai tools dengan izin.

Deliverables:

- tool registry,
- risk level,
- approval request,
- audit logs,
- internal tools,
- GitHub/repo read tools,
- draft patch tool,
- Policy Engine eksekutabel - `policy_rules` + `tool_trust_scores` + `content_provenance_flags` (ADR 0005, 🔴 mulai di sini, lebih murah daripada retrofit nanti),
- Ephemeral Sandbox Runtime untuk tool type shell/browser/MCP - wajib aktif sebelum tool jenis itu benar-benar dinyalakan (ADR 0011, 🟢 pengeras keamanan).
- Operational Credential Vault storage layer - `credential_vault` + `credential_uses`, terenkripsi at rest, tidak pernah masuk prompt/trace/memory/vector (ADR 0014, 🟢 pengeras keamanan). Storage saja - belum ada satu pun tool login/kirim pesan yang dinyalakan di fase ini.

Exit criteria:

- Low-risk tools auto.
- High-risk tools ask approval.
- Critical tools denied.
- Tool policy eval pass.
- Keputusan allow/ask/deny dihasilkan Policy Engine, bukan judgement model saat itu.
- Tool shell/browser/MCP apa pun yang dinyalakan, jalan di sandbox ephemeral - tidak ada exception ambient.

## Phase 5 - Dev Partner Loop ⏳

Goal: Hibob membantu membangun dirinya.

Deliverables:

- issue drafting,
- blueprint update proposal,
- Cline/Aider workflow docs,
- repo search/read,
- patch draft flow,
- CI basic,
- Self-building loop merge gate: `propose_blueprint_update`/`draft_patch`/`create_github_issue_draft` dievaluasi Policy Engine, security/policy/schema file selalu high risk, merge butuh test + DeepEval + docs + approval Bob (ADR 0013 - menutup gap "self-building loop under-specified").

Exit criteria:

- Diskusi dapat berubah menjadi issue.
- Issue dapat dibantu AI coding agent.
- Tests/evals run sebelum merge.
- Tidak ada satu pun self-build patch yang merge tanpa lewat gate ADR 0013, berapa pun kecil diff-nya.

## Phase 6 - Observability & Regression Quality ⏳

Goal: kualitas Hibob bisa dilacak dan ditingkatkan.

Deliverables:

- Phoenix traces integrated,
- DeepEval suites expanded,
- eval datasets,
- prompt versioning,
- failure review workflow,
- Deterministic Replay Harness - simpan assembled prompt, dry-run mode di Model Router, diff terhadap eval_results (ADR 0008, 🟠 ROI tertinggi - hampir gratis dari disiplin tracing yang sudah ada),
- Eval judge integrity - golden dataset + pinned `eval_judge_versions` (ADR 0009 bagian judge),
- Learned router bias - bandit epsilon-greedy di antara kandidat yang sudah diizinkan tabel statis, berbasis `router_policy_feedback` (ADR 0012 bagian learned routing),
- Mulai Adversarial Self-Red-Team Loop terhadap instance sandboxed (ADR 0009, 🟢 - butuh Policy Engine dari Phase 4 sebagai target serangan).

Exit criteria:

- Trace per run tersedia.
- Eval pass rate tracked.
- Setiap failure penting menambah regression test.
- Minimal satu replay batch sudah dijalankan dan dicatat sebagai evidence di sebuah ADR migrasi (nyata atau latihan).
- Eval judge terpin versinya, agreement score terhadap golden dataset terlacak.

## Phase 7 - Controlled Browser & Automation ⏳

Goal: Hibob bisa mengoperasikan environment terbatas.

Deliverables:

- Playwright MCP localhost only,
- Activepieces human-in-loop flows,
- browser UI testing,
- workflow trigger approval,
- sandbox policy (Ephemeral Sandbox dari Phase 4, ADR 0011, sekarang menanggung tool browser/automation yang lebih aktif),
- Red-team loop (ADR 0009) memasukkan tipe serangan baru yang relevan dengan browser/automation (`permission_persuasion` lewat workflow, dst).
- Tool login/kirim pesan pertama yang memakai Credential Vault (ADR 0014) boleh dinyalakan di sini paling cepat - selalu lewat Tool Gateway + Sandbox (ADR 0011) + approval per-aksi, risk tier tetap `critical`, tidak pernah trust-tier escalation.

Exit criteria:

- Hibob bisa test UI lokal.
- Tidak bisa submit public/sensitive action.
- Approval/audit works.
- Kalau ada tool login/kirim pesan yang diaktifkan: nol resolusi credential_ref yang lolos tanpa approval, dan nol nilai kredensial asli yang tercatat di trace/log (ADR 0014).
- Red-team cycle terbaru terhadap tool browser/automation tidak punya `succeeded` attempt yang belum dikonversi jadi eval case.

## Phase 8 - Personal AI OS Beta ⏳

Goal: Hibob jadi lapisan operasi personal Bob.

Deliverables:

- multi-source memory,
- reflection lintas-sesi yang lebih dalam (dasar sudah jalan sejak Phase 3.5, ADR 0010 - di sini ditingkatkan ke horizon waktu lebih panjang),
- advanced project management,
- repo/code semantic search,
- optional voice,
- custom UI.

Exit criteria:

- Hibob membantu planning, coding, knowledge, and reflection.
- Bob menggunakan Hibob sebagai sistem harian.

## Things intentionally delayed

- avatar,
- realtime voice,
- mobile app,
- autonomous web write,
- email/calendar write,
- deployment production public,
- multi-user SaaS,
- fine-tuning.

## Roadmap risks

The biggest risk is trying to jump from Phase 0 to Phase 8. Hibob must earn autonomy step by step.

The accepted overpower ADRs (0005-0013) make this risk sharper, not smaller: it is now tempting to build the memory graph, policy engine, or red-team loop before `/chat` and basic memory even work. Every "multiplier" capability added by these ADRs is exactly that - a multiplier of whatever exists at Phase 0-2. A multiplier of zero is still zero. See `REVIEW_DAN_REKOMENDASI_OVERPOWER.md` §5 for the same warning from the review that produced these ADRs.
