"""
Quantities derived from the posterior samples of AMORPH. display.py,
export_pgf.py and the CI scripts all use these functions, so that they
report the same numbers.

The curves of the wide (amorphous) and narrow (crystalline) components come
from posterior_sample.txt, one row per posterior sample and one column per
data point.
"""

import numpy as np


def amorphous_fraction(wide, narrow):
    """
    The fraction amorph/(amorph + crystal) of each posterior sample, from
    the integrals of the wide and narrow components over the data grid.

    A sample without a wide component is 0% amorphous. The fraction is NaN
    only for a sample that has neither component.
    """
    wide_integral = np.atleast_2d(wide).sum(axis=1)
    narrow_integral = np.atleast_2d(narrow).sum(axis=1)
    total = wide_integral + narrow_integral

    fraction = np.full(total.shape, np.nan)
    has_peaks = total > 0.0
    fraction[has_peaks] = wide_integral[has_peaks] / total[has_peaks]
    return fraction


def wide_component_shape(x, wide):
    """
    The shape of the wide component of each posterior sample, treating its
    curve as a distribution over the data grid x. Returns four arrays:
    centre of mass, half-width (standard deviation), skewness and
    nongaussianity (the Kullback-Leibler divergence from the Gaussian with
    the same centre and width).

    All four are NaN for a sample without a wide component.
    """
    x = np.asarray(x, dtype=float)
    wide = np.atleast_2d(np.asarray(wide, dtype=float))
    num_samples = wide.shape[0]

    center = np.full(num_samples, np.nan)
    width = np.full(num_samples, np.nan)
    skewness = np.full(num_samples, np.nan)
    nongaussianity = np.full(num_samples, np.nan)

    integral = wide.sum(axis=1)
    has_wide = integral > 0.0
    if not np.any(has_wide):
        return center, width, skewness, nongaussianity

    # Normalised curves
    f = wide[has_wide] / integral[has_wide, None]

    c = (f * x).sum(axis=1)
    dx = x - c[:, None]
    w = np.sqrt((f * dx**2).sum(axis=1))

    # Best fitting Gaussian to each curve
    gaussian = np.exp(-0.5 * dx**2 / w[:, None]**2)
    gaussian /= gaussian.sum(axis=1, keepdims=True)

    center[has_wide] = c
    width[has_wide] = w
    skewness[has_wide] = (f * (dx / w[:, None])**3).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        nongaussianity[has_wide] = (f * np.log(f / gaussian + 1E-300)).sum(axis=1)

    return center, width, skewness, nongaussianity
