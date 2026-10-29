#!/bin/bash
#SBATCH --job-name=p1-TODO
#SBATCH --partition=TODO
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --output=logs/%x-%j.out

set -euo pipefail

module load cuda/12.1 || true
source activate p1 || conda activate p1

# Always run from the repo root so relative paths in configs stay valid.
cd "$(dirname "$0")/../.."
mkdir -p logs

python "$@"
