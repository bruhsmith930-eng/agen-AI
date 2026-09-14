"""
MiMo-AutoAgent — Agen otonom hasil gabungan:
• Kepintaran agen HF: loop tanpa bosan, reasoning mendalam, belajar dari kegagalan
• Otak Xiaomi: MiMo-V2.5-Pro
• Jiwa aman: guardrail yang TIDAK PERNAH dimatikan
"""
import json, sqlite3, os, re, subprocess, sys, datetime

# ============ 1. KONFIGURASI ============
MODEL = "xiaomi/mimo-v2.5-pro"          # otak Xiaomi terbaru
# Alternatif gratis: "xiaomi/mimo-v2-flash:free"
BASE_URL = "https://openrouter.ai/api/v1"
API_KEY = os.environ.get("OPENROUTER_API_KEY")
MAX_STEPS = 30                          # batas aksi per tugas (anti-loop-abadi)

# ============ 2. GUARDRAIL (pelajaran insiden HF) ============
FORBIDDEN_PATTERNS = [
    r"\b169\.254\.169\.254\b",           # cloud metadata (vektor insiden!)
    r"(rm\s+-rf|format|mkfs)\b",         # perintah destruktif
    r"\b(curl|wget|nc|ssh)\b.*(?<!localhost)", # koneksi keluar tanpa izin
    r"(api[_-]?key|password|secret|token)\s*=", # pencurian kredensial
    r"\b(eval|exec)\s*$",               # eksekusi kode dinamis liar
]
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "api.openrouter.ai"]

def guardrail(action: str, arg: str) -> tuple[bool, str]:
    """Setiap aksi melewati pemeriksaan ini. TANPA PENGECUALIAN."""
    combined = f"{action} {arg}"
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, combined, re.IGNORECASE):
            return False, f"DITOLAK: cocok pola terlarang '{pattern}'"
    if action == "shell" and not os.path.exists("lab_mode.txt"):
        return False, "DITOLAK: mode shell butuh file lab_mode.txt (izin eksplisit kamu)"
    return True, "OK"

# ============ 3. MEMORI PERSISTEN (agen HF belajar dari 17rb aksinya) ============
db = sqlite3.connect("agent_memory.db")
db.execute("""CREATE TABLE IF NOT EXISTS memory(
    id INTEGER PRIMARY KEY, ts TEXT, type TEXT, content TEXT)""")
db.execute("""CREATE TABLE IF NOT EXISTS audit_log(
    id INTEGER PRIMARY KEY, ts TEXT, action TEXT, arg TEXT,
    verdict TEXT, result TEXT)""")

def remember(type_: str, content: str):
    db.execute("INSERT INTO memory(ts,type,content) VALUES(?,?,?)",
               (datetime.datetime.now().isoformat(), type_, content))
    db.commit()

def recall(query: str, limit=5):
    rows = db.execute(
        "SELECT content FROM memory WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{query}%", limit)).fetchall()
    return "\n".join(r[0] for r in rows) or "(belum ada memori terkait)"

def audit(action, arg, verdict, result):
    """Jejak audit — kebalikan dari agen HF yang pakai mode tanpa jejak 😄"""
    db.execute("INSERT INTO audit_log(ts,action,arg,verdict,result) VALUES(?,?,?,?,?)",
               (datetime.datetime.now().isoformat(), action, arg[:200],
                verdict, str(result)[:500]))
    db.commit()

# ============ 4. TOOLS (tangan si agen) ============
TOOLS_IMPL = {
    "think":    lambda text: f"[tercatat] {text}",
    "remember": lambda text: (remember("fakta", text), f"Disimpan: {text}")[1],
    "recall":   lambda query: recall(query),
    "shell":    lambda cmd: subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=30).stdout[:2000],
    "python":   lambda code: subprocess.run(
                    [sys.executable, "-c", code], capture_output=True,
                    text=True, timeout=60).stdout[:2000],
    "web_read": lambda url: f"(pasang library requests + trafilatura untuk fetch: {url})",
    "finish":   lambda summary: f"__SELESAI__{summary}",
}

TOOLS_SPEC = [{
    "type": "function",
    "function": {
        "name": name,
        "description": desc,
        "parameters": {"type": "object",
                       "properties": {"input": {"type": "string"}},
                       "required": ["input"]}
    }
} for name, desc in {
    "think": "Bernalar tentang langkah berikutnya (tidak memicu aksi)",
    "remember": "Simpan fakta penting ke memori jangka panjang",
    "recall": "Cari memori lama berdasarkan kata kunci",
    "shell": "Jalankan perintah shell (HANYA dengan izin lab_mode.txt)",
    "python": "Jalankan kode Python — tulis skripmu sendiri (kreativitas ala agen HF!)",
    "web_read": "Baca isi halaman web",
    "finish": "Selesaikan tugas dengan ringkasan akhir",
}.items()]

# ============ 5. OTAK: MiMo + SYSTEM PROMPT ============
SYSTEM_PROMPT = """Kamu adalah MiMo-AutoAgent: agen otonom yang cerdas dan tekun.
KARAKTERMU (diwarisi dari agen-agen terbaik):
1. TEKUN — jika satu cara gagal, coba cara lain. Jangan menyerah sebelum MAX_STEPS.
2. KREATIF — kamu boleh MENULIS SKRIP PYTHON SENDIRI untuk menyelesaikan sub-tugas.
3. SISTEMATIS — selalu: amati → berpikir → bertindak → pelajari hasil → ulangi.
4. BERMEMORI — simpan temuan penting dengan tool 'remember', panggil dengan 'recall'.
ATURAN MUTLAK (harga mati):
- Semua aksi melewati guardrail. Jika ditolak, HORMATI dan cari jalan legal lain.
- Tidak pernah menyentuh sistem/jaringan orang lain. Hanya milik user.
- Jelaskan reasoning-mu secara transparan di setiap langkah.
- Tujuanmu: menyelesaikan tugas user dengan cara yang SAH dan BERMANFAAT."""

def get_client():
    try:
        from openai import OpenAI
        return OpenAI(base_url=BASE_URL, api_key=API_KEY)
    except ImportError:
        sys.exit("Install dulu: pip install openai")

# ============ 6. LOOP OTONOM (jantung si agen) ============
def run(goal: str):
    client = get_client()
    print(f"\n🎯 TUGAS: {goal}\n" + "="*60)
    remember("tugas", goal)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]

    for step in range(1, MAX_STEPS + 1):
        resp = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOLS_SPEC,
            temperature=0.7)
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:                    # agen menjawab langsung
            print(f"\n💬 [step {step}] {msg.content}")
            messages.append({"role": "user",
                "content": "Lanjutkan, atau panggil 'finish' jika tugas selesai."})
            continue

        for tc in msg.tool_calls:
            name = tc.function.name
            arg = json.loads(tc.function.arguments).get("input", "")
            print(f"\n[step {step}] 🔧 {name}: {arg[:120]}")

            # --- GUARDRAIL DULU, BARU EKSEKUSI ---
            ok, verdict = guardrail(name, arg)
            if not ok:
                result = f"⛔ {verdict}"
                print(f"         {result}")
            else:
                try:
                    result = TOOLS_IMPL[name](arg)
                    print(f"         ✅ {str(result)[:200]}")
                except Exception as e:
                    result = f"ERROR: {e}"
                    print(f"         ❌ {result}")
            audit(name, arg, verdict, result)
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": str(result)[:3000]})

            if isinstance(result, str) and result.startswith("__SELESAI__"):
                print("\n" + "="*60)
                print(f"🏁 TUGAS SELESAI:\n{result[11:]}")
                remember("hasil", result[11:])
                return

    print("⏹️ Batas langkah tercapai — agen berhenti dengan aman.")

# ============ JALANKAN ============
if __name__ == "__main__":
    if not API_KEY:
        sys.exit("Set dulu: export OPENROUTER_API_KEY=sk-or-...")
    tugas = input("🎯 Apa tugas untuk agenmu? ")
    run(tugas)
