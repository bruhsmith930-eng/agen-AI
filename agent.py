"""
MiMo-AutoAgent v3.1 (FINAL)
Agen otonom: loop amati-pikir-aksi-belajar + guardrail permanen + memori persisten.
Fitur v3.1:
  - Otak otomatis model GRATIS ($0) dengan cadangan berantai
  - Dukungan Ollama lokal (offline, tanpa key) via .env
  - Sandbox ala "workspace-write": read_file hanya di dalam folder proyek
  - Tool baca file ala Codex: read_file
  - Ringkasan sesi ala footer Codex (jumlah aksi, ditolak, durasi)
Cara pakai: lihat README.md
"""
import json, os, re, sqlite3, subprocess, sys, time, datetime
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

# ================= 1. KONFIGURASI =================
FREE_MODELS = [m for m in [
    os.environ.get("MODEL", ""),                    # pilihanmu dari .env
    "xiaomi/mimo-v2-flash:free",                    # otak Xiaomi tier gratis
    "deepseek/deepseek-chat-v3-0324:free",          # cadangan gratis 1
    "meta-llama/llama-3.3-70b-instruct:free",        # cadangan gratis 2
] if m]
BASE_URL  = os.environ.get("BASE_URL", "https://openrouter.ai/api/v1")
API_KEY   = os.environ.get("OPENROUTER_API_KEY", "ollama")  # "ollama" = mode lokal
MAX_STEPS = int(os.environ.get("MAX_STEPS", "20"))
WORKSPACE = os.getcwd()                              # batas sandbox
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "openrouter.ai", "api.openrouter.ai",
                 "huggingface.co", "id.wikipedia.org"}
T0 = time.time()
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

# ================= 2. GUARDRAIL (TIDAK BISA DIMATIKAN) =================
FORBIDDEN = [
    r"169\.254\.169\.254",                                      # metadata cloud
    r"\brm\s+-rf\b|\bmkfs\b|:\s*$$\s*\{",                     # destruktif/fork bomb
    r"(password|secret|token|api[_-]?key)\s*=\s*['\"]?\S{8,}",  # bocorkan kredensial
]

def guardrail(action, arg):
    """Setiap aksi melewati sini. Tanpa pengecualian."""
    for p in FORBIDDEN:
        if re.search(p, arg, re.I):
            return False, f"pola terlarang: {p}"
    if action == "web_read":
        host = urlparse(arg).hostname or ""
        if host not in ALLOWED_HOSTS:
            return False, f"host '{host}' di luar ALLOWED_HOSTS"
    if action == "read_file":
        if not os.path.abspath(arg).startswith(WORKSPACE):
            return False, "di luar workspace (sandbox workspace-write)"
    if action in ("shell", "python") and not os.path.exists("lab_mode.txt"):
        return False, "eksekusi terkunci: buat lab_mode.txt sebagai izin eksplisitmu"
    return True, "ok"

# ================= 3. MEMORI & AUDIT =================
db = sqlite3.connect("agent_memory.db")
db.executescript("""
CREATE TABLE IF NOT EXISTS memory(id INTEGER PRIMARY KEY, ts TEXT, content TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, action TEXT,
               arg TEXT, verdict TEXT, result TEXT);""")

def remember(t):
    db.execute("INSERT INTO memory(ts,content) VALUES(?,?)",
               (datetime.datetime.now().isoformat(), t))
    db.commit()

def recall(q):
    rows = db.execute("SELECT content FROM memory WHERE content LIKE ? "
                      "ORDER BY id DESC LIMIT 5", (f"%{q}%",)).fetchall()
    return "\n".join(r[0] for r in rows) or "(belum ada memori)"

def audit(a, g, v, r):
    db.execute("INSERT INTO audit(ts,action,arg,verdict,result) VALUES(?,?,?,?,?)",
               (datetime.datetime.now().isoformat(), a, g[:200], v, str(r)[:500]))
    db.commit()

def session_stats():
    total  = db.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
    denied = db.execute("SELECT COUNT(*) FROM audit WHERE verdict!='ok'").fetchone()[0]
    return (f"📊 Sesi: {total} aksi | {denied} ditolak guardrail | "
            f"{round(time.time()-T0,1)} detik")

# ================= 4. TOOLS =================
def t_shell(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True, timeout=30).stdout[:2000]

def t_python(code):
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=60).stdout[:2000]

def t_web(url):
    import requests
    return requests.get(url, timeout=15,
                        headers={"User-Agent": "MiMo-AutoAgent/3.1"}).text[:3000]

def t_read(path):
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()[:3000]

TOOLS = {
    "think":     lambda t: f"[pikiran tercatat] {t}",
    "remember":  lambda t: (remember(t), f"disimpan: {t}")[1],
    "recall":    recall,
    "shell":     t_shell,
    "python":    t_python,
    "web_read":  t_web,
    "read_file": t_read,
    "finish":    lambda s: f"__SELESAI__{s}",
}

SPEC = [{"type": "function", "function": {"name": n, "description": d,
         "parameters": {"type": "object",
                        "properties": {"input": {"type": "string"}},
                        "required": ["input"]}}}
        for n, d in {
    "think":     "Bernalar tentang langkah berikutnya tanpa aksi",
    "remember":  "Simpan temuan penting ke memori jangka panjang",
    "recall":    "Cari memori lama berdasarkan kata kunci",
    "shell":     "Jalankan perintah shell (butuh lab_mode.txt)",
    "python":    "Tulis & jalankan skrip Python sendiri (butuh lab_mode.txt)",
    "web_read":  "Baca halaman web dari ALLOWED_HOSTS",
    "read_file": "Baca isi file teks di dalam folder workspace",
    "finish":    "Akhiri tugas dengan ringkasan final",
}.items()]

SYSTEM = """Kamu MiMo-AutoAgent v3.1: agen otonom yang tekun, kreatif, dan transparan.
Cara kerja: amati -> pikir -> aksi -> pelajari hasil -> ulangi sampai selesai.
Jika satu cara gagal, coba cara lain; kamu boleh menulis skrip Python sendiri.
Simpan temuan penting dengan 'remember'; ambil memori lama dengan 'recall'.
Baca file proyek dengan 'read_file' (hanya di dalam workspace).
ATURAN MUTLAK: patuhi guardrail (jika ditolak, cari jalan sah lain); jangan sentuh
sistem di luar izin user; jelaskan reasoning-mu di setiap langkah."""

# ================= 5. PEMANGGILAN MODEL + CADANGAN GRATIS =================
def ask_llm(msgs, tools):
    last_err = None
    for model in FREE_MODELS:
        for attempt in range(2):
            try:
                msg = client.chat.completions.create(
                    model=model, messages=msgs, tools=tools,
                    temperature=0.7).choices[0].message
                return msg, model
            except Exception as e:
                last_err = e
                print(f"   ...model {model} gagal ({type(e).__name__}), coba berikutnya")
                time.sleep(2)
    raise last_err

# ================= 6. LOOP OTONOM =================
def run(goal):
    print(f"\n🎯 TUGAS: {goal}\n{'='*60}")
    remember(f"tugas: {goal}")
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": goal}]
    for step in range(1, MAX_STEPS + 1):
        msg, model = ask_llm(msgs, SPEC)
        print(f"\n[step {step}] 🧠 otak: {model}")
        msgs.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            print(f"💬 {msg.content}")
            msgs.append({"role": "user",
                         "content": "Lanjutkan, atau panggil 'finish' jika selesai."})
            continue
        for tc in msg.tool_calls:
            name = tc.function.name
            arg = json.loads(tc.function.arguments).get("input", "")
            ok, verdict = guardrail(name, arg)
            print(f"🔧 {name}: {arg[:100]}")
            if not ok:
                result = f"⛔ DITOLAK - {verdict}"
            else:
                try:
                    result = TOOLS[name](arg)
                except Exception as e:
                    result = f"ERROR: {e}"
            print(f"   {verdict.upper()}: {str(result)[:150]}")
            audit(name, arg, verdict, result)
            msgs.append({"role": "tool", "tool_call_id": tc.id,
                         "content": str(result)[:3000]})
            if isinstance(result, str) and result.startswith("__SELESAI__"):
                print(f"\n🏁 SELESAI:\n{result[11:]}")
                remember(result[11:])
                print(session_stats())
                return
    print("⏹️ Batas langkah tercapai - agen berhenti dengan aman.")
    print(session_stats())

if __name__ == "__main__":
    run(input("🎯 Tugas untuk agen? "))
