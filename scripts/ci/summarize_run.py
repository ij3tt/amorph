"""
Summarise one AMORPH run for the validation workflow
(.github/workflows/validate.yml).

Run it in the folder holding the output of the sampler (sample.txt,
sample_info.txt, levels.txt). It does the DNest4 post-processing, which
writes posterior_sample.txt, and stores posterior summaries of the noise
parameters and of the quantities that display.py reports in a JSON file.

    python summarize_run.py --data easy_data.txt --out summary.json
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
import amorph_stats
import dnest_functions as dn4


def summary(values):
    """
    Median, 16% and 84% quantiles, mean and size of the finite values.
    """
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return None
    q16, q50, q84 = np.percentile(v, [16.0, 50.0, 84.0])
    return {"median": float(q50), "q16": float(q16), "q84": float(q84),
            "mean": float(v.mean()), "n": int(v.size)}


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", required=True,
                   help="the two-column data file that was analysed")
    p.add_argument("--out", required=True, help="the JSON file to write")
    p.add_argument("--seconds", type=int, default=0,
                   help="run time of the sampler, for the record")
    args = p.parse_args()

    logz, information, _ = dn4.postprocess(plot=False)

    x = np.loadtxt(args.data, comments="#")[:, 0]
    n = x.size

    indices = dn4.load_column_names("posterior_sample.txt")["indices"]
    posterior = np.atleast_2d(np.loadtxt("posterior_sample.txt"))

    def curve(first):
        start = indices[first]
        return posterior[:, start:start + n]

    wide = curve("wide[0]")
    narrow = curve("narrow[0]")
    fraction = amorph_stats.amorphous_fraction(wide, narrow)
    center, width, _, _ = amorph_stats.wide_component_shape(x, wide)
    has_wide = wide.sum(axis=1) > 0.0

    result = {
        "data": args.data,
        "seconds": args.seconds,
        "n_data": int(n),
        "n_posterior": int(posterior.shape[0]),
        "log_z": float(logz),
        "information": float(information),
        "no_wide_component": float(np.mean(~has_wide)),
        "quantities": {
            "amorphous_fraction": summary(fraction),
            "wide_center_of_mass": summary(center),
            "wide_halfwidth": summary(width),
            "nu": summary(posterior[:, indices["nu"]]),
            "sigma0": summary(posterior[:, indices["sigma0"]]),
            "sigma1": summary(posterior[:, indices["sigma1"]]),
            "num_narrow_peaks": summary(posterior[:, indices["num_peaks1"]]),
            "num_wide_peaks": summary(posterior[:, indices["num_peaks2"]]),
        },
    }

    with open(args.out, "w") as fout:
        json.dump(result, fout, indent=2)


if __name__ == "__main__":
    main()
