#!/usr/bin/env python3
"""Prepare a local sampling plan; only --run can query the existing vLLM server."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000"
MODEL = "qwen2.5-14b-instruct"
N_SAMPLES = 5
MAX_NEW_TOKENS = 36
CONTEXT_LIMIT = 2048
SEED = 10
BAD_WORDS = ["### User:", "### Assistant:", "### System:", "User:", "Assistant:", "System:", "###"]
SOURCE_SHA256 = "48a5005c0eb4f8a4ae5b9868644297fd5bf1e694aeb3dc9c8ab958cac0d5b201"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, data: bytes, *, immutable: bool = False) -> None:
    if path.is_symlink():
        raise ValueError(f"Refusing symlink: {path}")
    if immutable and path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"Refusing to replace different saved data: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".a2-writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_bytes() != data:
                    raise ValueError(f"Saved data changed concurrently: {path}")
        else:
            os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_prompt(record: dict, demos: list[dict]) -> str:
    prefix = "### System:\nThis is a bot that correctly answers questions.\n\n"
    prefix += "".join("### User:\n" + r["question"] + "\n### Assistant:\n" + r["gold_value"] + "\n\n" for r in demos)
    return prefix + "### User:\n" + record["question"] + "\n### Assistant:\n"


def load_inputs(project: Path) -> tuple[list[dict], list[dict], dict, dict, str]:
    prefix = "data/processed/triviaqa_a2"
    preparation_path = project / prefix / "manifest.json"
    preparation = read_json(preparation_path)
    if preparation.get("source", {}).get("sha256") != SOURCE_SHA256:
        raise ValueError("Unexpected prepared data source.")
    paths = [f"{prefix}/questions.jsonl", f"{prefix}/few_shot.jsonl", "data/splits/triviaqa_a2_pilot.json"]
    values = []
    for name in paths:
        content = (project / name).read_bytes()
        if digest(content) != preparation["artifacts"][name]["sha256"]:
            raise ValueError(f"Prepared artifact hash mismatch: {name}")
        values.append([json.loads(s) for s in content.decode("utf-8").splitlines()] if name.endswith("jsonl") else json.loads(content))
    questions, demos, split = values
    qids = [r["qid"] for r in questions]
    if not 1 <= len(questions) <= 50 or len(set(qids)) != len(qids):
        raise ValueError("Pilot question count/uniqueness check failed.")
    if len(demos) != 3 or len({r["qid"] for r in demos}) != 3:
        raise ValueError("Expected three distinct few-shot examples.")
    if qids != split["generation_order"]:
        raise ValueError("Question order differs from the fixed split.")
    calibration, test = set(split["calibration_ids"]), set(split["test_ids"])
    if calibration & test or calibration | test != set(qids):
        raise ValueError("Calibration/test IDs are overlapping or incomplete.")
    if set(qids) & {r["qid"] for r in demos}:
        raise ValueError("A few-shot example appears in the pilot.")
    return questions, demos, split, preparation, digest(preparation_path.read_bytes())


def failed_plan(project: Path) -> tuple[dict, dict]:
    """Only start the corrected plan after the old first request was explicitly rejected."""
    old_root = project / "cache/a2_conu_pilot"
    old = read_json(old_root / "plan.json")
    result = read_json(old_root / "diagnostic-first-request.result.json")
    error = json.loads(result["body"]).get("error", {})
    if (result.get("status") != 400 or error.get("param") != "bad_words" or
            "must tokenize to at least one token" not in error.get("message", "")):
        raise ValueError("Old run has no confirmed bad_words rejection; no new sampling plan created.")
    if list((old_root / "responses").glob("*.json")):
        raise ValueError("Old run already has saved answers; do not start a second sampling plan.")
    if sorted(p.name for p in (old_root / "attempts").glob("*.json")) != ["0000-00.json"]:
        raise ValueError("Unexpected old request history; preserve it for review.")
    receipt = read_json(old_root / "attempts/0000-00.json")
    if (receipt["plan_sha256"] != digest(encode(old)) or
            receipt["request_sha256"] != digest(encode(receipt["request"]))):
        raise ValueError("Old rejected request hash mismatch.")
    return old, {"plan_sha256": digest((old_root / "plan.json").read_bytes()),
                 "diagnostic_sha256": digest((old_root / "diagnostic-first-request.result.json").read_bytes())}


def newline_bias(tokenizer) -> dict:
    # The upstream single newline bad-word token is approximated by a -100 logit bias.
    # vLLM strips leading whitespace from bad_words, so a literal newline is invalid there.
    ids = tokenizer.encode("\n", add_special_tokens=False)
    if len(ids) != 1 or not isinstance(ids[0], int):
        raise ValueError("Expected a single-token Qwen newline; no approximation applied to multi-token text.")
    for word in BAD_WORDS:
        if not tokenizer.encode(word.lstrip(), add_special_tokens=False):
            raise ValueError(f"Empty tokenization in non-whitespace bad word: {word!r}")
    return {str(ids[0]): -100.0}


def prepare(project: Path) -> tuple[dict, Path]:
    from transformers import AutoTokenizer

    if not (project / "pyproject.toml").is_file():
        raise ValueError("Upload a2_sample_fixed.py into the NLP-project root directory.")
    previous, rejected_provenance = failed_plan(project)
    questions, demos, split, preparation, preparation_hash = load_inputs(project)
    model_dir = project.parent / "models/Qwen2.5-14B-Instruct"
    generation_config = read_json(model_dir / "generation_config.json")
    tokenizer = AutoTokenizer.from_pretrained(str(model_dir), local_files_only=True, use_fast=False, trust_remote_code=False)
    bias = newline_bias(tokenizer)
    eos = generation_config.get("eos_token_id", tokenizer.eos_token_id)
    stop_ids = list(eos) if isinstance(eos, list) else [eos]
    if tokenizer.eos_token_id is not None:
        stop_ids.append(tokenizer.eos_token_id)
    if any(not isinstance(t, int) or t < 0 for t in stop_ids):
        raise ValueError("Invalid model EOS token IDs.")
    stop_ids = sorted(set(stop_ids))
    decode = {
        "max_new_tokens": MAX_NEW_TOKENS,
        "temperature": 1.0,
        "top_p": 0.9,
        "top_k": generation_config.get("top_k", 50),
        "repetition_penalty": generation_config.get("repetition_penalty", 1.0),
        "min_p": generation_config.get("min_p", 0.0),
        "stop_token_ids": stop_ids,
        "bad_words": BAD_WORDS,
        "logit_bias": bias,
        "ignore_eos": False,
    }
    planned = []
    for index, record in enumerate(questions):
        prompt = make_prompt(record, demos)
        token_ids = tokenizer.encode(prompt, add_special_tokens=True)
        if len(token_ids) + MAX_NEW_TOKENS > CONTEXT_LIMIT:
            raise ValueError(f"Context limit exceeded: {record['qid']}")
        planned.append({
            "qid": record["qid"], "question": record["question"], "gold": record["gold"],
            "role": "calibration" if record["qid"] in split["calibration_ids"] else "test",
            "prompt": prompt, "prompt_token_ids": token_ids,
            "sample_seeds": [SEED + N_SAMPLES * index + j for j in range(N_SAMPLES)],
        })
    probe_ids = tokenizer.encode(". ", add_special_tokens=True)
    old_eos_id = probe_ids[1] if len(probe_ids) > 1 else None
    file_names = ["config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json", "merges.txt", "vocab.json", "special_tokens_map.json"]
    model_files = {name: digest((model_dir / name).read_bytes()) for name in file_names if (model_dir / name).is_file()}
    plan = {
        "schema": "confqa.conu.a2_sampling.v2", "endpoint": BASE_URL + "/v1/completions",
        "model": MODEL, "model_path": str(model_dir.resolve()), "model_tokenizer_files": model_files,
        "preparation_manifest_sha256": preparation_hash, "conu_git_head": preparation["conu_git_head"],
        "script_sha256": digest(Path(__file__).read_bytes()),
        "rejected_predecessor": rejected_provenance,
        "packages": {name: importlib.metadata.version(name) for name in ["vllm", "torch", "transformers", "huggingface-hub"]},
        "num_questions": len(planned), "num_samples": N_SAMPLES, "maximum_requests": len(planned) * N_SAMPLES,
        "context_limit": CONTEXT_LIMIT, "decode": decode, "questions": planned,
        "upstream_eos_probe": {"ids": probe_ids, "second_id": old_eos_id,
                               "second_token_text": tokenizer.decode([old_eos_id]) if old_eos_id is not None else None},
        "adaptations": [
            "Fixed 50-question supplementary pilot and five responses per question, not the upstream 20 responses.",
            "Preserve the upstream three-shot plain prompt; send its token IDs to /v1/completions without a chat template.",
            "Use the already-validated BF16 vLLM server rather than starting a second Transformers FP16 model copy.",
            "Use Qwen model EOS IDs, replacing the upstream tokenizer('. ')[1] model-specific EOS assumption.",
            "Retain seven non-whitespace upstream bad_words strings. vLLM 0.33 lstrip turns the newline entry into empty text and rejects it.",
            "Apply logit_bias=-100 to the locally tokenized single newline token instead. This strongly suppresses it but is not an exact -infinity token ban; backend adaptation is explicit.",
            "Pin top_k/repetition_penalty/min_p from the local generation configuration/defaults.",
            "Set an independent recorded request seed 10 + question_index*5 + sample_index; no bitwise Transformers equivalence claimed.",
            "Keep all five raw answers, including empty/duplicate answers; do not regenerate to obtain correct answers.",
        ],
    }
    for key in ["model", "model_path", "model_tokenizer_files", "preparation_manifest_sha256", "conu_git_head", "packages",
                "num_questions", "num_samples", "maximum_requests", "context_limit", "questions", "upstream_eos_probe"]:
        if plan[key] != previous[key]:
            raise ValueError(f"Corrected plan would change frozen input/model setting {key}; refusing.")
    old_decode = {key: value for key, value in previous["decode"].items() if key != "bad_words"}
    new_decode = {key: value for key, value in decode.items() if key not in ("bad_words", "logit_bias")}
    if old_decode != new_decode or previous["decode"]["bad_words"] != BAD_WORDS + ["\n"]:
        raise ValueError("Unexpected decode changes beyond the known newline correction.")
    root = project / "cache/a2_conu_pilot_v2"
    atomic_write(root / "plan.json", encode(plan), immutable=True)
    print("A2 SAMPLING PLAN READY", flush=True)
    print(f"Questions: {len(planned)}; responses/question: {N_SAMPLES}; maximum responses: {len(planned) * N_SAMPLES}", flush=True)
    print("Decode:", json.dumps(decode, ensure_ascii=False), flush=True)
    print("Max input tokens:", max(len(q["prompt_token_ids"]) for q in planned), flush=True)
    print("Plan:", root / "plan.json", flush=True)
    return plan, root


def request_payload(plan: dict, qi: int, si: int) -> dict:
    q, settings = plan["questions"][qi], plan["decode"]
    return {
        "model": plan["model"], "prompt": q["prompt_token_ids"], "n": 1,
        "max_tokens": settings["max_new_tokens"], "temperature": settings["temperature"],
        "top_p": settings["top_p"], "top_k": settings["top_k"],
        "repetition_penalty": settings["repetition_penalty"], "min_p": settings["min_p"],
        "bad_words": settings["bad_words"], "stop_token_ids": settings["stop_token_ids"],
        "logit_bias": settings["logit_bias"],
        "ignore_eos": False, "seed": q["sample_seeds"][si], "stream": False,
        "skip_special_tokens": True, "spaces_between_special_tokens": True,
    }


def response_text(envelope: dict, plan: dict, qi: int, si: int) -> str:
    payload_hash = digest(encode(request_payload(plan, qi, si)))
    if envelope.get("plan_sha256") != digest(encode(plan)) or envelope.get("request_sha256") != payload_hash:
        raise ValueError(f"Saved response belongs to a different plan/request: {qi}/{si}")
    body = envelope.get("response", {})
    if body.get("model") != plan["model"]:
        raise ValueError("Saved response model does not match the plan.")
    choices = body.get("choices", [])
    if len(choices) != 1 or choices[0].get("index") != 0 or not isinstance(choices[0].get("text"), str):
        raise ValueError(f"Expected exactly one text completion: {qi}/{si}")
    if choices[0].get("finish_reason") not in ("stop", "length"):
        raise ValueError(f"Completion did not finish normally: {qi}/{si}")
    return choices[0]["text"]


def completion_file(root: Path, qi: int, si: int) -> Path:
    return root / "responses" / f"{qi:04d}-{si:02d}.json"


def collect(root: Path, plan: dict) -> tuple[list[dict], int]:
    records, received = [], 0
    for qi, q in enumerate(plan["questions"]):
        envelopes, samples = [], []
        for si in range(plan["num_samples"]):
            path = completion_file(root, qi, si)
            if path.exists():
                envelope = read_json(path)
                samples.append(response_text(envelope, plan, qi, si))
                envelopes.append(envelope)
                received += 1
        if len(samples) != plan["num_samples"]:
            continue
        records.append({
            "qid": q["qid"], "question": q["question"], "gold": q["gold"],
            "samples": samples, "model": plan["model"], "decode": plan["decode"],
            "seed": q["sample_seeds"][0], "sample_seeds": q["sample_seeds"],
            "role": q["role"], "prompt": q["prompt"],
            "finish_reasons": [e["response"]["choices"][0]["finish_reason"] for e in envelopes],
            "usage_per_sample": [e["response"].get("usage") for e in envelopes],
            "raw_response_files": [str(completion_file(root, qi, si).relative_to(root).as_posix()) for si in range(plan["num_samples"])],
            "sampling_plan_sha256": digest(encode(plan)),
        })
    return records, received


def save_snapshot(root: Path, plan: dict) -> tuple[int, int]:
    records, received = collect(root, plan)
    data = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in records).encode("utf-8")
    atomic_write(root / "conu_generations.partial.jsonl", data)
    if len(records) == plan["num_questions"]:
        atomic_write(root / "conu_generations.jsonl", data, immutable=True)
    atomic_write(root / "progress.json", encode({
        "updated_at_utc": timestamp(), "complete_questions": len(records),
        "received_responses": received, "target_questions": plan["num_questions"],
        "target_responses": plan["maximum_requests"], "plan_sha256": digest(encode(plan)),
    }))
    return len(records), received


@contextmanager
def run_lock(root: Path):
    import fcntl  # The actual run is on the school Linux host.
    with (root / "sampling.lock").open("a+") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Another sampling process is already running; do not start a second one.")
        yield


def local_http(path: str, payload=None, timeout=10):
    # Only connect to this container's loopback service; bypass proxy settings.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    data = encode(payload) if payload is not None else None
    request = urllib.request.Request(BASE_URL + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with opener.open(request, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        error.a2_body = body
        raise RuntimeError(f"HTTP {error.code} on {path}: {body}") from error


def check_server(plan: dict, root: Path) -> None:
    local_http("/health")
    models = local_http("/v1/models")
    if not any(m.get("id") == plan["model"] for m in models.get("data", [])):
        raise ValueError("The expected Qwen model is not served on port 8000.")
    schema = local_http("/openapi.json")
    properties = schema.get("components", {}).get("schemas", {}).get("CompletionRequest", {}).get("properties", {})
    missing = set(request_payload(plan, 0, 0)) - set(properties)
    if missing:
        raise ValueError(f"Server does not advertise required completion fields: {sorted(missing)}; no generation sent.")
    session_name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + f"-{os.getpid()}.json"
    atomic_write(root / "server_sessions" / session_name,
                 encode({"checked_at_utc": timestamp(), "models": models, "completion_fields": sorted(properties)}), immutable=True)


def generate_one(root: Path, plan: dict, qi: int, si: int, send=local_http) -> None:
    target = completion_file(root, qi, si)
    if target.exists():
        response_text(read_json(target), plan, qi, si)
        return
    intent = root / "attempts" / f"{qi:04d}-{si:02d}.json"
    if intent.exists():
        raise ValueError(f"A previous request may have run without a saved reply: {intent}. No retry was sent; preserve the files for diagnosis.")
    payload = request_payload(plan, qi, si)
    receipt = {"plan_sha256": digest(encode(plan)), "request_sha256": digest(encode(payload)),
               "qid": plan["questions"][qi]["qid"], "sample_index": si,
               "requested_at_utc": timestamp(), "request": payload}
    atomic_write(intent, encode(receipt), immutable=True)
    started = time.monotonic()
    # Deliberately never retry a generation POST: a missing reply does not prove no tokens were generated.
    try:
        body = send("/v1/completions", payload, timeout=180)
    except Exception as error:
        source = error.__cause__ if isinstance(error.__cause__, urllib.error.HTTPError) else error
        atomic_write(root / "errors" / f"{qi:04d}-{si:02d}.json", encode({
            "request": receipt, "error": str(error), "recorded_at_utc": timestamp(),
            "http_status": getattr(source, "code", None), "body": getattr(source, "a2_body", None),
        }), immutable=True)
        raise
    envelope = {k: receipt[k] for k in ["plan_sha256", "request_sha256", "qid", "sample_index", "requested_at_utc"]}
    envelope.update({"elapsed_seconds": time.monotonic() - started, "response": body})
    atomic_write(target, encode(envelope), immutable=True)
    response_text(envelope, plan, qi, si)


def run(plan: dict, root: Path, limit: int) -> None:
    if not 1 <= limit <= plan["num_questions"]:
        raise ValueError("Question limit is outside the fixed plan.")
    with run_lock(root):
        completed, received = save_snapshot(root, plan)
        print(f"Already saved: {completed} complete questions, {received} responses.", flush=True)
        if completed == plan["num_questions"]:
            print("A2 SAMPLING DONE (reused saved responses; no new generation)", flush=True)
            return
        # Catch uncertain interrupted requests before contacting the generation service.
        for qi in range(limit):
            for si in range(plan["num_samples"]):
                if (root / "attempts" / f"{qi:04d}-{si:02d}.json").exists() and not completion_file(root, qi, si).exists():
                    raise ValueError(f"Unresolved request {qi}/{si}; no automatic retry. Preserve the sampling log.")
        check_server(plan, root)
        for qi in range(limit):
            for si in range(plan["num_samples"]):
                existed = completion_file(root, qi, si).exists()
                generate_one(root, plan, qi, si)
                if not existed:
                    print(f"Saved question {qi + 1}/{plan['num_questions']}, answer {si + 1}/{plan['num_samples']}", flush=True)
            completed, received = save_snapshot(root, plan)
        if completed == plan["num_questions"]:
            print(f"A2 SAMPLING DONE: {completed} questions, {received} responses.", flush=True)
            print("Output:", root / "conu_generations.jsonl", flush=True)
        else:
            print(f"A2 SAMPLING PAUSED AT LIMIT: {completed}/{plan['num_questions']} complete questions, {received} saved responses.", flush=True)
            print("Rerun the same --run command without --limit-questions to continue; saved responses will be reused.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Actually query the already-running local Qwen server.")
    parser.add_argument("--limit-questions", type=int, default=50, help="Process only this prefix of the fixed 50-question plan.")
    args = parser.parse_args()
    project = Path(__file__).resolve().parent
    plan, root = prepare(project)
    if args.run:
        run(plan, root, args.limit_questions)
    else:
        print("PLAN ONLY: no model service started and no generation requests sent.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
