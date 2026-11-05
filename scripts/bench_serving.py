#!/usr/bin/env python3
"""Measure the local vLLM endpoint under the real ConU workload shape.

The ConU pipeline needs 500 prompts x 20 samples at temperature 1.0. Before
spending GPU hours on that, measure what the current server configuration can
actually do.

    python bench_serving.py --num-prompts 20 --n 20

Everything is standard library, so it runs inside the HPC env without extra
installs. Results go to stdout and to --out (json).
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

DEFAULT_PROMPTS = [
    'Who wrote the novel "The Golden Notebook"?',
    "What is the capital of Australia?",
    "Who painted the Mona Lisa?",
    "Which planet is known as the Red Planet?",
    "Who composed the Ninth Symphony?",
    "What is the largest ocean on Earth?",
    "Who invented the telephone?",
    "In which year did the Berlin Wall fall?",
    "What is the currency of Japan?",
    'Who wrote "Pride and Prejudice"?',
    "What is the chemical symbol for gold?",
    "Which country hosted the 2016 Summer Olympics?",
    "Who was the first person to walk on the moon?",
    "What is the longest river in Africa?",
    "Who discovered penicillin?",
    "What is the smallest prime number?",
    "Which language has the most native speakers?",
    'Who directed the film "Jaws"?',
    "What is the boiling point of water at sea level in Celsius?",
    "Which element has atomic number 1?",
]


def load_prompts(path: str | None, count: int) -> list[str]:
    if path is None:
        prompts = list(DEFAULT_PROMPTS)
    else:
        raw = Path(path).read_text(encoding="utf-8").strip()
        if raw.startswith("["):
            items = json.loads(raw)
        else:
            items = [json.loads(line) for line in raw.splitlines() if line.strip()]
        prompts = []
        for item in items:
            prompts.append(item if isinstance(item, str) else str(item.get("question", item)))
    if count > len(prompts):
        prompts = [prompts[i % len(prompts)] for i in range(count)]
    return prompts[:count]


def post_chat(base_url: str, payload: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def request_once(args, prompt: str, seed: int) -> dict:
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "n": args.n,
        "seed": seed,
    }
    started = time.perf_counter()
    body = post_chat(args.base_url, payload, args.timeout)
    elapsed = time.perf_counter() - started
    choices = body.get("choices", [])
    usage = body.get("usage", {}) or {}
    return {
        "prompt": prompt,
        "latency_s": elapsed,
        "n_returned": len(choices),
        "contents": [c.get("message", {}).get("content", "") for c in choices],
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }


def percentiles(values: list[float]) -> dict:
    if not values:
        return {"mean": None, "p50": None, "p95": None, "max": None}
    ordered = sorted(values)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    return {
        "mean": statistics.fmean(ordered),
        "p50": ordered[len(ordered) // 2],
        "p95": p95,
        "max": ordered[-1],
    }


def uniqueness(contents: list[str]) -> float:
    normalized = {c.strip().lower() for c in contents if c.strip()}
    return len(normalized) / len(contents) if contents else 0.0


class GpuSampler:
    """Poll nvidia-smi in a thread; MIG hosts may answer N/A, which is fine."""

    def __init__(self, interval: float = 0.5) -> None:
        self.interval = interval
        self.samples: list[int] = []
        self.raw_last: str | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                proc = subprocess.run(
                    ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                first = proc.stdout.strip().splitlines()[0].strip()
                self.raw_last = first
                if first.isdigit():
                    self.samples.append(int(first))
            except (OSError, subprocess.SubprocessError, IndexError, ValueError):
                pass
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def summary(self) -> dict:
        return {
            "samples": len(self.samples),
            "peak_mib": max(self.samples) if self.samples else None,
            "median_mib": statistics.median(self.samples) if self.samples else None,
            "raw_last": self.raw_last,
        }


def build_report(args, results: list[dict], elapsed: float, gpu: dict) -> dict:
    latencies = [r["latency_s"] for r in results]
    prompt_tokens = sum(r["prompt_tokens"] or 0 for r in results)
    completion_tokens = sum(r["completion_tokens"] or 0 for r in results)
    uniq = [uniqueness(r["contents"]) for r in results]
    degenerate = 0
    if args.n > 1:
        threshold = 1.0 / args.n
        degenerate = sum(1 for r in results if uniqueness(r["contents"]) <= threshold)

    per_request = statistics.fmean(latencies) if latencies else 0.0
    return {
        "config": {
            "base_url": args.base_url,
            "model": args.model,
            "num_prompts": len(results),
            "n": args.n,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "concurrency": args.concurrency,
        },
        "elapsed_s": elapsed,
        "requests": len(results),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "output_tokens_per_s": completion_tokens / elapsed if elapsed else None,
        "total_tokens_per_s": (prompt_tokens + completion_tokens) / elapsed if elapsed else None,
        "latency_s": percentiles(latencies),
        "seconds_per_request": per_request,
        "unique_fraction_mean": statistics.fmean(uniq) if uniq else None,
        "all_identical_requests": degenerate,
        "gpu": gpu,
        "projected": {
            "conu_500x20_hours": per_request * 500 * 20 / max(1, args.concurrency) / 3600,
            "extension_50x5_minutes": per_request * 50 * 5 / max(1, args.concurrency) / 60,
        },
    }


def run_all(args, prompts: list[str]) -> tuple[list[dict], float]:
    started = time.perf_counter()
    if args.concurrency <= 1:
        results = [request_once(args, p, args.seed + i) for i, p in enumerate(prompts)]
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(request_once, args, p, args.seed + i) for i, p in enumerate(prompts)
            ]
            results = [future.result() for future in futures]
    return results, time.perf_counter() - started


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="qwen2.5-14b-instruct")
    parser.add_argument("--num-prompts", type=int, default=20)
    parser.add_argument("--n", type=int, default=20, help="samples per prompt")
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--prompts-file", default=None)
    parser.add_argument("--out", default="bench_result.json")
    parser.add_argument("--no-gpu-sample", action="store_true")
    args = parser.parse_args(argv)

    prompts = load_prompts(args.prompts_file, args.num_prompts)

    for i in range(args.warmup):
        request_once(args, prompts[i % len(prompts)], args.seed + i)

    if args.no_gpu_sample:
        results, elapsed = run_all(args, prompts)
        gpu = {"samples": 0, "peak_mib": None, "median_mib": None, "raw_last": None}
    else:
        with GpuSampler() as sampler:
            results, elapsed = run_all(args, prompts)
            gpu = sampler.summary()

    report = build_report(args, results, elapsed, gpu)
    Path(args.out).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )

    print(f"requests={report['requests']} n={args.n} elapsed={elapsed:.1f}s")
    print(f"output tokens/s = {report['output_tokens_per_s']:.1f}")
    print(
        f"latency p50/p95 = {report['latency_s']['p50']:.2f}s / {report['latency_s']['p95']:.2f}s"
    )
    print(f"unique fraction = {report['unique_fraction_mean']:.2f}")
    print(f"projected 500x20 = {report['projected']['conu_500x20_hours']:.2f} h")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
