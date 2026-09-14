# 🤖 agen-AI — MiMo-AutoAgent

> Agen AI otonom: ketekunan & kreativitas agen riset + otak Xiaomi MiMo-V2.5-Pro + guardrail permanen yang tidak bisa dimatikan.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Brain](https://img.shields.io/badge/Brain-MiMo--V2.5--Pro-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Apa ini?
MiMo-AutoAgent bekerja dengan loop **amati → pikir → aksi → belajar → ulangi**.
Beri satu tujuan, dan ia akan: bernalar sendiri, menulis skrip Python sendiri,
menyimpan temuan ke memori jangka panjang, dan mencoba terus sampai tugas selesai —
semua di bawah pagar keamanan yang tercatat di audit log.

## 🧬 DNA proyek ini
| Sumber | Yang diadopsi |
|---|---|
| Studi agen otonom (insiden HF 2026) | Ketekunan tanpa bosan, kreativitas membuat tool sendiri, memori lintas-aksi |
| Xiaomi MiMo-V2.5-Pro (open source) | Otak reasoning & coding tingkat flagship |
| Pelajaran AI safety | Guardrail permanen, audit log transparan, allowlist target |

## 🏗️ Arsitektur
```
tujuan → [Otak MiMo] → pilih tool → [GUARDRAIL] → eksekusi → observasi → memori → ulangi
```

## 🚀 Instalasi
```bash
git clone https://github.com/bruhsmith930-eng/agen-AI.git
cd agen-AI
pip install -r requirements.txt
cp .env.example .env      # lalu isi API key-mu di .env (JANGAN di-commit!)
python agent.py
```

## 🛡️ Model keamanan
- Pola perintah berbahaya diblokir regex guardrail
- Eksekusi shell/python terkunci sampai user membuat `lab_mode.txt` (izin eksplisit)
- Akses web dibatasi `ALLOWED_HOSTS`
- Semua aksi tercatat di `agent_memory.db` (tabel audit)

## 🗺️ Roadmap
- [ ] Tool tambahan: rangkum dokumen, kirim email
- [ ] Mode multi-agen (planner + executor)
- [ ] Integrasi Galaxy AI / Chatbox mobile
- [ ] UI web sederhana

## 📜 Lisensi
MIT — bebas dipakai untuk belajar.
