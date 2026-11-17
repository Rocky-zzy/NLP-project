
import json, time, urllib.parse, urllib.request
from pathlib import Path

root = Path(r"C:\Users\27059\Desktop\Files and Subjects\26Autumn学习资料\NLP\NLP-project")
out_dir = Path(r"C:\Users\27059\Desktop\Files and Subjects\26Autumn学习资料\NLP\pilot-artifacts")
out_dir.mkdir(exist_ok=True)

opener = urllib.request.build_opener(
    urllib.request.ProxyHandler({"https": "http://127.0.0.1:7897", "http": "http://127.0.0.1:7897"}))
opener.addheaders = [("User-Agent", "confqa-research-pilot/1.0 (course project)")]

def get(url):
    for attempt in range(3):
        try:
            with opener.open(url, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 2:
                return None
            time.sleep(1.5 * (attempt + 1))

names = [l.strip() for l in (root / "data/factscore_names.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
PROPS = {"P31": "instance_of", "P569": "birth", "P570": "death", "P106": "occupation",
         "P108": "employer", "P39": "position", "P166": "award", "P19": "birthplace",
         "P20": "deathplace", "P27": "citizenship", "P69": "education"}

results = []
for i, name in enumerate(names):
    rec = {"name": name}
    s = get("https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json&language=en&limit=3&search=" + urllib.parse.quote(name))
    if not s:
        rec["error"] = "search failed"
        results.append(rec); continue
    hits = s.get("search", [])
    rec["search_hits"] = [(h["id"], h.get("description", "")) for h in hits]
    if not hits:
        rec["qid"] = None
        results.append(rec); continue
    qid = hits[0]["id"]; rec["qid"] = qid
    e = get("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json&props=labels|descriptions|claims&languages=en&ids=" + qid)
    if not e:
        rec["error"] = "entity fetch failed"
        results.append(rec); continue
    ent = e["entities"][qid]
    rec["description"] = ent.get("descriptions", {}).get("en", {}).get("value", "")
    claims = ent.get("claims", {})
    rec["n_statements"] = sum(len(v) for v in claims.values())
    rec["props"] = {label: (claims.get(pid, []) != []) for pid, label in PROPS.items()}
    results.append(rec)
    if i % 10 == 0:
        print(f"{i}/{len(names)}", flush=True)

(out_dir / "wikidata_pilot.json").write_text(
    json.dumps({"retrieved": "2026-11-17", "source": "wikidata wbsearchentities+wbgetentities",
                "n_names": len(names), "records": results}, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", len(results))
