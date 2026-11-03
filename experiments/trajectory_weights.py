"""Explicit mechanistic programs in the existing actor; no fitting or training."""
import argparse
import hashlib
import io
import json
import zipfile
import torch
from evaluate import ROOT, BASE, load_state

PARENT = ROOT / 'artifacts/ultra/wall_panic_fast.zip'
OUT = ROOT / 'artifacts/trajectory_v4'


def build(variant):
    s = load_state(PARENT)
    if variant in ('early_panic', 'exit_support', 'exit_approach', 'early_smooth', 'turn_preview'):
        # The .4m lateral threshold intervened after the steering spike had begun.
        # .6m is a manually specified .2m anticipation, preserving the same AND.
        s['mlp_extractor.policy_net.0.bias'][15] = (.6 - 15.) / .05
    if variant == 'early_smooth':
        # The previous phase's half-degree low-pass reduced beam-scale noise.
        # Apply it only to the four variable learned gates, preserving the
        # manually programmed wall predicate and all other rows.
        from scipy.ndimage import gaussian_filter1d
        w = s['mlp_extractor.policy_net.0.weight']
        for i in (1, 14, 41, 61):
            w[i] = torch.tensor(gaussian_filter1d(w[i].numpy(), 2., mode='reflect'))
    if variant in ('exit_support', 'exit_only', 'exit_approach', 'turn_preview'):
        w1, b1 = s['mlp_extractor.policy_net.0.weight'], s['mlp_extractor.policy_net.0.bias']
        w2, b2 = s['mlp_extractor.policy_net.2.weight'], s['mlp_extractor.policy_net.2.bias']
        wo, bo = s['action_net.weight'], s['action_net.bias']
        # h1[0] is almost +1; h2[14] almost -1 on development observations.
        # Retain their constant contributions, then reuse them for one predicate.
        b2 += w2[:, 0]
        w2[:, 0] = 0.
        bo -= wo[:, 14]
        wo[:, 14] = 0.
        # Lateral projection of the +/-5deg sector around left 60deg. It sees
        # the approaching outside wall earlier than the perpendicular beam.
        import numpy as np
        angles = np.linspace(-2.35, 2.35, 1080)[760:800]
        w1[0, :] = 0.
        w1[0, 760:800] = torch.tensor(-15. * np.sin(angles) / (.2 * 40.), dtype=w1.dtype)
        b1[0] = (1. - 15. * float(np.sin(angles).mean())) / .2
        # AND(right-turn branch, approaching outside-left wall).
        w2[14, :] = 0.
        w2[14, 0], w2[14, 41], w2[14, 61] = 4., -4., 4.
        b2[14] = -8.
        wo[0, 14] = -.08
        bo[0] -= .08
        if variant == 'turn_preview':
            # Sochi traces begin turning only with ~3m ahead, then run wide.
            # Start a small right-turn contribution before that late switch,
            # only when the learned right branch and a closing front agree.
            w1[0, :] = 0.
            w1[0, 520:560] = -15. / 40.
            b1[0] = 6. - 15.
            wo[0, 14] = -.05
            bo[0] += .03
        if variant == 'exit_approach':
            # Close to a wall is not enough: the broad gate disrupted benign
            # wall-hugging. Require approach toward that wall AND release of
            # the learned hard-right branch (h1[1] positive).
            b2 -= w2[:, 62]
            w2[:, 62] = 0.
            theta = np.linspace(-2.35, 2.35, 1080)
            w1[62, :] = 0.
            w1[62, 1000:1040] = torch.tensor(15.*np.sin(theta[1000:1040])/(.075*40.), dtype=w1.dtype)
            w1[62, 760:800] = torch.tensor(-15.*np.sin(theta[760:800])/(.075*40.), dtype=w1.dtype)
            b1[62] = (15.*(float(np.sin(theta[1000:1040]).mean())-float(np.sin(theta[760:800]).mean()))-.15)/.075
            w2[14, 62], w2[14, 1], b2[14] = 4., 4., -16.
    # No longitudinal intervention: retain the previous +.2m/s model throttle,
    # apart from bounded residual of compensating a nearly constant neuron.
    original, parent = load_state(BASE), load_state(PARENT)
    assert all(torch.equal(v, original[k]) for k, v in s.items() if 'value' in k or k == 'log_std')
    assert all(torch.isfinite(v).all() for v in s.values())
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f'{variant}.zip'
    buffer = io.BytesIO()
    torch.save(s, buffer)
    with zipfile.ZipFile(PARENT) as src, zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            dst.writestr(item, buffer.getvalue() if item.filename == 'policy.pth' else src.read(item.filename))
    counts = lambda ref: {k: int((v != ref[k]).sum()) for k, v in s.items() if not torch.equal(v, ref[k])}
    manifest = dict(variant=variant, parent=str(PARENT.relative_to(ROOT)),
                    parent_sha256=hashlib.sha256(PARENT.read_bytes()).hexdigest(),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    changed_from_original=counts(original), changed_from_parent=counts(parent),
                    method='manually reasoned weight edits; no gradients, training, fitting or parameter search',
                    early_panic='left-side threshold .4 -> .6m; same internal steering predicate',
                    exit_support='h0=tanh((1m-mean(d_left60*sin(theta)))/.2m); g=tanh(4*(h0-h41+h61-2)); steer -= .08*(1+g)',
                    exit_approach='Requires additionally h62=tanh((y_left120-y_left60-.15m)/.075m) and h1 positive; g=tanh(4*(h0-h41+h61+h62+h1-4))',
                    early_smooth='Gaussian angular low-pass sigma 2 beams (~0.5deg), only learned first-layer rows 1,14,41,61',
                    turn_preview='h0=tanh((6m-front_mean)/1m); g=tanh(4*(h0-h41+h61-2)); steer -= .05*(1+g)',
                    inference_only=True)
    path.with_suffix('.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('variant', choices=['early_panic', 'exit_support', 'exit_only', 'exit_approach', 'early_smooth', 'turn_preview'])
    build(ap.parse_args().variant)
