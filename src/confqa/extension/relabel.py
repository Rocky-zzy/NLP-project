"""Re-label Part 4 claims against the Wikipedia article (beyond the brief).

The first labeling pass asked the model from memory and proved unreliable on
obscure people. This pass grounds every verdict in retrieved text: fetch the
person's Wikipedia extract once, then judge the claims against it.

This is an extension the team added; it is not required by the project brief.

    python -m confqa.extension.relabel --clusters cache/ext/clusters.jsonl

Verdicts: supported | contradicted | absent | not_claim. Only "supported"
counts as correct, matching the FActScore convention. "not_claim" rows are
dropped from the metric because sentences like "more details are needed" are
not factual assertions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

WIKI_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "confqa-course-project/0.1 (educational research)"

PROMPT = """Below is a Wikipedia extract about {name} and a numbered list of claims.

For each claim decide:
- "supported": the extract states it, or clearly entails it
- "contradicted": the extract states something incompatible
- "absent": the extract does not cover it
- "not_claim": it is not a factual assertion (hedging, meta-commentary, opinion)

Return one JSON object per claim and nothing else:
{{"id": <number>, "verdict": "<one of the four>", "why": "<max 12 words>"}}

Wikipedia extract:
{extract}

Claims:
{claims}
"""


def api(params: dict) -> dict:
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_extract(name: str, cache_dir: Path, fetch: bool) -> tuple[str, str]:
    """Return (title, extract). Empty extract means the page was not found."""
    cache = cache_dir / (name.replace("/", "_").replace(" ", "_") + ".json")
    if cache.exists():
        saved = json.loads(cache.read_text(encoding="utf-8"))
        return saved["title"], saved["extract"]
    if not fetch:
        return "", ""
    try:
        found = api(
            {
                "action": "query",
                "list": "search",
                "srsearch": name,
                "format": "json",
                "srlimit": 1,
            }
        )
        hits = found["query"]["search"]
        if not hits:
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({"title": "", "extract": ""}), encoding="utf-8")
            return "", ""
        title = hits[0]["title"]
        page = api(
            {
                "action": "query",
                "prop": "extracts",
                "explaintext": 1,
                "redirects": 1,
                "format": "json",
                "titles": title,
            }
        )
        pages = page["query"]["pages"]
        extract = next(iter(pages.values())).get("extract", "")
    except Exception as exc:  # noqa: BLE001 - network variance is expected here
        print(f"  fetch failed for {name}: {exc}", file=sys.stderr)
        return "", ""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"title": title, "extract": extract}), encoding="utf-8")
    return title, extract


def call_model(base_url: str, model: str, prompt: str, timeout: float = 180.0) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 700,
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"]


def parse_verdicts(raw: str, expected: list[int]) -> dict[int, tuple[str, str]]:
    out: dict[int, tuple[str, str]] = {}
    for line in raw.splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
            out[int(row["id"])] = (str(row["verdict"]), str(row.get("why", "")))
        except (json.JSONDecodeError, KeyError, ValueError):
            continue
    missing = [cid for cid in expected if cid not in out]
    if missing:
        raise ValueError(f"missing verdicts: {missing}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clusters", default="cache/ext/clusters.jsonl")
    parser.add_argument("--names", default="data/factscore_names.txt")
    parser.add_argument("--out", default="cache/ext/labels_wiki.jsonl")
    parser.add_argument("--cache-dir", default="cache/wiki")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="qwen2.5-14b-instruct")
    parser.add_argument("--max-chars", type=int, default=3000, help="fits the 2048-token context")
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args(argv)

    names = [
        n.strip() for n in Path(args.names).read_text(encoding="utf-8").splitlines() if n.strip()
    ]
    by_pid: dict[str, list[dict]] = defaultdict(list)
    for line in Path(args.clusters).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        by_pid[row["pid"]].append(row)

    labels, no_source, stats = [], [], defaultdict(int)
    started = time.perf_counter()
    for index, pid in enumerate(sorted(by_pid)):
        name = names[int(pid.split("-")[1])]
        title, extract = fetch_extract(name, Path(args.cache_dir), not args.no_fetch)
        claims = sorted(by_pid[pid], key=lambda r: r["cid"])
        if not extract:
            no_source.append({"pid": pid, "name": name})
            for claim in claims:
                labels.append(
                    {
                        "pid": pid,
                        "cid": claim["cid"],
                        "verdict": "no_source",
                        "why": "",
                        "title": title,
                    }
                )
            print(f"[{index + 1}/{len(by_pid)}] {name}: no page")
            continue
        body = "\n".join(f"{c['cid']}: {c['text']}" for c in claims)
        try:
            raw = call_model(
                args.base_url,
                args.model,
                PROMPT.format(name=name, extract=extract[: args.max_chars], claims=body),
            )
        except urllib.error.HTTPError as exc:
            if exc.code != 400:
                raise
            print(f"[{pid}] context too long; retrying with half the extract", file=sys.stderr)
            raw = call_model(
                args.base_url,
                args.model,
                PROMPT.format(name=name, extract=extract[: args.max_chars // 2], claims=body),
            )
        try:
            verdicts = parse_verdicts(raw, [c["cid"] for c in claims])
        except ValueError as exc:
            print(f"[{pid}] unusable: {exc}", file=sys.stderr)
            continue
        for claim in claims:
            verdict, why = verdicts[claim["cid"]]
            labels.append(
                {"pid": pid, "cid": claim["cid"], "verdict": verdict, "why": why, "title": title}
            )
            stats[verdict] += 1
        print(f"[{index + 1}/{len(by_pid)}] {name}: {len(claims)} claims")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in labels),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"wrote {out}: {len(labels)} rows, {dict(stats)}, "
        f"{len(no_source)} people without a page, {time.perf_counter() - started:.0f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
