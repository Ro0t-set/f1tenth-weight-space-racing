#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python_bin="${PYTHON_BIN:-python3.11}"
"$python_bin" -c 'import sys; assert sys.version_info[:2] == (3, 11), "Use Python 3.11"'
upstream_commit=9381a13eec6b182ff38e4fba55a105cf94219da6
tracks_commit=3f581789c749261ae36fc4fef19a81372acc3ecf
if [[ ! -e upstream ]]; then
  git clone --no-checkout https://github.com/zucchero-sintattico/svs-f1tenth_gym.git upstream
fi
git -C upstream checkout --detach "$upstream_commit"
git -C upstream submodule update --init --recursive --checkout
test "$(git -C upstream/map/f1tenth_racetracks rev-parse HEAD)" = "$tracks_commit"
"$python_bin" -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip check
.venv/bin/python -c 'from hashlib import sha256; from pathlib import Path; assert sha256(Path("upstream/train_test/best_global_model.zip").read_bytes()).hexdigest() == "1cab23c05d804aa4f15fca9e79960f18f6af91e2b8d458bb8e659b3592307d6b"'
