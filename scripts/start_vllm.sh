#!/usr/bin/env bash
# Start the project vLLM server (OpenAI-compatible) on the HPC dev container.
#
#   bash scripts/start_vllm.sh
#
# Override anything with environment variables:
#   PROJECT_ROOT   working directory on the shared filesystem
#   VLLM_MAX_SEQS  concurrent sequences (default 16; A's evidence used 1)
#   VLLM_EAGER     1 disables CUDA graphs (default 1; the config A validated)
#   VLLM_PORT      default 8000
set -euo pipefail

ROOT="${PROJECT_ROOT:-/hpc2ssd/JH_DATA/spooler/aiaa4051_077}"
ENV_DIR="${VLLM_ENV:-$ROOT/envs/confqa}"
MODEL_DIR="${VLLM_MODEL:-$ROOT/models/Qwen2.5-14B-Instruct}"
PORT="${VLLM_PORT:-8000}"
MAX_SEQS="${VLLM_MAX_SEQS:-16}"
MAX_LEN="${VLLM_MAX_LEN:-2048}"
GPU_UTIL="${VLLM_GPU_UTIL:-0.9}"
LOG_DIR="$ROOT/logs"

if [[ ! -x "$ENV_DIR/bin/vllm" ]]; then
    printf 'vllm not found in %s\n' "$ENV_DIR" >&2
    exit 1
fi
if [[ ! -f "$MODEL_DIR/model.safetensors.index.json" ]]; then
    printf 'model index not found in %s\n' "$MODEL_DIR" >&2
    exit 1
fi

if "$ENV_DIR/bin/python" -c 'import socket, sys; socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=1).close()' "$PORT" >/dev/null 2>&1; then
    printf 'port %s is already serving; stop it first\n' "$PORT" >&2
    exit 1
fi

mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/vllm-$(date +%Y%m%d-%H%M%S).log"

export PATH="$ENV_DIR/bin:$PATH"
# Work around the FlashInfer sampling build issue seen on this image.
export VLLM_USE_FLASHINFER_SAMPLER=0

EAGER_ARGS=()
if [[ "${VLLM_EAGER:-1}" == "1" ]]; then
    EAGER_ARGS=(--enforce-eager)
fi

nohup "$ENV_DIR/bin/vllm" serve "$MODEL_DIR" \
    --served-model-name qwen2.5-14b-instruct \
    --host 127.0.0.1 --port "$PORT" \
    --dtype bfloat16 --tensor-parallel-size 1 \
    --max-model-len "$MAX_LEN" --max-num-seqs "$MAX_SEQS" \
    --gpu-memory-utilization "$GPU_UTIL" \
    "${EAGER_ARGS[@]}" \
    >"$LOG" 2>&1 </dev/null &

printf 'started pid %s\n' "$!"
printf 'log %s\n' "$LOG"

printf 'waiting for the server'
for _ in $(seq 1 150); do
    if curl -sS -m 2 "http://127.0.0.1:$PORT/v1/models" >/dev/null 2>&1; then
        printf '\nready: http://127.0.0.1:%s/v1\n' "$PORT"
        exit 0
    fi
    printf '.'
    sleep 2
done
printf '\nserver did not become ready in 5 minutes; check %s\n' "$LOG" >&2
exit 1
