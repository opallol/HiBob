# HiBob

**HiBob** adalah fondasi AI saudara digital, second brain, agent operator, dan AI dev partner milik Bob.

Repo ini saat ini berisi beberapa subproject utama yang sedang dikembangkan dan/atau dianalisis.

## Struktur Repo Saat Ini

```text
HiBob/
├── ddac_deepseek_kms/
├── hibob-blueprint/
├── hello_world
└── README.md
```

## Subproject

### `ddac_deepseek_kms/`

Project DDAC / DeepSeek KMS yang sedang dianalisis.

### `hibob-blueprint/`

Blueprint arsitektur HiBob: AI saudara digital, second brain, agent operator, memory core, model routing, policy, dan tool gateway.

Bukan lagi sekadar dokumen — backend `hibob_core` sudah berjalan: **Phase 1-5 selesai** (Core, Memory Core, Memory Graph & Calibration, Knowledge Base/RAG, Reflective Sibling, Multimodal Input, Tool Gateway, Dev Partner Loop). Lihat `hibob-blueprint/backend/README.md` untuk cara menjalankan dan `hibob-blueprint/docs/11_ROADMAP.md` untuk status per fase.

### `hello_world`

File/contoh awal untuk pengujian repository.

## Catatan

README ini sudah dibersihkan dari merge conflict akibat penggabungan dua riwayat Git yang berbeda.

Sebelum melanjutkan development, pastikan tidak ada file sensitif yang ikut ter-push, seperti:

- `.env`
- API key
- token GitHub
- password database
- private key
- credential cloud
