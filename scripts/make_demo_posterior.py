"""
Create a synthetic data set and a matching posterior_sample.txt.

This is only needed to try out the plotting pipeline (src/export_pgf.py
plus doc/figures/xrd_fit.tex) without first running the AMORPH sampler.
The generated files have exactly the same layout as the real output of
AMORPH, so the exporter cannot tell the difference.

    python make_demo_posterior.py --out demo

writes demo/demo_data.txt and demo/demo_posterior_sample.txt.
"""

import argparse
import os
import numpy as np


# The AMORPH peak shape is a Student-t density, normalised so that the
# integral over the lookup table [-20, 20] is one (see src/Lookup.cpp).
LOOKUP_XMIN = -20.0
LOOKUP_XMAX = 20.0
LOOKUP_N = 10001


_NORMALISATION = {}


def t_shape_normalisation(nu):
    """
    Integral of the Student-t shape over the lookup grid of Lookup.cpp.
    """
    if nu not in _NORMALISATION:
        xs = np.linspace(LOOKUP_XMIN, LOOKUP_XMAX, LOOKUP_N)
        dx = (LOOKUP_XMAX - LOOKUP_XMIN) / (LOOKUP_N - 1)
        f = (1.0 + xs * xs / nu) ** (-0.5 * (nu + 1.0))
        _NORMALISATION[nu] = f.sum() * dx
    return _NORMALISATION[nu]


def t_shape(nu, x):
    """
    Normalised Student-t shape, evaluated on the lookup grid of Lookup.cpp.
    """
    z = t_shape_normalisation(nu)
    return (1.0 + np.asarray(x) ** 2 / nu) ** (-0.5 * (nu + 1.0)) / z


# Crystalline (narrow) peaks: position, height, width
NARROW_PEAKS = [(34.35, 225.0, 0.10),
                (36.10, 150.0, 0.12),
                (38.30, 430.0, 0.13),
                (40.60, 350.0, 0.14),
                (42.60, 45.0, 0.12),
                (44.10, 45.0, 0.15)]

# Amorphous (wide) peaks: position, height, width
WIDE_PEAKS = [(34.50, 60.0, 0.60),
              (37.00, 80.0, 0.80),
              (39.00, 70.0, 0.70),
              (43.00, 60.0, 0.70)]

NARROW_NU = 1000.0
WIDE_NU = 100.0


def peak_curve(x, peaks, nu):
    """
    Sum of the peaks, using the same formula as MyModel::compute_narrow
    and MyModel::compute_wide: an amplitude m (the "mass") and a width w
    give a contribution of (m/w)*shape((x-c)/w).
    """
    shape0 = t_shape(nu, 0.0)
    y = np.zeros_like(x)
    for c, h, w in peaks:
        mass = h * w / shape0
        y += (mass / w) * t_shape(nu, (x - c) / w)
    return y


def background(x, level, n_knots):
    """
    Piecewise linear background, as in MyModel::compute_bg. The knots sit
    at x_min, 10, 40 and x_max; the value at a knot is
    level*exp(n_knots[i]).
    """
    xk = np.array([x.min(), 10.0, 40.0, x.max()], dtype=float)
    vk = level * np.exp(np.asarray(n_knots, dtype=float))
    y = np.zeros_like(x)
    for i in range(len(xk) - 1):
        mask = (x >= xk[i]) & (x <= xk[i + 1])
        if not np.any(mask):
            continue
        lam = (x[mask] - xk[i]) / (xk[i + 1] - xk[i])
        y[mask] = (1.0 - lam) * vk[i] + lam * vk[i + 1]
    return y


def make_header(n_narrow_max, n_wide_max, n_points):
    """
    The column names, in the same order as MyModel::description.
    """
    names = ["background"]
    names += ["n_knots[{0}]".format(i) for i in range(4)]
    names += ["dim_peaks1", "max_num_peaks1", "location_log_amplitude1",
              "scale_log_amplitude1", "location_log_width1",
              "scale_log_width1", "num_peaks1"]
    names += ["center1[{0}]".format(i) for i in range(n_narrow_max)]
    names += ["log_amplitude1[{0}]".format(i) for i in range(n_narrow_max)]
    names += ["width1[{0}]".format(i) for i in range(n_narrow_max)]
    names += ["dim_peaks2", "max_num_peaks2", "location_log_amplitude2",
              "scale_log_amplitude2", "location_log_width2",
              "scale_log_width2", "num_peaks2"]
    names += ["center2[{0}]".format(i) for i in range(n_wide_max)]
    names += ["log_amplitude2[{0}]".format(i) for i in range(n_wide_max)]
    names += ["width2[{0}]".format(i) for i in range(n_wide_max)]
    names += ["peak_shape", "sigma0", "sigma1", "nu"]
    for block in ("bg", "narrow", "wide", "model_curve"):
        names += ["{0}[{1}]".format(block, i) for i in range(n_points)]
    return names


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="demo", help="output folder")
    p.add_argument("--xmin", type=float, default=33.0)
    p.add_argument("--xmax", type=float, default=46.0)
    p.add_argument("--step", type=float, default=0.01)
    p.add_argument("--samples", type=int, default=200,
                   help="number of posterior samples to fake")
    p.add_argument("--seed", type=int, default=3)
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    n = int(round((args.xmax - args.xmin) / args.step)) + 1
    x = args.xmin + args.step * np.arange(n)

    n_narrow_max = 12
    n_wide_max = 4

    header = make_header(n_narrow_max, n_wide_max, n)
    rows = []

    for s in range(args.samples):
        # Jitter the peak positions, heights and widths
        narrow = [(c + rng.normal(0.0, 0.015),
                   h * np.exp(rng.normal(0.0, 0.09)),
                   w * np.exp(rng.normal(0.0, 0.05)))
                  for c, h, w in NARROW_PEAKS]
        wide = [(c + rng.normal(0.0, 0.08),
                 h * np.exp(rng.normal(0.0, 0.12)),
                 w * np.exp(rng.normal(0.0, 0.09)))
                for c, h, w in WIDE_PEAKS]

        level = 2.0 * np.exp(rng.normal(0.0, 0.2))
        bg = background(x, level, [0.0, 0.0, 0.2, 0.4])
        narrow_curve = peak_curve(x, narrow, NARROW_NU)
        wide_curve = peak_curve(x, wide, WIDE_NU)
        model = bg + narrow_curve + wide_curve

        row = [level]
        row += [0.0, 0.0, 0.2, 0.4]
        row += [3, n_narrow_max, 0.0, 1.0, 0.0, 0.02, len(narrow)]
        row += [p[0] for p in narrow] + [0.0] * (n_narrow_max - len(narrow))
        row += [np.log(p[1] * p[2] / t_shape(NARROW_NU, 0.0)) for p in narrow]
        row += [0.0] * (n_narrow_max - len(narrow))
        row += [p[2] for p in narrow] + [0.0] * (n_narrow_max - len(narrow))
        row += [3, n_wide_max, 0.0, 1.0, 0.0, 0.05, len(wide)]
        row += [p[0] for p in wide] + [0.0] * (n_wide_max - len(wide))
        row += [np.log(p[1] * p[2] / t_shape(WIDE_NU, 0.0)) for p in wide]
        row += [0.0] * (n_wide_max - len(wide))
        row += [p[2] for p in wide] + [0.0] * (n_wide_max - len(wide))
        row += [np.log(NARROW_NU), 1.0, 1.0, 100.0]
        row += list(bg) + list(narrow_curve) + list(wide_curve) + list(model)
        rows.append(row)

    rows = np.asarray(rows)

    # The "experimental" data: the mean model plus heavy-tailed noise
    mean_model = rows[:, -n:].mean(axis=0)
    nu = 5.0
    noise = rng.standard_t(nu, size=n) * (1.0 + 0.05 * mean_model)
    data = mean_model + noise
    data = np.clip(data, 0.0, None)

    data_file = os.path.join(args.out, "demo_data.txt")
    np.savetxt(data_file, np.column_stack((x, data)), fmt="%.8e")
    print("Wrote {0}".format(data_file))

    post_file = os.path.join(args.out, "demo_posterior_sample.txt")
    with open(post_file, "w") as f:
        f.write("#" + ",".join(header) + "\n")
        np.savetxt(f, rows, fmt="%.7e")
    print("Wrote {0}".format(post_file))


if __name__ == "__main__":
    main()
