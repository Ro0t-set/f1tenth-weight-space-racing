"""Compile a forward TTC clearance requirement into the frozen arc envelopes."""
from pathlib import Path
import hashlib
import json
import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'artifacts/arc_recovery/launch_guard.pt'
OUT = ROOT / 'artifacts/arc_recovery/pose_guard.pt'


def build():
    model = torch.jit.load(str(SOURCE)).eval()
    angles = np.linspace(-2.35, 2.35, 1080)
    cosine = np.cos(angles)
    forward = cosine > 0
    footprint = np.minimum(.155 / np.abs(np.sin(angles)), .1651 / np.abs(cosine))
    # The one-metre horizon commands up to 3 m/s. Allow the two-step steering
    # delay and the original TTC interval before a corrective turn can act.
    required = np.zeros_like(angles)
    required[forward] = footprint[forward] + .03 + 3 * (.02 + .005) * cosine[forward]
    # Complete the 4 cm activation fade if this current-pose test fails.
    required[forward] += .04
    floor = torch.as_tensor(required.reshape(180, 6).max(axis=1), dtype=model.envelope.dtype)
    weights = torch.maximum(model.envelope, floor)
    changed = int((weights != model.envelope).sum())
    model.envelope.copy_(weights)
    model.save(str(OUT))
    OUT.with_suffix('.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(), sha256=hashlib.sha256(OUT.read_bytes()).hexdigest(), changed_envelope_scalars=changed, guard='front TTC radius + 3cm noise + 3m/s * (20ms actuation delay + 5ms TTC) * cos(theta); all horizons, 4cm complete fade'),indent=2)+'\n')
    return OUT


if __name__ == '__main__':
    print(build())
