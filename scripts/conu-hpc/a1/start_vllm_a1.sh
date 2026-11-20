#!/usr/bin/env bash
# 在学校 Linux 开发环境中运行：bash start_vllm_a1.sh
set -euo pipefail

# C 的目录不同，可通过 A1_ROOT / A1_ENV_DIR / A1_MODEL_DIR 覆盖。
a1_root="${A1_ROOT:?Set A1_ROOT to the work directory}"
a1_env="${A1_ENV_DIR:-$a1_root/envs/confqa}"
a1_model="${A1_MODEL_DIR:-$a1_root/models/Qwen2.5-14B-Instruct}"
a1_port="${A1_PORT:-8000}"
a1_logs="$a1_root/logs"

if [[ ! -x "$a1_env/bin/vllm" || ! -x "$a1_env/bin/python" ]]; then
    printf '找不到项目环境：%s\n' "$a1_env" >&2
    exit 1
fi
if [[ ! -f "$a1_model/model.safetensors.index.json" ]]; then
    printf '找不到模型权重索引：%s\n' "$a1_model" >&2
    exit 1
fi

# 指定环境的工具搜索路径；仅写 vllm 的绝对路径不能替代 PATH。
export PATH="$a1_env/bin:$PATH"
# 已验证的 PyTorch 采样配置，避开当前镜像的 FlashInfer sampling 编译问题。
export VLLM_USE_FLASHINFER_SAMPLER=0

# 如果端口已被占用，先报告，避免重复启动已在运行的服务。
if "$a1_env/bin/python" -c 'import socket, sys; s = socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1); s.close()' "$a1_port" >/dev/null 2>&1; then
    printf '端口 %s 已有服务，请先确认现有服务状态。\n' "$a1_port" >&2
    exit 1
fi

mkdir -p "$a1_logs"
a1_log="$a1_logs/vllm-a1-$(date +%Y%m%d-%H%M%S).log"

# 后台启动并保留日志；学校开发环境仍须保持运行。
nohup "$a1_env/bin/vllm" serve "$a1_model" \
    --served-model-name qwen2.5-14b-instruct \
    --host 127.0.0.1 --port "$a1_port" \
    --dtype bfloat16 --tensor-parallel-size 1 \
    --max-model-len 2048 --max-num-seqs 1 \
    --gpu-memory-utilization 0.9 --enforce-eager \
    >"$a1_log" 2>&1 </dev/null &

a1_pid=$!
printf '%s\n' "$a1_pid" >"$a1_logs/vllm-a1.pid"
printf '%s\n' "$a1_log" >"$a1_logs/vllm-a1.latest-log"
printf '已提交启动，PID：%s\n日志：%s\n' "$a1_pid" "$a1_log"
printf '请查看日志并完成一次请求验证；提交任务不等于服务已就绪。\n'
