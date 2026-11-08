"""Label the Part 4 target claims with an LLM judge.

There is no retrieval corpus for these biographies, so correctness is a proxy:
the generator model is asked, once per prompt, which of its claims are true.
Both scoring methods are evaluated against the same labels, so the comparison
is internally consistent. Report the human agreement rate next to any result.

    python -m confqa.extension.label \
        --clusters cache/ext/clusters.jsonl \
        --out cache/ext/labels.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import threading
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

PROMPT = """You are fact-checking a short biography.

Decide for each numbered claim whether it is factually correct. Use only what
you actually know; if a claim is about an obscure detail you cannot verify,
mark it false.

Return one JSON object per claim, nothing else:
{"id": <claim number>, "correct": true or false}

Claims:
{claims}
"""


class Client:
    def __init__(self, base_url: str, timeout: float = 180.0) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.calls = 0

    def complete(self, prompt: str, model: str, max_tokens: int = 800) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        request = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
        self.calls += 1
        return body["choices"][0]["message"]["content"]


def parse_verdicts(raw: str, expected: list[int]) -> dict[int, bool]:
    out: dict[int, bool] = {}
    for line in raw.splitlines():
        line = line.strip().strip(",")
        if not line.startswith("{"):
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            match = re.search(r'\{"id"\s*:\s*(\d+).*?"correct"\s*:\s*(true|false)', line)
            if not match:
                continue
            out[int(match.group(1))] = match.group(2) == "true"
            continue
        out[int(row["id"])] = bool(row["correct"])
    missing = [cid for cid in expected if cid not in out]
    if missing:
        raise ValueError(f"missing verdicts for {missing}")
    return out


class Progress:
    def __init__(self, client: Client, every: float = 20.0) -> None:
        self.client = client
        self.every = every
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        started = time.perf_counter()
        while not self._stop.wait(self.every):
            print(f"  calls={self.client.calls} {time.perf_counter() - started:.0f}s", flush=True)

    def __enter__(self) -> Progress:
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clusters", default="cache/ext/clusters.jsonl")
    parser.add_argument("--out", default="cache/ext/labels.jsonl")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="qwen2.5-14b-instruct")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    rows = [
        json.loads(line) for line in Path(args.clusters).read_text(encoding="utf-8").splitlines()
    ]
    by_pid: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_pid[row["pid"]].append(row)
    pids = sorted(by_pid)[: args.limit]

    client = Client(args.base_url)
    labels, failures = [], 0
    started = time.perf_counter()
    with Progress(client):
        for index, pid in enumerate(pids):
            claims = sorted(by_pid[pid], key=lambda r: r["cid"])
            body = "\n".join(f"{c['cid']}: {c['text']}" for c in claims)
            raw = client.complete(PROMPT.replace("{claims}", body), args.model)
            try:
                verdicts = parse_verdicts(raw, [c["cid"] for c in claims])
            except ValueError as exc:
                failures += 1
                print(f"[{pid}] judge output unusable: {exc}", file=sys.stderr)
                continue
            for claim in claims:
                labels.append({"pid": pid, "cid": claim["cid"], "correct": verdicts[claim["cid"]]})
            print(f"[{index + 1}/{len(pids)}] {pid}: {len(claims)} claims")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(row) + "\n" for row in labels), encoding="utf-8", newline="\n"
    )
    total = len(labels)
    print(
        f"wrote {out}: {total} labels, true={sum(r['correct'] for r in labels)}, "
        f"failures={failures}, calls={client.calls}, {time.perf_counter() - started:.0f}s"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
