"""MiMo-AutoAgent v2 — ketekunan agen otonom + otak Xiaomi MiMo + guardrail permanen."""
import json, os, re, sqlite3, subprocess, sys, time, datetime
from urllib.parse import urlparse
try:
    from dotenv import load_dotenv; load_dotenv()
except ImportError:
    pass
from openai import OpenAI

# ---------- KONFIG ----------
MODEL    = os.environ.get("MODEL", "xiaomi/mimo-v2.5-pro")
API_KEY  = os.environ.get("OPENROUTER_API_KEY")
BASE_URL = os.environ.get("BASE_URL", "https://openrouter.ai/api/v1")
MAX_STEPS = int(os.environ.get("MAX_STEPS", "30"))
ALLOWED_HOSTS = {"localhost", "127.0.0.1", "openrouter.ai", "api.openrouter.ai",
                 "huggingface.co", "id.wikipedia.org"}   # tambah situs aman milikmu
if not API_KEY:
    sys.exit("❌ OPENROUTER_API_KEY belum diisi. Buat file .env (lihat .env.example).")
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

# ---------- GUARDRAIL (tidak bisa dimatikan) ----------
FORBIDDEN = [
    r"169\.254\.169\.254",                                    # metadata cloud
    r"\brm\s+-rf\b|\bmkfs\b|:\s*$$\s*\{",                   # destruktif / fork bomb
    r"(password|secret|token|api[_-]?key)\s*=\s*['\"]?\S{8,}", # bocorkan kredensial
]
def guardrail(action, arg):
    for p in FORBIDDEN:
        if re.search(p, arg, re.I):
            return False, f"pola terlarang: {p}"
    if action == "web_read":
        host = urlparse(arg).hostname or ""
        if host not in ALLOWED_HOSTS:
            return False, f"host '{host}' di luar ALLOWED_HOSTS"
    if action in ("shell", "python") and not os.path.exists("lab_mode.txt"):
        return False, "mode eksekusi terkunci: buat file lab_mode.txt sebagai izin eksplisitmu"
    return True, "ok"

# ---------- MEMORI & AUDIT ----------
db = sqlite3.connect("agent_memory.db")
db.executescript("""
CREATE TABLE IF NOT EXISTS memory(id INTEGER PRIMARY KEY, ts TEXT, content TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, ts TEXT, action TEXT,
               arg TEXT, verdict TEXT, result TEXT);""")
def remember(t):
    db.execute("INSERT INTO memory(ts,content) VALUES(?,?)",
               (datetime.datetime.now().isoformat(), t)); db.commit()
def recall(q):
    rows = db.execute("SELECT content FROM memory WHERE content LIKE ? "
                      "ORDER BY id DESC LIMIT 5", (f"%{q}%",)).fetchall()
    return "\n".join(r[0] for r in rows) or "(belum ada memori)"
def audit(a, g, v, r):
    db.execute("INSERT INTO audit(ts,action,arg,verdict,result) VALUES(?,?,?,?,?)",
               (datetime.datetime.now().isoformat(), a, g[:200], v, str(r)[:500]))
    db.commit()

# ---------- TOOLS ----------
def t_shell(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True, timeout=30).stdout[:2000]
def t_python(code):
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, timeout=60).stdout[:2000]
def t_web(url):
    import requests
    return requests.get(url, timeout=15,
                        headers={"User-Agent": "MiMo-AutoAgent/2.0"}).text[:3000]
TOOLS = {"think": lambda t: f"[pikiran tercatat] {t}",
         "remember": lambda t: (remember(t), f"disimpan: {t}")[1],
         "recall": recall, "shell": t_shell, "python": t_python,
         "web_read": t_web, "finish": lambda s: f"__SELESAI__{s}"}
SPEC = [{"type": "function", "function": {"name": n, "description": d,
         "parameters": {"type": "object",
                        "properties": {"input": {"type": "string"}},
                        "required": ["input"]}}}
        for n, d in {
    "think": "Bernalar tentang langkah berikutnya tanpa aksi",
    "remember": "Simpan temuan penting ke memori jangka panjang",
    "recall": "Cari memori lama berdasarkan kata kunci",
    "shell": "Jalankan perintah shell (butuh lab_mode.txt)",
    "python": "Tulis & jalankan skrip Python sendiri (butuh lab_mode.txt)",
    "web_read": "Baca halaman web dari ALLOWED_HOSTS",
    "finish": "Akhiri tugas dengan ringkasan final"}.items()]

SYSTEM = """Kamu MiMo-AutoAgent v2: agen otonom yang tekun, kreatif, dan transparan.
Cara kerja: amati → pikir → aksi → pelajari hasil → ulangi sampai selesai.
Jika satu cara gagal, coba cara lain; kamu boleh menulis skrip Python sendiri.
Simpan temuan penting dengan 'remember'; ambil memori lama dengan 'recall'.
ATURAN MUTLAK: patuhi guardrail (jika ditolak, cari jalan sah lain); jangan sentuh
sistem di luar izin user; jelaskan reasoning-mu di setiap langkah."""

# ---------- LOOP OTONOM ----------
def run(goal):
    print(f"\n🎯 TUGAS: {goal}\n{'='*60}")
    remember(f"tugas: {goal}")
    msgs = [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": goal}]
    for step in range(1, MAX_STEPS + 1):
        for attempt in range(3):                       # retry jika API gagal
            try:
                msg = client.chat.completions.create(
                    model=MODEL, messages=msgs, tools=SPEC,
                    temperature=0.7).choices[0].message
                break
            except Exception as e:
                if attempt == 2: raise
                print(f"⚠️ retry API ({attempt+1}): {e}"); time.sleep(3*(attempt+1))
        msgs.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            print(f"\n💬 [step {step}] {msg.content}")
            msgs.append({"role": "user",
                         "content": "Lanjutkan, atau panggil 'finish' jika selesai."})
            continue
        for tc in msg.tool_calls:
            name = tc.function.name
            arg = json.loads(tc.function.arguments).get("input", "")
            ok, verdict = guardrail(name, arg)
            print(f"\n[step {step}] 🔧 {name}: {arg[:100]}")
            if not ok:
                result = f"⛔ DITOLAK — {verdict}"
            else:
                try: result = TOOLS[name](arg)
                except Exception as e: result = f"ERROR: {e}"
            print(f"    {verdict.upper()}: {str(result)[:150]}")
            audit(name, arg, verdict, result)
            msgs.append({"role": "tool", "tool_call_id": tc.id,
                         "content": str(result)[:3000]})
            if isinstance(result, str) and result.startswith("__SELESAI__"):
                print(f"\n🏁 SELESAI:\n{result[11:]}"); remember(result[11:]); return
    print("⏹️ Batas langkah tercapai — agen berhenti dengan aman.")

if __name__ == "__main__":
    run(input("🎯 Tugas untuk agen? "))
