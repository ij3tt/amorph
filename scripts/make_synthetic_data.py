"""
Create two synthetic scans with a known amorphous fraction: one fully
amorphous (only the halo, fraction 1) and one fully crystalline (only the
narrow peaks, fraction 0).

They test AMORPH at the two ends of the scale, where the true answer is
known exactly. Both scans have the same background and the same grid, like
the 50% standard: Cu K-alpha, 10-40 degrees 2theta, step 0.02, counts of a
few seconds a step. The peaks have the shapes of the model (see
make_demo_posterior.py), so the model can describe each scan exactly:

* the halo is two wide peaks (nu = 100, nearly Gaussian), centred within
  the default left_edge and right_edge (0.3-0.7 of the range, 19-31 deg);
* the crystalline peaks are Student-t profiles with nu = 3 at positions
  like those of quartz and feldspar, all of the same width (FWHM 0.13 deg);
* the background is a straight line, as with control_points [10, 40];
* the counts are Poisson.

    python make_synthetic_data.py --out ../src

writes synthetic_amorphous.dat and synthetic_crystalline.dat.
"""

import argparse
import os
import numpy as np

from make_demo_posterior import peak_curve


# Background: counts at 10 and at 40 degrees
BACKGROUND = (45.0, 55.0)

# Amorphous (wide) peaks: position, height, width
WIDE_PEAKS = [(24.0, 110.0, 3.5),
              (30.0, 25.0, 3.0)]
WIDE_NU = 100.0

# Crystalline (narrow) peaks: position, height, width
NARROW_PEAKS = [(13.87, 120.0, 0.06),
                (20.86, 300.0, 0.06),
                (22.04, 180.0, 0.06),
                (23.60, 110.0, 0.06),
                (24.24, 90.0, 0.06),
                (26.64, 1400.0, 0.06),
                (27.94, 700.0, 0.06),
                (30.15, 130.0, 0.06),
                (36.54, 110.0, 0.06),
                (39.46, 120.0, 0.06)]
NARROW_NU = 3.0


def write_scan(path, x, counts, title, fraction, seed):
    with open(path, "w", newline="\n") as f:
        f.write("# Synthetic scan: {0}\n".format(title))
        f.write("# True amorphous fraction: {0:.1f}\n".format(fraction))
        f.write("# Made by scripts/make_synthetic_data.py, seed {0}\n"
                .format(seed))
        for xi, yi in zip(x, counts):
            f.write("{0:.2f} {1:d}\n".format(xi, yi))
    print("Wrote {0}".format(path))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=".", help="output folder")
    p.add_argument("--xmin", type=float, default=10.0)
    p.add_argument("--xmax", type=float, default=40.0)
    p.add_argument("--step", type=float, default=0.02)
    p.add_argument("--seed", type=int, default=1)
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    n = int(round((args.xmax - args.xmin) / args.step)) + 1
    x = args.xmin + args.step * np.arange(n)

    lam = (x - args.xmin) / (args.xmax - args.xmin)
    bg = (1.0 - lam) * BACKGROUND[0] + lam * BACKGROUND[1]

    scans = [("synthetic_amorphous.dat", "fully amorphous", 1.0,
              peak_curve(x, WIDE_PEAKS, WIDE_NU)),
             ("synthetic_crystalline.dat", "fully crystalline", 0.0,
              peak_curve(x, NARROW_PEAKS, NARROW_NU))]
    for name, title, fraction, peaks in scans:
        counts = rng.poisson(bg + peaks)
        write_scan(os.path.join(args.out, name), x, counts, title, fraction,
                   args.seed)


if __name__ == "__main__":
    main()
