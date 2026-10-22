"""
Summarise one AMORPH run for the validation workflow
(.github/workflows/validate.yml).

Run it in the folder holding the output of the sampler (sample.txt,
sample_info.txt, levels.txt), also when the sampler was stopped part-way.
It does the DNest4 post-processing, which writes posterior_sample.txt, and
stores posterior summaries of the noise parameters and of the quantities
that display.py reports in a JSON file.

    python summarize_run.py --data easy_data.txt --out summary.json
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
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


def complete_lines(lines, num_values):
    """
    The data lines (not comments) that were written completely: they end
    with a newline and hold num_values values.
    """
    return [l for l in lines if not l.startswith("#")
            and l.endswith("\n") and len(l.split()) == num_values]


def trim_outputs():
    """
    Make the output of a sampler that was stopped part-way consistent. Each
    save appends a line to sample.txt and then one to sample_info.txt, so
    the last of them may be cut off or missing: keep the samples that are
    complete in both files. levels.txt is rewritten at every save, so its
    last line may be cut off too. Returns the number of samples kept.
    """
    with open("levels.txt") as f:
        lines = f.readlines()
    levels = complete_lines(lines, 7)
    if not levels:
        raise SystemExit("levels.txt holds no complete levels")
    with open("levels.txt", "w") as f:
        f.writelines([l for l in lines if l.startswith("#")] + levels)

    with open("sample_info.txt") as f:
        lines = f.readlines()
    header = [l for l in lines if l.startswith("#")]
    info = complete_lines(lines, 4)

    # Where the complete lines of sample.txt end. They hold as many values
    # (each followed by a space) as the first one.
    ends = []
    num_values = None
    offset = 0
    with open("sample.txt", "rb") as f:
        for line in f:
            offset += len(line)
            if line.startswith(b"#"):
                continue
            if num_values is None:
                num_values = line.count(b" ")
            if not line.endswith(b"\n") or line.count(b" ") != num_values:
                break
            ends.append(offset)

    keep = min(len(info), len(ends))
    if keep == 0:
        raise SystemExit("The sampler saved no complete samples")
    with open("sample_info.txt", "w") as f:
        f.writelines(header + info[:keep])
    os.truncate("sample.txt", ends[keep - 1])
    return keep


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", required=True,
                   help="the two-column data file that was analysed")
    p.add_argument("--out", required=True, help="the JSON file to write")
    p.add_argument("--seconds", type=int, default=0,
                   help="run time of the sampler, for the record")
    p.add_argument("--stopped", action="store_true",
                   help="the sampler was stopped before it finished")
    args = p.parse_args()

    saves = trim_outputs()
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
    wide_integral = wide.sum(axis=1)
    narrow_integral = narrow.sum(axis=1)

    # A sample without a wide component is 0% amorphous, not missing
    total = wide_integral + narrow_integral
    fraction = np.full(total.shape, np.nan)
    fraction[total > 0.0] = wide_integral[total > 0.0] / total[total > 0.0]

    # Centre of mass and half-width of the wide component, where there is one
    has_wide = wide_integral > 0.0
    f = wide[has_wide] / wide_integral[has_wide, None]
    center = np.full(wide_integral.shape, np.nan)
    width = np.full(wide_integral.shape, np.nan)
    center[has_wide] = (f * x).sum(axis=1)
    width[has_wide] = np.sqrt((f * (x - center[has_wide, None])**2).sum(axis=1))

    result = {
        "data": args.data,
        "seconds": args.seconds,
        "saves": saves,
        "stopped": args.stopped,
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
