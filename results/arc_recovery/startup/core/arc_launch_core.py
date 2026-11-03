"""Compile a slow departure arc into the existing visibility tensor."""
import numpy as np

from from_scratch import radial_envelope


def build_launch_envelope(curvature, horizons, angles, valid, speed_function, steady_function):
    """Return dynamic envelope weights. The two callables take (curvature, horizon)
    and (curvature, speed), returning speed and (steering, steady slip) respectively.

    The first half metre starts at the actual body width and gradually restores
    the five-centimetre reserve. Longer paths retain their original reserve.
    """
    envelope = np.zeros((len(curvature), len(horizons), len(angles) // 6))
    short = np.zeros((len(curvature), 2, len(angles) // 6))
    # Every orientation of the physical car contains a disc with this
    # radius. Protect that disc by three standard deviations of scan noise.
    core_radius = .155 + .03
    for row, kappa in enumerate(curvature):
        for column, horizon in enumerate(horizons):
            if not valid[row, column]:
                continue
            speed = speed_function(kappa, horizon)
            _, beta = steady_function(kappa, speed)
            full = radial_envelope(kappa, horizon, angles, beta=beta)
            envelope[row, column] = full
            if column < 2:
                count = max(2, int(np.ceil(horizon / .03)) + 1)
                distance = np.linspace(0., horizon, count)
                margin = (.05 * np.clip((distance - .5) / .5, 0., 1.))[:, None, None]
                launch = radial_envelope(kappa, horizon, angles, margin=margin, beta=beta)
                # When only 0.5 m is available, the speed head starts at 0.25 m.
                # The 2 cm radial allowance cancels half of the existing 4 cm
                # feasibility ramp at that threshold. A successful launch needs
                # the measured rays to clear the actual swept rectangle.
                short[row, column] = np.minimum(full, np.maximum(launch + (.02 if column == 0 else .03), core_radius + .03))
    envelope = np.maximum.accumulate(envelope, axis=1)
    envelope[:, :2] = np.maximum.accumulate(short, axis=1)
    return envelope
