from pathlib import Path
import json, re, sys, datetime
from collections import Counter, defaultdict

manifest_path = Path(sys.argv[1])    # out/YYYY/MM/DD/manifest.json
text_dir      = Path(sys.argv[2])    # out/YYYY/MM/DD/transcripts
sheet_out     = Path(sys.argv[3])    # out/daily/Gabriel_YYYY-MM-DD.md
onedrive_root = sys.argv[4]          # "Sales/Coaching/Gabriel"

# --- helpers ---
def load_manifest(p):
    if not p.exists(): return []
    data = json.loads(p.read_text(encoding="utf-8"))
    # coerce list if a single object
    return data if isinstance(data, list) else [data]

def read_texts(folder: Path):
    texts = {}
    for f in folder.glob("*.txt"):
        try:
            texts[f.stem] = f.read_text(encoding="utf-8")
        except Exception:
            pass
    return texts

def count_keywords(text, terms):
    text_l = text.lower()
    counts = {t: len(re.findall(r"\b" + re.escape(t.lower()) + r"\b", text_l)) for t in terms}
    return counts

def any_phrase(text, phrases):
    tl = text.lower()
    return any(p in tl for p in phrases)

def extract_followups(text):
    # crude cues for promised actions / scheduling
    cues = [
        r"\b(i('ll| will) (send|email|call|follow up|follow-up|reach out))\b",
        r"\b(we('ll| will) (send|email|call|follow up))\b",
        r"\b(can you email|please email|send me|share the proposal|share a quote)\b",
        r"\b(book(ed)? (it|for)|schedule(d)?|tomorrow|next (week|tuesday|wednesday|thursday|friday))\b",
    ]
    found = set()
    for line in text.splitlines():
        ll = line.strip()
        for pat in cues:
            if re.search(pat, ll, flags=re.I):
                # keep short, readable
                found.add(ll[:180])
                break
    return list(found)[:10]

# --- load data ---
items = load_manifest(manifest_path)
texts = read_texts(text_dir)
today = datetime.datetime.now(datetime.timezone.utc).astimezone().strftime("%Y-%m-%d")

total_calls = len(items)
total_secs  = sum(int(i.get("durationSec",0) or 0) for i in items)
avg_secs    = int(total_secs/total_calls) if total_calls else 0

inbound  = sum(1 for i in items if str(i.get("direction","")).lower() == "inbound")
outbound = sum(1 for i in items if str(i.get("direction","")).lower() == "outbound")

# Aggregate transcript text
combined = "\n".join(texts.values())

# Simple intent/objection heuristics
intent_terms    = ["meeting","meet","book","booking","demo","trial","quote","proposal","next step","follow up"]
ask_phrases     = ["can we book", "shall we book", "how about", "does tuesday work", "can i book", "let's schedule", "let us schedule"]
objection_buckets = {
    "Price":      ["too expensive","budget","cost","price","pricing"],
    "Timing":     ["busy","later","not now","q4","q1","after","next month","too soon"],
    "Authority":  ["need approval","my boss","decision maker","sign off","sign-off","committee"],
    "Competitor": ["we already use","switching from","competitor","alternative","another vendor"],
    "Fit":        ["not relevant","not a fit","don’t need","no need","covered already"]
}

intent_counts = count_keywords(combined, intent_terms) if combined else {t:0 for t in intent_terms}
ask_rate = 0
if combined:
    ask_rate = sum(1 for _ in re.finditer("|".join(map(re.escape, ask_phrases)), combined.lower()))

# Objection tallies per bucket
objections = {k: sum(count_keywords(combined, v).values()) if combined else 0
              for k,v in objection_buckets.items()}

# Follow-ups promised (snippets)
followups = []
for t in texts.values():
    followups.extend(extract_followups(t))
# de-dup while preserving order
seen = set(); followups = [x for x in followups if not (x in seen or seen.add(x))]

# Top calls to review (longest calls or high-intent)
def score_item(it):
    s = int(it.get("durationSec",0) or 0)
    stem = Path(str(it.get("file",""))).stem
    txt  = texts.get(stem, "")
    # boost if intent or objections present
    if any_phrase(txt, intent_terms): s += 180
    if any_phrase(txt, ["meeting","demo","quote","proposal"]): s += 240
    return s

top_calls = sorted(items, key=score_item, reverse=True)[:5]

# Recommendations logic (simple rules)
recs = []
if ask_rate == 0 and total_calls > 0:
    recs.append("Increase direct meeting asks — aim for **1–2 explicit asks per call** (try a clean 10-second CTA).")
elif ask_rate < max(1, total_calls//3):
    recs.append("Raise the meeting-ask frequency — target **~30–40%** of conversations to include a concrete scheduling ask.")
if objections.get("Price",0) >= 3:
    recs.append("Tighten value framing before price; lead with outcome + reference story, then budget.")
if objections.get("Authority",0) >= 2:
    recs.append("Early authority check — confirm decision process by minute 2 and propose a **joint follow-up** with the approver.")
if outbound > inbound and avg_secs < 120:
    recs.append("Lengthen qualifying on cold calls — shoot for **~3–4 minutes** with 3 discovery questions before the ask.")
if intent_counts.get("demo",0) + intent_counts.get("meeting",0) == 0 and total_calls > 0:
    recs.append("Trial a **two-line pitch** and a single outcome ask to simplify the close.")
if not recs:
    recs.append("Solid baseline — maintain structure; next step: test **time-boxed closes** (\"I have Tue 10:30 or 15:00 — which suits?\").")

# Build markdown
mins, secs = divmod(total_secs, 60)
body = []
body.append(f"# Gabriel — Daily Coaching Sheet ({today})\n")
body.append("## Summary")
body.append(f"- **Calls:** {total_calls}")
body.append(f"- **Talk time:** {mins}m {secs}s  |  **Avg/call:** {avg_secs}s")
body.append(f"- **Inbound/Outbound:** {inbound}/{outbound}")
body.append(f"- **Meeting ask count (approx):** {ask_rate}")
if total_calls == 0:
    body.append("\n_No eligible recordings today._\n")

body.append("\n## Signals")
if combined:
    top_intent = ", ".join([f"{k}×{v}" for k,v in sorted(intent_counts.items(), key=lambda x:-x[1]) if v>0][:6]) or "—"
    body.append(f"- **Intent keywords:** {top_intent}")
    if any(objections.values()):
        body.append("- **Objections (theme counts):** " + ", ".join([f"{k}×{v}" for k,v in objections.items() if v>0]))
else:
    body.append("- (Limited transcript signal today.)")

if followups:
    body.append("\n## Follow-ups promised today")
    for f in followups[:8]:
        body.append(f"- {f}")

body.append("\n## Top calls to review")
if top_calls:
    for it in top_calls:
        when = it.get("when","")
        dur  = it.get("durationSec",0)
        remote = it.get("remoteNumber","unknown")
        stem = Path(str(it.get("file",""))).stem
        text_name = stem + ".txt"
        body.append(f"- {when}  •  {remote}  •  {dur}s  •  transcript: `{text_name}`")
else:
    body.append("- —")

body.append("\n## Recommendations for tomorrow")
for r in recs:
    body.append(f"- {r}")

# Save
sheet_out.parent.mkdir(parents=True, exist_ok=True)
sheet_out.write_text("\n".join(body) + "\n", encoding="utf-8")
print(f"Wrote {sheet_out}")
