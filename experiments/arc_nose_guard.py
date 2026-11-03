"""Protect the front face during launch using the car's forward travel budget."""
import hashlib
import json
import numpy as np
import torch

from from_scratch import ROOT


def build():
    directory = ROOT / 'artifacts/arc_recovery'
    source = directory / 'launch_guard.pt'
    model = torch.jit.load(str(source)).eval()
    normal = torch.jit.load(str(directory/'clear_straight.pt')).eval()
    angles = np.linspace(-2.35, 2.35, 1080)
    front_face = np.abs(angles) <= np.arctan2(.155, .1651)
    floor = np.zeros_like(angles)
    # Forward translation consumes the clearance in front of the axle box.
    # Require 3cm of scan reserve plus motion during the steering/TTC delay.
    cosine = np.cos(angles[front_face])
    floor[front_face] = .1651/cosine + .03 + 3.*(.02+.005)*cosine + .04
    guard = torch.as_tensor(floor.reshape(180, 6).max(axis=1), dtype=model.envelope.dtype)
    # Limit this requirement to the space newly opened for low-speed departure.
    # In particular, all the normal arcs of 1.5m and longer stay bit-identical.
    original = model.envelope.clone()
    model.envelope[:, :2].copy_(torch.maximum(original[:, :2], torch.minimum(normal.envelope[:, :2], guard)))
    path = directory/'nose_guard.pt'
    model.save(str(path))
    torch.save(model.state_dict(), directory/'nose_guard_weights.pth')
    path.with_suffix('.json').write_text(json.dumps(dict(parent=source.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  changed_envelope_scalars=int((model.envelope != original).sum()), horizons_m=[.5,1.],
                  forward_graph_unchanged=model.code==normal.code),indent=2)+'\n')
    print(path)


if __name__ == '__main__':
    build()
