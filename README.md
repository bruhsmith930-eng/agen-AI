# 🤖 agen-AI — MiMo-AutoAgent v3.1

> Agen AI otonom: ketekunan agen riset + otak model terbuka (Xiaomi MiMo / Qwen lokal) + guardrail permanen yang tidak bisa dimatikan.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Cost](https://img.shields.io/badge/Biaya-%240-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Apa ini?
Beri satu tujuan, dan agen akan: bernalar sendiri, menulis skrip Python sendiri,
membaca file proyek, menyimpan temuan ke memori jangka panjang, dan mencoba terus
sampai tugas selesai — semua di bawah pagar keamanan yang tercatat di audit log.

## 🧰 Perkakas agen (terinspirasi Codex)
| Tool | Fungsi |
|---|---|
| think / remember / recall | penalaran + memori persisten (SQLite) |
| python / shell | eksekusi terkunci `lab_mode.txt` |
| read_file | baca file **hanya di dalam workspace** (sandbox ala workspace-write) |
| web_read | baca web dari allowlist host |
| finish | akhiri tugas + cetak statistik sesi |

## 🚀 Instalasi
```bash
git clone https://github.com/bruhsmith930-eng/agen-AI.git
cd agen-AI
pip install -r requirements.txt
cp .env.example .env      # isi key gratis / mode Ollama lokal
python agent.py
```

## 🆓 Mode gratis
- **OpenRouter `:free`** — biaya $0, otomatis pindah model bila satu gagal
- **Ollama lokal** — offline total, tanpa key, tanpa kuota

## 🛡️ Model keamanan
- Regex guardrail blokir perintah berbahaya & kebocoran kredensial
- Sandbox workspace untuk baca file
- Eksekusi shell/python butuh izin eksplisit `lab_mode.txt`
- Semua aksi tercatat di `agent_memory.db` (tabel audit) + statistik sesi

## 🗺️ Roadmap
- [ ] Mode multi-agen (planner + executor)
- [ ] UI web sederhana
- [ ] Integrasi PocketPal (offline di Android)

## 📜 Lisensi
MIT
