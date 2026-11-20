#!/usr/bin/env python3
"""在学校服务器收集 A1 交接材料；不启动模型，也不修改权重。"""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=os.environ.get("A1_ROOT"),
                        required=not os.environ.get("A1_ROOT"))
    parser.add_argument("--env-dir", default=os.environ.get("A1_ENV_DIR"))
    parser.add_argument("--model-dir", default=os.environ.get("A1_MODEL_DIR"))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    env = Path(args.env_dir).resolve() if args.env_dir else root / "envs/confqa"
    model = Path(args.model_dir).resolve() if args.model_dir else root / "models/Qwen2.5-14B-Instruct"
    if Path(sys.prefix).resolve() != env:
        raise RuntimeError(f"请用项目 Python 执行：{env}/bin/python {Path(__file__).name}")

    required = [
        "scripts/start_vllm_a1.sh", "scripts/smoke_request.json", "scripts/README.md",
        "logs/a1-requirements-lock.txt", "logs/a1-smoke-response.json",
        "logs/a1-script-smoke-response.json", "logs/vllm-a1.latest-log",
    ]
    for relative in required:
        if not (root / relative).is_file():
            raise FileNotFoundError(f"缺少交接材料：{root / relative}")

    index = model / "model.safetensors.index.json"
    weight_map = json.loads(index.read_text(encoding="utf-8"))["weight_map"]
    shards = sorted(set(weight_map.values()))
    if len(shards) != 8:
        raise RuntimeError(f"预期本次模型为 8 个权重分片，索引中实际为 {len(shards)} 个；请先核查。")
    for name in shards:
        if Path(name).name != name or not (model / name).is_file() or (model / name).stat().st_size == 0:
            raise RuntimeError(f"权重分片不存在、为空或路径异常：{name}")
    incomplete = list(model.glob("*.incomplete"))
    if incomplete:
        raise RuntimeError(f"模型目录仍有未完成文件：{[p.name for p in incomplete]}")

    # 只读取顶层非隐藏文件；下载缓存和模型权重本身不会复制进交接包。
    model_files = sorted(p for p in model.iterdir() if p.is_file() and not p.name.startswith("."))
    started = time.monotonic()
    started_utc = datetime.now(timezone.utc).isoformat()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = root / f"a1-evidence-{stamp}"
    out.mkdir(exist_ok=False)
    print(f"开始收集，输出目录：{out}", flush=True)

    def copy_record(relative, required_file=True):
        source = root / relative
        if not source.is_file():
            if required_file:
                raise FileNotFoundError(source)
            return
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    for relative in required:
        copy_record(relative)
    for relative in [
        "logs/vllm-a1.pid", "logs/vllm-a1.log", "logs/vllm-a1-retry1.log",
        "logs/vllm-a1-retry2.log", "logs/a1-gpu-after-smoke.txt",
    ]:
        copy_record(relative, required_file=False)
    shutil.copy2(Path(__file__).resolve(), out / "scripts/collect_a1_evidence.py")

    latest = Path((root / "logs/vllm-a1.latest-log").read_text(encoding="utf-8").strip()).resolve()
    logs_root = (root / "logs").resolve()
    if not latest.is_relative_to(logs_root) or not latest.is_file():
        raise RuntimeError(f"最新启动日志路径异常或文件不存在：{latest}")
    copy_record(str(latest.relative_to(root)))
    if "Application startup complete" not in latest.read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError("最新日志未找到 Application startup complete，请先核查服务启动记录。")

    responses = {}
    for name in ["a1-smoke-response.json", "a1-script-smoke-response.json"]:
        response = json.loads((root / "logs" / name).read_text(encoding="utf-8"))
        choice = response["choices"][0]
        if response.get("model") != "qwen2.5-14b-instruct" or choice["message"]["content"].strip() != "Paris" or choice.get("finish_reason") != "stop":
            raise RuntimeError(f"{name} 与本次固定请求的已知成功响应不一致，请先核查。")
        responses[name] = {"id": response.get("id"), "model": response.get("model"),
                           "content": choice["message"]["content"], "finish_reason": choice.get("finish_reason"),
                           "usage": response.get("usage"), "system_fingerprint": response.get("system_fingerprint")}

    commands = []

    def record_command(argv, relative, must_succeed=False):
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60, check=False)
            target.write_text(result.stdout, encoding="utf-8")
            if result.stderr:
                target.with_name(target.name + ".stderr.txt").write_text(result.stderr, encoding="utf-8")
            commands.append({"argv": argv, "returncode": result.returncode, "stdout": relative})
            if must_succeed and result.returncode != 0:
                raise RuntimeError(f"命令失败：{argv}；请查看 {target.parent}")
        except (OSError, subprocess.TimeoutExpired) as exc:
            target.write_text(str(exc) + "\n", encoding="utf-8")
            commands.append({"argv": argv, "error": str(exc), "stdout": relative})
            if must_succeed:
                raise

    record_command([sys.executable, "-m", "pip", "freeze"], "environment/pip-freeze-current.txt", must_succeed=True)
    record_command(["nvidia-smi"], "environment/nvidia-smi-at-collection.txt")
    release = Path("/etc/os-release")
    if release.is_file():
        shutil.copy2(release, out / "environment/os-release.txt")
    versions = {}
    for name in ["torch", "vllm", "transformers", "flashinfer-python", "modelscope", "modelscope-hub", "ninja"]:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    write_json(out / "environment/python-platform.json", {
        "executable": sys.executable, "prefix": sys.prefix, "python": sys.version,
        "platform": platform.platform(), "machine": platform.machine(),
        "libc": platform.libc_ver(), "package_versions": versions,
        "commands": commands,
    })

    manifest = []
    model_records = out / "model"
    model_records.mkdir()
    print(f"开始计算模型文件 SHA256：{len(model_files)} 个文件，含 {len(shards)} 个权重分片。", flush=True)
    print("只读取文件，不使用 GPU；每完成一个文件都会更新进度。", flush=True)
    with (model_records / "SHA256SUMS").open("w", encoding="utf-8", newline="\n") as sums:
        for number, path in enumerate(model_files, 1):
            print(f"[{number}/{len(model_files)}] {path.name} ({path.stat().st_size:,} bytes)", flush=True)
            before = path.stat()
            digest = sha256_file(path)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                raise RuntimeError(f"计算哈希时文件发生变化：{path}")
            sums.write(f"{digest}  {path.name}\n")
            sums.flush()
            manifest.append({"path": path.name, "bytes": after.st_size, "sha256": digest})
    write_json(model_records / "model-manifest.json", manifest)
    write_json(model_records / "source-notes.json", {
        "repository": "Qwen/Qwen2.5-14B-Instruct", "download_service": "ModelScope",
        "requested_revision": "master", "immutable_source_revision": None,
        "local_model_directory": str(model), "weight_shards": shards,
        "notes": "master 是可变分支。此清单固定本次本地文件内容，不代表已取得来源提交号，也不代表已和 Hugging Face 文件逐个比对。哈希范围为顶层非隐藏文件，不含下载缓存。",
    })
    write_json(out / "collection-record.json", {
        "started_utc": started_utc, "finished_utc": datetime.now(timezone.utc).isoformat(),
        "collection_elapsed_seconds": round(time.monotonic() - started, 3),
        "collection_time_scope": "仅本次材料收集与哈希计算耗时，不是模型下载、服务启动、推理耗时或 GPU 配额用量。",
        "root": str(root), "environment": str(env), "responses": responses,
        "status": "A 的脚本启动和固定请求已验证；C 独立复跑、团队仓库落地及实验资源记录仍待完成。",
        "pid_files": "复制的 PID 文件是历史运行记录，不能直接用于后续停止进程。",
        "gpu_snapshots": "快照不代表峰值显存；nvidia-smi 的采集失败会记录在环境文件中。",
    })
    bundle_files = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        bundle_files.append({"path": path.relative_to(out).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_json(out / "bundle-file-manifest.json", bundle_files)
    archive = out.with_name(out.name + ".tar.gz")
    with tarfile.open(archive, "x:gz") as bundle:
        bundle.add(out, arcname=out.name)
    print(f"完成：{archive}", flush=True)
    print(f"交接包大小：{archive.stat().st_size:,} bytes。权重与 Python 环境仍保留在原目录。", flush=True)


if __name__ == "__main__":
    main()
