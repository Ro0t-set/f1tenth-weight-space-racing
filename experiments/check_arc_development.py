"""Check the occupied pixels against the complete car on dense development traces."""
import argparse
import json
from pathlib import Path

import numpy as np
from trajectory_audit import Geometry


def audit(path):
    results = json.loads(path.read_text())
    audited = []
    for name in sorted({r['map'] for r in results['rows']}):
        geometry = Geometry(name)
        for row in (r for r in results['rows'] if r['map'] == name):
            trace = path.with_name(f'{path.stem}_{name}_{row["seed"]}_trace.npz')
            with np.load(trace) as data:
                states = data['states']
                assert np.array_equal(data['steps'], np.arange(row['steps']))
                assert len(states) == row['steps']
            clearance = np.asarray([geometry.clearance(s[:2], s[4], with_center=False) for s in states])
            audited.append(dict(map=name, seed=row['seed'], success=row['success'],
                                min_clearance_m=float(clearance.min()), contact_frames=int((clearance <= 1e-10).sum())))
    summary = dict(checkpoint_sha256=results['sha256'], completed_clean=sum(r['success'] and r['contact_frames']==0 for r in audited),
                   completed_with_contact=sum(r['success'] and r['contact_frames']>0 for r in audited), rows=audited)
    path.with_name(path.stem+'_geometry.json').write_text(json.dumps(summary, indent=2)+'\n')
    print(summary['completed_clean'], summary['completed_with_contact'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    audit(parser.parse_args().result)
