import math
import os
import re
from collections import Counter
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODELS = [
    m.strip()
    for m in os.getenv(
        "OPENROUTER_MODEL",
        "google/gemma-4-31b-it:free,google/gemma-4-26b-a4b-it:free,nvidia/nemotron-3.5-lightning:free,inclusionai/ling-3.2-flash:free",
    ).split(",")
    if m.strip()
]

SYSTEM = (
    "You are an assistant for two real estate companies: DarGlobal (luxury developer) and Wasalt "
    "(Saudi PropTech listings platform). Answer ONLY from the CONTEXT passages given. If the context "
    "does not contain the answer, say you do not have that information. Mention which company a fact "
    "belongs to. Prices for Wasalt listings are in SAR. Keep answers short and factual."
)

TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text: str):
    return TOKEN.findall(text.lower())


MAX_CHARS = 1100


def split_text(text: str):
    """Split a long section into pieces of at most MAX_CHARS on sentence boundaries."""
    if len(text) <= MAX_CHARS:
        return [text]
    parts, cur = [], ""
    for sent in re.split(r"(?<=[.;])\s+", text):
        if cur and len(cur) + len(sent) > MAX_CHARS:
            parts.append(cur)
            cur = ""
        cur = (cur + " " + sent).strip()
    if cur:
        parts.append(cur)
    return parts


def load_chunks():
    chunks = []
    for path in sorted(DATA_DIR.glob("*.md")):
        source = path.stem
        title, buf = "", []

        def flush():
            body = " ".join(buf).strip()
            for n, piece in enumerate(split_text(body), 1):
                label = title if n == 1 else f"{title} (part {n})"
                chunks.append({"source": source, "title": label, "text": f"{title}. {piece}"})

        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                flush()
                title, buf = line[3:].strip(), []
            elif not line.startswith("# "):
                buf.append(line.strip())
        flush()
    return chunks


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [Counter(tokens(d)) for d in docs]
        self.len = [sum(c.values()) for c in self.docs]
        self.avg = sum(self.len) / max(len(self.len), 1)
        self.k1, self.b = k1, b
        df = Counter()
        for c in self.docs:
            df.update(c.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def top(self, query, k=4):
        q = tokens(query)
        scores = []
        for i, c in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t in c:
                    f = c[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
            scores.append((s, i))
        scores.sort(reverse=True)
        return [i for s, i in scores[:k] if s > 0]


CHUNKS = load_chunks()
INDEX = BM25([c["text"] for c in CHUNKS])

app = FastAPI(title="DarGlobal + Wasalt chatbot")


class Ask(BaseModel):
    message: str
    history: list[dict] = []


@app.get("/health")
def health():
    return {"ok": True, "chunks": len(CHUNKS), "models": MODELS, "key_set": bool(os.getenv("OPENROUTER_API_KEY"))}


async def call_llm(messages):
    key = os.getenv("OPENROUTER_API_KEY", "")
    if not key:
        return None, "no key"
    last = ""
    async with httpx.AsyncClient(timeout=60) as client:
        for model in MODELS:
            try:
                r = await client.post(
                    OPENROUTER_URL,
                    headers={"Authorization": f"Bearer {key}", "X-Title": "DarGlobal Wasalt chatbot"},
                    json={"model": model, "messages": messages, "temperature": 0.2},
                )
                if r.status_code == 200:
                    return r.json()["choices"][0]["message"]["content"], model
                last = f"{model}: HTTP {r.status_code}"
            except Exception as e:  # try the next free model
                last = f"{model}: {e}"
    return None, last


@app.post("/api/chat")
async def chat(req: Ask):
    ids = INDEX.top(req.message, k=5)
    passages = [CHUNKS[i] for i in ids]
    context = "\n\n".join(f"[{p['source']} / {p['title']}]\n{p['text']}" for p in passages)
    messages = [{"role": "system", "content": SYSTEM}]
    for h in req.history[-6:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {req.message}"})
    answer, info = await call_llm(messages)
    if answer is None:
        answer = "The language model is unavailable right now (" + info + "). Closest passages from the scraped data:\n\n" + "\n\n".join(
            p["text"][:500] for p in passages
        )
        info = "retrieval-only"
    return {"answer": answer, "model": info, "sources": [f"{p['source']}: {p['title']}" for p in passages]}


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


PAGE = """<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>DarGlobal + Wasalt Assistant</title>
<style>body{font-family:system-ui;margin:0;background:#f5f5f7}main{max-width:760px;margin:auto;padding:16px}
h1{font-size:20px}#log{background:#fff;border-radius:12px;padding:12px;min-height:320px;max-height:60vh;overflow:auto}
.u{background:#e8f0fe;border-radius:10px;padding:8px 12px;margin:8px 0 8px 15%}.a{background:#f1f3f4;border-radius:10px;padding:8px 12px;margin:8px 15% 8px 0;white-space:pre-wrap}
small{color:#666}form{display:flex;gap:8px;margin-top:12px}input{flex:1;padding:12px;border:1px solid #ccc;border-radius:10px}
button{padding:12px 18px;border:0;border-radius:10px;background:#1a1a1a;color:#fff;cursor:pointer}.chips button{background:#fff;color:#222;border:1px solid #ccc;margin:4px 4px 0 0;padding:6px 10px;font-size:13px}</style></head>
<body><main><h1>DarGlobal + Wasalt Assistant</h1>
<small>Answers come from scraped public data (Wasalt listings, DarGlobal profile). Model via OpenRouter.</small>
<div class=chips id=chips></div><div id=log></div>
<form id=f><input id=q placeholder="Ask about DarGlobal projects or Wasalt listings" autocomplete=off><button>Send</button></form></main>
<script>
const log=document.getElementById('log'),q=document.getElementById('q');let hist=[];
['What is Dar Global?','Which projects does Dar Global have in Oman and Qatar?','What is Wasalt?','Show villas for sale in Jeddah','Cheapest apartments for sale in Madinah']
.forEach(t=>{const b=document.createElement('button');b.type='button';b.textContent=t;b.onclick=()=>{q.value=t;f.requestSubmit()};chips.appendChild(b)});
function add(c,t){const d=document.createElement('div');d.className=c;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;return d}
f.onsubmit=async e=>{e.preventDefault();const m=q.value.trim();if(!m)return;q.value='';add('u',m);const w=add('a','...');
try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:m,history:hist})});
const j=await r.json();w.textContent=j.answer+'\\n\\n['+j.model+'] sources: '+j.sources.join('; ');hist.push({role:'user',content:m},{role:'assistant',content:j.answer})}
catch(x){w.textContent='Error: '+x}};
</script></body></html>"""
