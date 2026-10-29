#!/usr/bin/env bash
# Create the project environment on the cluster.
# Usage: bash scripts/setup_env.sh [env_name]
set -euo pipefail

ENV_NAME=confqa
if [ "$#" -gt 0 ]; then ENV_NAME="$1"; fi

# TODO: replace with this cluster's CUDA module (or delete the line).
module load cuda/12.1 2>/dev/null || true

if ! command -v conda >/dev/null 2>&1; then
  echo "conda not found: load an anaconda/miniconda module first" >&2
  exit 1
fi

conda create -y -n "$ENV_NAME" python=3.11
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

pip install -e ".[dev]"

echo
echo "base env ready. install the GPU stack next (match the driver's CUDA):"
echo "  pip install -r requirements-gpu.txt"
