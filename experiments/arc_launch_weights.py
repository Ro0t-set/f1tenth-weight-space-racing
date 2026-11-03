"""Compile short departure sweeps into ArcNetwork's existing visibility tensor."""
import numpy as np

from from_scratch import radial_envelope


def build_launch_envelope(curvature, horizons, angles, valid, speed_function, steady_function):
    """Build the 17 × 9 × 180 envelope for the existing LiDAR arc policy.

    speed_function(curvature, horizon) returns m/s. steady_function(curvature,
    speed) returns a steering angle and a steady slip angle in radians.
    """
    if len(horizons) < 3 or not np.allclose(horizons[:2], [.5, 1.]):
        raise ValueError('Departure sweeps require the first two horizons at 0.5 and 1 metre')

    sectors = len(angles) // 6
    envelope = np.zeros((len(curvature), len(horizons), sectors))
    departures = np.zeros((len(curvature), 2, sectors))

    # The circle inscribed in the body is independent of yaw. Three scan-noise
    # standard deviations give its centre a larger reserve than the corners.
    core_radius = .31 / 2 + 3 * .01
    for row, kappa in enumerate(curvature):
        for column, horizon in enumerate(horizons):
            if not valid[row, column]:
                continue
            speed = speed_function(kappa, horizon)
            _, slip = steady_function(kappa, speed)
            full = radial_envelope(kappa, horizon, angles, beta=slip)
            envelope[row, column] = full
            if column >= 2:
                continue

            # radial_envelope samples the path at intervals of at most 3 cm.
            # Use the true body for the first half-metre. Over the next half
            # metre, restore the ordinary 5 cm clearance around the body.
            samples = max(2, int(np.ceil(horizon / .03)) + 1)
            distance = np.linspace(0., horizon, samples)
            margin = (.05 * np.clip((distance - .5) / .5, 0., 1.))[:, None, None]
            departure = radial_envelope(kappa, horizon, angles, margin=margin, beta=slip)

            # The speed head starts at 0.25 m and feasibility fades across
            # 4 cm. Half of that fade corresponds to a single 0.5 m sweep,
            # three quarters to a common obstruction over the full metre.
            radial_allowance = .02 if column == 0 else .03
            required = np.maximum(departure + radial_allowance, core_radius + .03)
            departures[row, column] = np.minimum(full, required)

    # Under different predicted slips, the longer sweep must still cover the
    # earlier footprints. Preserve the original nesting from 1.5 m onward.
    envelope = np.maximum.accumulate(envelope, axis=1)
    envelope[:, :2] = np.maximum.accumulate(departures, axis=1)
    return envelope
