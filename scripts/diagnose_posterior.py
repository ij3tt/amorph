"""
Diagnose the posterior of an AMORPH run: is the amorphous fraction well
determined, or does part of the posterior describe the amorphous hump with
narrow peaks instead?

Run it on a folder with the output of the sampler after the DNest4
post-processing (showresults.py or summarize_run.py):

    python diagnose_posterior.py RUN_FOLDER --data RUN_FOLDER/data.txt \
        --json diagnosis.json --table particles.csv.gz

It reads sample.txt, sample_info.txt and weights.txt (every saved particle
with its posterior weight) and posterior_sample.txt, and reports

- the posterior quantiles of the amorphous fraction and the weight of the
  posterior with a fraction of 0, below 0.2 and below 0.45;
- for each of these bands of the fraction: the number of particles, their
  weight, and the median log likelihood, number of narrow peaks, shape nu of
  the narrow peaks and misfit (RMS of model - data);
- the weight of particles with a number of narrow peaks near its maximum,
  which shows that the prior limit, not the data, sets that number;
- the posterior of the noise parameters and of nu of the narrow peaks.

--table writes one row per saved particle with these quantities, a small
file instead of the hundreds of megabytes of sample.txt.
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import amorph_stats

# Bands of the amorphous fraction: (name, lower bound, upper bound)
BANDS = [("0", 0.0, 0.0), ("(0, 0.2)", 0.0, 0.2), ("[0.2, 0.45)", 0.2, 0.45),
         (">= 0.45", 0.45, 1.0)]

# A number of narrow peaks at least this share of the maximum is "at the cap"
AT_CAP = 0.9


def column_names(filename):
    """
    The column names in the first line of a DNest4 output file.
    """
    with open(filename) as f:
        line = f.readline()
    names = [n.strip() for n in line.lstrip("#").split(",")]
    return [n for n in names if n]


def read_columns(filename, columns):
    """
    The given columns of a DNest4 output file. Some values there are
    separated by two spaces, and posterior_sample.txt has a second, empty
    header line, so split on any whitespace and skip lines starting with #.
    """
    table = pd.read_csv(filename, sep=r"\s+", header=None, comment="#",
                        usecols=columns, engine="c", dtype=np.float64)
    return table[columns].to_numpy()


def block(indices, first, n):
    return list(range(indices[first], indices[first] + n))


def weighted_quantiles(values, weights, qs):
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    cumulative /= cumulative[-1]
    return [float(np.interp(q, cumulative, values[order])) for q in qs]


def summary(values, weights):
    """
    Weighted median and 16% and 84% quantiles.
    """
    q16, q50, q84 = weighted_quantiles(values, weights, [0.16, 0.5, 0.84])
    return {"median": q50, "q16": q16, "q84": q84}


def in_band(fraction, band):
    name, low, high = band
    if name == "0":
        return fraction == 0.0
    if high >= 1.0:
        return fraction >= low
    return (fraction > low) & (fraction < high) if low == 0.0 \
        else (fraction >= low) & (fraction < high)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder", help="folder with the output of the sampler")
    p.add_argument("--data", required=True,
                   help="the two-column data file that was analysed")
    p.add_argument("--json", help="write the diagnosis to this JSON file")
    p.add_argument("--table", help="write one row per saved particle to this "
                                   "CSV file (.gz to compress it)")
    args = p.parse_args()

    def path(name):
        return os.path.join(args.folder, name)

    x, y = amorph_stats.load_data(args.data)
    n = x.size

    # Every saved particle, with its posterior weight
    names = column_names(path("sample.txt"))
    indices = {name: i for i, name in enumerate(names)}
    scalars = ["num_peaks1", "num_peaks2", "max_num_peaks1", "max_num_peaks2",
               "peak_shape", "nu", "sigma0", "sigma1", "background"]
    columns = ([indices[s] for s in scalars] + block(indices, "wide[0]", n)
               + block(indices, "narrow[0]", n))
    values = read_columns(path("sample.txt"), columns)
    info = np.atleast_2d(np.loadtxt(path("sample_info.txt"), comments="#"))
    weights = np.atleast_1d(np.loadtxt(path("weights.txt")))
    m = min(len(values), len(info), len(weights))
    values, info, weights = values[:m], info[:m], weights[:m]
    weights = weights / weights.sum()

    particles = pd.DataFrame({s: values[:, i] for i, s in enumerate(scalars)})
    wide = values[:, len(scalars):len(scalars) + n]
    narrow = values[:, len(scalars) + n:]
    particles["log_likelihood"] = info[:, 1]
    particles["weight"] = weights
    particles["nu_narrow"] = np.exp(particles["peak_shape"])
    particles["fraction"] = amorph_stats.amorphous_fraction(wide, narrow, x)
    fraction = particles["fraction"].to_numpy()
    defined = ~np.isnan(fraction)
    max_narrow = int(particles["max_num_peaks1"].iloc[0])
    at_cap = particles["num_peaks1"].to_numpy() >= AT_CAP * max_narrow

    # The misfit of the equally weighted posterior samples
    post_names = column_names(path("posterior_sample.txt"))
    post_indices = {name: i for i, name in enumerate(post_names)}
    post = read_columns(path("posterior_sample.txt"),
                        block(post_indices, "wide[0]", n)
                        + block(post_indices, "narrow[0]", n)
                        + block(post_indices, "model_curve[0]", n))
    post_fraction = amorph_stats.amorphous_fraction(post[:, :n],
                                                    post[:, n:2 * n], x)
    rms = np.sqrt(((post[:, 2 * n:] - y)**2).mean(axis=1))

    w = weights[defined]
    result = {
        "saves": int(m),
        "effective_sample_size": float(np.exp(-np.sum(weights
                                       * np.log(weights + 1E-300)))),
        "max_num_narrow_peaks": max_narrow,
        "max_num_wide_peaks": int(particles["max_num_peaks2"].iloc[0]),
        "fraction": dict(zip(["q05", "q16", "q25", "q50", "q75", "q84", "q95"],
                             weighted_quantiles(fraction[defined], w,
                                                [0.05, 0.16, 0.25, 0.5,
                                                 0.75, 0.84, 0.95]))),
        "weight_fraction_0": float(weights[fraction == 0.0].sum()),
        "weight_fraction_below_0.2": float(weights[defined
                                                   & (fraction < 0.2)].sum()),
        "weight_fraction_below_0.45": float(weights[defined
                                                    & (fraction < 0.45)].sum()),
        "weight_narrow_at_cap": float(weights[at_cap].sum()),
        "nu_narrow": summary(particles["nu_narrow"].to_numpy(), weights),
        "nu": summary(particles["nu"].to_numpy(), weights),
        "sigma0": summary(particles["sigma0"].to_numpy(), weights),
        "sigma1": summary(particles["sigma1"].to_numpy(), weights),
        "num_narrow_peaks": summary(particles["num_peaks1"].to_numpy(),
                                    weights),
        "bands": [],
    }
    hist, edges = np.histogram(fraction[defined], bins=20, range=(0.0, 1.0),
                               weights=w)
    result["histogram"] = {"edges": edges.tolist(), "weights": hist.tolist()}

    # Within each band the medians are weighted by the posterior weight: the
    # saved particles come from all the levels of the sampler, and plain
    # medians would mix in the early, nearly prior ones.
    for band in BANDS:
        sel = in_band(fraction, band)
        post_sel = in_band(post_fraction, band)
        entry = {"band": band[0], "particles": int(sel.sum()),
                 "weight": float(weights[sel].sum())}
        if sel.any():
            entry["max_log_likelihood"] = \
                float(particles["log_likelihood"][sel].max())
        if weights[sel].sum() > 0.0:
            for key, column in (("log_likelihood", "log_likelihood"),
                                ("narrow_peaks", "num_peaks1"),
                                ("nu_narrow", "nu_narrow")):
                entry[key] = summary(particles[column].to_numpy()[sel],
                                     weights[sel])["median"]
        if post_sel.any():
            entry["rms"] = float(np.mean(rms[post_sel]))
            entry["posterior_samples"] = int(post_sel.sum())
        result["bands"].append(entry)

    # Report
    f = result["fraction"]
    print("Saved particles: {0}, effective sample size {1:.0f}".format(
        m, result["effective_sample_size"]))
    print("Amorphous fraction: median {0:.3f}, 50% interval [{1:.3f}, "
          "{2:.3f}], 90% interval [{3:.3f}, {4:.3f}]".format(
              f["q50"], f["q25"], f["q75"], f["q05"], f["q95"]))
    print("Posterior weight with fraction 0: {0:.2%}, below 0.2: {1:.2%}, "
          "below 0.45: {2:.2%}".format(result["weight_fraction_0"],
                                       result["weight_fraction_below_0.2"],
                                       result["weight_fraction_below_0.45"]))
    print("Posterior weight with at least {0:.0f} of {1} narrow peaks: "
          "{2:.2%}".format(AT_CAP * max_narrow, max_narrow,
                           result["weight_narrow_at_cap"]))
    print("Per band of the fraction: posterior weight, and weighted medians "
          "of logL, number of narrow peaks and their nu; the highest logL; "
          "the mean RMS of model - data of the posterior samples")
    print("{0:12s} {1:>9s} {2:>8s} {3:>9s} {4:>9s} {5:>7s} {6:>9s} "
          "{7:>7s}".format("fraction", "particles", "weight", "logL",
                           "max logL", "narrow", "nu_narrow", "RMS"))

    def fmt(entry, key, form):
        return form.format(entry[key]) if key in entry else "-"

    for e in result["bands"]:
        print("{0:12s} {1:9d} {2:8.2%} {3:>9s} {4:>9s} {5:>7s} {6:>9s} "
              "{7:>7s}".format(e["band"], e["particles"], e["weight"],
                               fmt(e, "log_likelihood", "{0:.1f}"),
                               fmt(e, "max_log_likelihood", "{0:.1f}"),
                               fmt(e, "narrow_peaks", "{0:.0f}"),
                               fmt(e, "nu_narrow", "{0:.3g}"),
                               fmt(e, "rms", "{0:.3f}")))
    for key in ("nu_narrow", "nu", "sigma0", "sigma1", "num_narrow_peaks"):
        s = result[key]
        print("{0}: {1:.3g} [{2:.3g}, {3:.3g}]".format(key, s["median"],
                                                      s["q16"], s["q84"]))

    if args.json:
        with open(args.json, "w") as fout:
            json.dump(result, fout, indent=2)
    if args.table:
        particles.drop(columns=["max_num_peaks1", "max_num_peaks2"]).to_csv(
            args.table, index=False, float_format="%.6g")


if __name__ == "__main__":
    main()
