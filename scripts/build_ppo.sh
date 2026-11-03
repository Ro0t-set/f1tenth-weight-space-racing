#!/usr/bin/env bash
# Compile PPO derivatives from the pinned upstream checkpoint, checking each SHA.
set -euo pipefail
cd "$(dirname "$0")/.."
root="$PWD"
python_bin="${PYTHON_BIN:-$root/.venv/bin/python}"
mode="${1:-comparison}"
if [[ "$mode" != comparison && "$mode" != all ]]; then
  echo "Usage: bash scripts/build_ppo.sh [comparison|all]" >&2
  exit 2
fi
mkdir -p reruns
work="$(mktemp -d "$root/reruns/ppo.XXXXXX")"
mkdir -p "$work/experiments" "$work/artifacts/racing_v2"
cp experiments/*.py "$work/experiments/"
ln -s "$root/upstream" "$work/upstream"
cd "$work"
run() { "$python_bin" "experiments/$1.py" "${@:2}"; }

run ultra_weights wall_panic
run ultra_weights wall_panic_fast
run trajectory_weights early_smooth
if [[ "$mode" == all ]]; then
  run evaluate --seeds 101 202 303 404 505 --trace --out results/development_baseline.json
  run edit_weights
  run edit_weights --cautious
  run evaluate --maps BrandsHatch YasMarina Monza Spa Sochi Budapest Oschersleben \
    --seeds 1101 2202 3303 --trace --out results/racing_v2/development_baseline.json
  for variant in clearance_speed two_gate two_gate_guard exit_guard geometric curvature_compensated straight_boost; do
    run racing_weights "$variant"
  done
  for variant in angular_smooth panic_gate; do run ultra_weights "$variant"; done
  for variant in early_panic exit_support exit_only exit_approach turn_preview; do run trajectory_weights "$variant"; done
fi
"$python_bin" - "$root" "$mode" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sys
root = Path(sys.argv[1])
index = json.loads((root / 'artifacts/checkpoints.json').read_text())
found = sorted(Path('artifacts').rglob('*.zip'))
expected = [name for name in index if name.startswith('artifacts/') and name.endswith('.zip')]
if sys.argv[2] == 'all' and set(map(str, found)) != set(expected):
    raise SystemExit('Incomplete PPO build')
for path in found:
    if sha256(path.read_bytes()).hexdigest() != index[str(path)]['historical_sha256']:
        raise SystemExit(f'Checkpoint hash mismatch for {path}; build retained in {Path.cwd()}')
for path in found:
    shutil.copyfile(path, root / path)
print(f'Verified and installed {len(found)} original-run PPO edits.')
PY
