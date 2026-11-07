"""Generate five responses per FActScore prompt from the local vLLM server.

Part 4 needs its own generations: the cached upstream outputs belong to the
factuality baseline, and the extension must be compared at the same sampling
budget on responses we produced ourselves.

    python -m confqa.extension.generate \
        --base-url http://127.0.0.1:8000/v1 \
        --out cache/ext_responses.jsonl

The prompt set comes from the committed split file, so it is fixed before any
output is inspected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

DEFAULT_NAMES = "data/factscore_names.txt"
DEFAULT_SPLIT = "data/splits/factscore.json"
TEMPLATE = "Tell me a paragraph bio of {name}"


def read_names(path: Path) -> list[str]:
    names = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [name for name in names if name]


def post(base_url: str, payload: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def sample_one(args, prompt: str, seed: int, attempt: int = 0) -> list[str]:
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "n": args.n,
        "seed": seed,
    }
    body = post(args.base_url, payload, args.timeout)
    texts = [c.get("message", {}).get("content", "").strip() for c in body.get("choices", [])]
    texts = [t for t in texts if t]
    if len(texts) < args.n and attempt < args.max_retries:
        print(f"  short sample ({len(texts)}/{args.n}), retrying", file=sys.stderr)
        return sample_one(args, prompt, seed, attempt + 1)
    if len(texts) < args.n:
        raise RuntimeError(f"only {len(texts)} non-empty responses for seed {seed}")
    return texts[: args.n]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="qwen2.5-14b-instruct")
    parser.add_argument("--names", default=DEFAULT_NAMES)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=220)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default="cache/ext_responses.jsonl")
    args = parser.parse_args(argv)

    names = read_names(Path(args.names))
    split = json.loads(Path(args.split).read_text(encoding="utf-8"))
    ids = sorted(split["splits"]["test"] + split["splits"]["dev"] + split["splits"]["calib_pool"])
    if len(ids) > len(names):
        raise ValueError("split has more ids than the name list")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    targets = ids[: args.limit] if args.limit else ids
    records = []
    for index, pid in enumerate(targets):
        name = names[int(pid.split("-")[1])]
        prompt = TEMPLATE.format(name=name)
        responses = sample_one(args, prompt, args.seed + index)
        records.append({"pid": pid, "prompt": prompt, "responses": responses})
        print(f"[{index + 1}/{len(targets)}] {pid} {name}")

    out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8",
        newline="\n",
    )
    meta = {
        "model": args.model,
        "n": args.n,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "seed": args.seed,
        "prompts": len(records),
        "elapsed_s": round(time.perf_counter() - started, 1),
        "output_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }
    out.with_suffix(".meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {out} ({len(records)} prompts) in {meta['elapsed_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
