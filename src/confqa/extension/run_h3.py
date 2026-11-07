"""Run the H3 claim pipeline against the local vLLM server.

Splits each generated response into claims, judges every target claim against
each comparison response, and writes the frequency baseline that the Part 4
extension is compared against.

    python -m confqa.extension.run_h3 \
        --base-url http://127.0.0.1:8000/v1 \
        --out-dir cache/h3 --targets 0
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from confqa.factuality.h3 import load_ext_responses, run_h3


class VLLMClient:
    """ChatClient backed by the OpenAI-compatible endpoint."""

    def __init__(self, base_url: str, timeout: float = 300.0, retries: int = 3) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.retries = retries
        self.calls = 0

    def complete(self, messages, *, model, temperature=0.0, max_tokens=1000) -> str:
        payload = {
            "model": model,
            "messages": list(messages),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
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
            except Exception as exc:  # noqa: BLE001 - surfaced after the last retry
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"request failed after {self.retries} attempts: {last_error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="qwen2.5-14b-instruct")
    parser.add_argument("--input", default="cache/ext_responses.jsonl")
    parser.add_argument("--out-dir", default="cache/h3")
    parser.add_argument("--targets", default="0", help="comma separated response ids")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    records = load_ext_responses(args.input)
    if args.limit:
        records = records[: args.limit]
    targets = [int(x) for x in args.targets.split(",") if x.strip()]

    client = VLLMClient(args.base_url)
    started = time.perf_counter()
    summary = run_h3(
        records,
        client,
        output_dir=args.out_dir,
        model=args.model,
        target_response_ids=targets,
    )
    elapsed = time.perf_counter() - started

    print(
        f"prompts={summary.prompts} splits={summary.split_responses} "
        f"target_rows={summary.target_rows} failures={summary.failure_rows} "
        f"calls={client.calls} elapsed={elapsed:.0f}s"
    )
    meta = {
        "model": args.model,
        "input": args.input,
        "targets": targets,
        "prompts": summary.prompts,
        "split_responses": summary.split_responses,
        "target_rows": summary.target_rows,
        "failure_rows": summary.failure_rows,
        "calls": client.calls,
        "elapsed_s": round(elapsed, 1),
    }
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "run_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    if summary.failure_rows:
        print(f"{summary.failure_rows} failures recorded", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
