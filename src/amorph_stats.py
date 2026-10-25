"""
Helpers shared by the post-processing scripts of AMORPH. display.py,
export_pgf.py and the CI scripts all use these functions, so that they read
the data the same way as the sampler and report the same numbers.

The curves of the wide (amorphous) and narrow (crystalline) components come
from posterior_sample.txt, one row per posterior sample and one column per
data point.
"""

import re

import numpy as np

# The smallest dataset that is accepted, as in Data.cpp
MIN_NUM_POINTS = 10

# A line of the data file: two numbers separated by spaces or tabs, or by a
# comma with or without spaces around it, as Data.cpp reads it
_NUMBER = r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
_DATA_LINE = re.compile(r"^\s*(" + _NUMBER + r")(?:[ \t]+|[ \t]*,[ \t]*)("
                        + _NUMBER + r")\s*$")


def _quote(line):
    line = line.rstrip()
    if len(line) > 60:
        line = line[:57] + "..."
    return "'" + line + "'"


def load_data(filename):
    """
    Read a data file with the rules of the sampler (Data.cpp): blank lines
    and lines starting with # are skipped anywhere, a UTF-8 byte order mark
    is allowed, and every other line holds two numbers (x and y) separated
    by spaces, tabs or a comma. x must increase strictly, and there must be
    at least 10 points. Returns (x, y); raises ValueError, with the file and
    the line, otherwise.
    """
    x, y = [], []
    previous_line = 0
    with open(filename, encoding="utf-8-sig", errors="replace") as f:
        for number, line in enumerate(f, start=1):
            stripped = line.strip()
            if stripped == "" or stripped.startswith("#"):
                continue
            match = _DATA_LINE.match(line)
            if match is None:
                raise ValueError("{0}, line {1}: expected two numbers (x and "
                                 "y), got {2}".format(filename, number,
                                                      _quote(line)))
            xi, yi = float(match.group(1)), float(match.group(2))
            if not (np.isfinite(xi) and np.isfinite(yi)):
                raise ValueError("{0}, line {1}: expected two numbers (x and "
                                 "y), got {2}".format(filename, number,
                                                      _quote(line)))
            if x and not xi > x[-1]:
                raise ValueError("{0}, line {1}: the x values must be "
                                 "strictly increasing, but x = {2} follows "
                                 "x = {3} (line {4})".format(
                                     filename, number, xi, x[-1],
                                     previous_line))
            x.append(xi)
            y.append(yi)
            previous_line = number
    if len(x) < MIN_NUM_POINTS:
        raise ValueError("{0}: found {1} data points, at least {2} are "
                         "needed".format(filename, len(x), MIN_NUM_POINTS))
    return np.array(x), np.array(y)


def grid_weights(x):
    """
    Trapezoidal quadrature weights of the data grid x: the integral of a
    curve y sampled on x is approximately sum(weights * y). The data grid
    need not be uniform.
    """
    x = np.asarray(x, dtype=float)
    if x.size < 2:
        return np.ones_like(x)
    weights = np.empty_like(x)
    weights[1:-1] = 0.5 * (x[2:] - x[:-2])
    weights[0] = 0.5 * (x[1] - x[0])
    weights[-1] = 0.5 * (x[-1] - x[-2])
    return weights


def amorphous_fraction(wide, narrow, x=None):
    """
    The fraction amorph/(amorph + crystal) of each posterior sample, from
    the integrals of the wide and narrow components over the data grid x.
    Without x the grid is taken to be uniform.

    This is a ratio of integrated intensities, not a mass fraction of the
    amorphous phase: turning one into the other needs a calibration.

    A sample without a wide component is 0% amorphous. The fraction is NaN
    only for a sample that has neither component.
    """
    wide = np.atleast_2d(wide)
    narrow = np.atleast_2d(narrow)
    weights = np.ones(wide.shape[1]) if x is None else grid_weights(x)
    wide_integral = (wide * weights).sum(axis=1)
    narrow_integral = (narrow * weights).sum(axis=1)
    total = wide_integral + narrow_integral

    fraction = np.full(total.shape, np.nan)
    has_peaks = total > 0.0
    fraction[has_peaks] = wide_integral[has_peaks] / total[has_peaks]
    return fraction


def wide_component_shape(x, wide):
    """
    The shape of the wide component of each posterior sample, treating its
    curve as a distribution over the data grid x (which need not be
    uniform). Returns four arrays: centre of mass, half-width (standard
    deviation), skewness and nongaussianity (the Kullback-Leibler divergence
    from the Gaussian with the same centre and width).

    All four are NaN for a sample without a wide component.
    """
    x = np.asarray(x, dtype=float)
    wide = np.atleast_2d(np.asarray(wide, dtype=float))
    num_samples = wide.shape[0]
    weights = grid_weights(x)

    center = np.full(num_samples, np.nan)
    width = np.full(num_samples, np.nan)
    skewness = np.full(num_samples, np.nan)
    nongaussianity = np.full(num_samples, np.nan)

    mass = wide * weights
    integral = mass.sum(axis=1)
    has_wide = integral > 0.0
    if not np.any(has_wide):
        return center, width, skewness, nongaussianity

    # The share of the area of each curve at each point of the grid
    f = mass[has_wide] / integral[has_wide, None]

    c = (f * x).sum(axis=1)
    dx = x - c[:, None]
    w = np.sqrt((f * dx**2).sum(axis=1))

    # Best fitting Gaussian to each curve, on the same grid
    gaussian = np.exp(-0.5 * dx**2 / w[:, None]**2) * weights
    gaussian /= gaussian.sum(axis=1, keepdims=True)

    center[has_wide] = c
    width[has_wide] = w
    skewness[has_wide] = (f * (dx / w[:, None])**3).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        nongaussianity[has_wide] = (f * np.log(f / gaussian + 1E-300)).sum(axis=1)

    return center, width, skewness, nongaussianity


def postprocessing_seed(config_file="config.yaml"):
    """
    The seed for the random resampling of the DNest4 post-processing: the
    seed of config.yaml if it has one, otherwise 0. Seeding NumPy with it
    makes the same sampler output always give the same posterior samples.
    """
    import yaml
    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return 0
    seed = config.get("seed") if isinstance(config, dict) else None
    if isinstance(seed, bool) or not isinstance(seed, int):
        return 0
    return seed % 2**32
