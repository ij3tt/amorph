"""
The results of an AMORPH run, as numbers and as figures.

    results = amorph_results.from_run("path/to/run")

reads what the sampler and the DNest4 post-processing left in the folder of
a run and computes everything that showresults.py and
scripts/diagnose_posterior.py report. report_lines(results) is the text of
the report, and each entry of FIGURES draws one figure on a matplotlib
Figure, so that the same figures can be shown in a window, saved to a file
or embedded in a program. amorph_archive.py stores the results in one
compressed file and reads them back, with the same report and figures.

The parts of the results that the folder has no files for are None:

- sampler: log(X) and the posterior weight of each saved sample, log(Z),
  the information and the effective sample size (levels.txt and
  sample_info.txt);
- particles and peaks: one row per saved sample, and its peaks
  (sample.txt and sample_info.txt, with levels.txt or weights.txt for the
  weights);
- posterior and curves: one row per posterior sample, and summaries of
  their curves (posterior_sample.txt);
- diagnosis: what scripts/diagnose_posterior.py reports (particles).
"""

import datetime
import os

import numpy as np
import pandas as pd
import yaml

import amorph_stats
import dnest_functions

# Quantiles of the curves of the posterior samples
CURVE_QUANTILES = [0.05, 0.16, 0.5, 0.84, 0.95]

# Quantiles of the amorphous fraction in the diagnosis
FRACTION_QUANTILES = [0.05, 0.16, 0.25, 0.5, 0.75, 0.84, 0.95]
FRACTION_QUANTILE_NAMES = ["q05", "q16", "q25", "q50", "q75", "q84", "q95"]

# Bands of the amorphous fraction: (name, lower bound, upper bound)
BANDS = [("0", 0.0, 0.0), ("(0, 0.2)", 0.0, 0.2), ("[0.2, 0.45)", 0.2, 0.45),
         (">= 0.45", 0.45, 1.0)]

# A number of narrow peaks at least this share of the maximum is "at the cap"
AT_CAP = 0.9

# The number of posterior samples drawn in the figure of the model
NUM_EXAMPLES = 50

# The curves of a sample, as the sampler names them
CURVES = ["bg", "wide", "narrow", "model_curve"]

# The scalars of a sample, as the sampler names them
SCALARS = ["background", "num_peaks1", "num_peaks2", "max_num_peaks1",
           "max_num_peaks2", "peak_shape", "sigma0", "sigma1", "nu"]

# The shape of the wide component (amorph_stats.wide_component_shape)
SHAPE = ["wide_center_of_mass", "wide_halfwidth", "wide_skewness",
         "wide_nongaussianity"]

# Number of rows of sample.txt and posterior_sample.txt read at a time
CHUNK_SIZE = 200


class Results(object):
    """
    The results of one run; see the documentation of the module.
    attachments holds the files of the run that an archive keeps as they
    are, by their name in the archive.
    """

    def __init__(self):
        self.info = {}
        self.x = None
        self.y = None
        self.sampler = None
        self.particles = None
        self.peaks = None
        self.posterior = None
        self.curves = None
        self.diagnosis = None
        self.attachments = {}


def parse_table(text):
    """
    The rows of a DNest4 output file such as levels.txt or sample_info.txt,
    as an array. Comment lines are skipped, and the rows end at the first
    line with a different number of values: the last line of a sampler that
    was stopped while writing it.
    """
    rows = []
    for line in text.splitlines():
        cells = line.split()
        if not cells or cells[0].startswith("#"):
            continue
        if rows and len(cells) != len(rows[0]):
            break
        rows.append([float(c) for c in cells])
    return np.atleast_2d(np.array(rows, dtype=float))


def column_names(filename):
    """
    The column names in the first line of a DNest4 output file.
    """
    with open(filename) as f:
        line = f.readline()
    names = [n.strip() for n in line.lstrip("#").split(",")]
    return [n for n in names if n]


def block(name, n):
    """
    The names of the columns name[0] to name[n - 1].
    """
    return ["{0}[{1}]".format(name, i) for i in range(n)]


def read_rows(filename, names, wanted, chunk_size=CHUNK_SIZE):
    """
    The columns `wanted` of the data lines of a DNest4 output file whose
    columns are `names`, chunk_size rows at a time, in the order of
    `wanted`. Some values there are separated by two spaces, and
    posterior_sample.txt has a second, empty header line, so split on any
    whitespace and skip lines starting with #.
    """
    indices = {name: i for i, name in enumerate(names)}
    columns = [indices[w] for w in wanted]
    reader = pd.read_csv(filename, sep=r"\s+", header=None, comment="#",
                         usecols=columns, engine="c", dtype=np.float64,
                         chunksize=chunk_size)
    for chunk in reader:
        yield chunk[columns].to_numpy()


def describe(values):
    """
    Mean, standard deviation, median, 16% and 84% quantiles and number of
    the finite values, or None if there are none.
    """
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return None
    q16, q50, q84 = np.percentile(v, [16.0, 50.0, 84.0])
    return {"mean": float(v.mean()), "std": float(v.std()),
            "median": float(q50), "q16": float(q16), "q84": float(q84),
            "n": int(v.size)}


def weighted_quantiles(values, weights, qs):
    order = np.argsort(values)
    cumulative = np.cumsum(weights[order])
    cumulative /= cumulative[-1]
    return [float(np.interp(q, cumulative, values[order])) for q in qs]


def weighted_summary(values, weights):
    """
    Weighted median and 16% and 84% quantiles.
    """
    q16, q50, q84 = weighted_quantiles(values, weights, [0.16, 0.5, 0.84])
    return {"median": q50, "q16": q16, "q84": q84}


def sampler_results(levels, sample_info):
    """
    What the DNest4 post-processing reports about the sampler: log(X) and
    the posterior weight of each saved sample, log(Z), the information and
    the effective sample size. They are computed as
    dnest_functions.postprocess computes them, without changing the state
    of the random numbers, which seeds its resampling.
    """
    state = np.random.get_state()
    try:
        log_x, weights, log_z, information, _ = \
            dnest_functions.log_x_and_weights(levels, sample_info)
    finally:
        np.random.set_state(state)
    weights = weights[:, 0] / weights[:, 0].sum()
    return {"levels": levels, "sample_info": sample_info,
            "log_x": log_x[:, 0], "weight": weights,
            "log_z": float(log_z[0, 0]),
            "information": float(information[0, 0]),
            "effective_sample_size":
                float(np.exp(-np.sum(weights * np.log(weights + 1E-300))))}


def read_particles(filename, x, info_rows, weights, log_x, fraction_range):
    """
    One row per saved sample of sample.txt: its scalars, log likelihood,
    weight, amorphous fraction and the shape of its wide component, and the
    position, log amplitude and width of each of its peaks (component 1:
    narrow, 2: wide). info_rows are the rows of sample_info.txt and weights
    their posterior weights; log_x may be None. Returns the table, the peaks
    and the maximum numbers of narrow and wide peaks.
    """
    n = x.size
    names = column_names(filename)
    scalars = [s for s in SCALARS if s in names]
    maxima = [sum(1 for name in names if name.startswith(
        "center{0}[".format(k))) for k in (1, 2)]
    peak_columns = []
    for k, m in zip((1, 2), maxima):
        for quantity in ("center", "log_amplitude", "width"):
            peak_columns += block("{0}{1}".format(quantity, k), m)
    wanted = scalars + peak_columns + block("wide", n) + block("narrow", n)
    if fraction_range is not None:
        inside = (x >= fraction_range[0]) & (x <= fraction_range[1])

    num_rows = min(len(info_rows), len(weights))
    parts = {"scalars": [], "fraction": [], "shape": [], "in_range": []}
    peaks = {"particle": [], "component": [], "center": [],
             "log_amplitude": [], "width": []}
    done = 0
    for values in read_rows(filename, names, wanted):
        values = values[:num_rows - done]
        if values.shape[0] == 0:
            break
        s = values[:, :len(scalars)]
        p = values[:, len(scalars):len(scalars) + len(peak_columns)]
        wide = values[:, len(scalars) + len(peak_columns):][:, :n]
        narrow = values[:, len(scalars) + len(peak_columns) + n:]

        parts["scalars"].append(s)
        parts["fraction"].append(amorph_stats.amorphous_fraction(wide, narrow,
                                                                 x))
        parts["shape"].append(np.column_stack(
            amorph_stats.wide_component_shape(x, wide)))
        if fraction_range is not None:
            parts["in_range"].append(amorph_stats.amorphous_fraction(
                wide[:, inside], narrow[:, inside], x[inside]))

        # The peaks that are switched on come first in each block
        start = 0
        for k, m in zip((1, 2), maxima):
            name = "num_peaks{0}".format(k)
            if m == 0 or name not in scalars:
                start += 3 * m
                continue
            count = s[:, scalars.index(name)]
            on = np.arange(m)[None, :] < count[:, None]
            rows = np.nonzero(on)[0]
            peaks["particle"].append(rows + done)
            peaks["component"].append(np.full(rows.size, k))
            for j, quantity in enumerate(("center", "log_amplitude",
                                          "width")):
                peaks[quantity].append(
                    p[:, start + j * m:start + (j + 1) * m][on])
            start += 3 * m
        done += values.shape[0]

    if done == 0:
        raise ValueError("{0} holds no saved samples".format(filename))
    s = np.vstack(parts["scalars"])
    table = pd.DataFrame({name: s[:, i] for i, name in enumerate(scalars)
                          if not name.startswith("max_num_peaks")})
    if "peak_shape" in table:
        table["nu_narrow"] = np.exp(table["peak_shape"])
    table["level"] = info_rows[:done, 0]
    table["log_likelihood"] = info_rows[:done, 1]
    if log_x is not None:
        table["log_x"] = log_x[:done]
    w = np.asarray(weights[:done], dtype=float)
    table["weight"] = w / w.sum()
    table["fraction"] = np.concatenate(parts["fraction"])
    shape = np.vstack(parts["shape"])
    for i, name in enumerate(SHAPE):
        table[name] = shape[:, i]
    if fraction_range is not None:
        table["fraction_in_range"] = np.concatenate(parts["in_range"])

    peaks = {key: (np.concatenate(value) if value else np.zeros(0))
             for key, value in peaks.items()}
    peaks["particle"] = peaks["particle"].astype(np.int64)
    peaks["component"] = peaks["component"].astype(np.int8)
    for k, name in ((1, "max_num_peaks1"), (2, "max_num_peaks2")):
        if name in scalars:
            maxima[k - 1] = int(s[0, scalars.index(name)])
    return table, peaks, maxima


def read_posterior(filename, x, y):
    """
    One row per posterior sample of posterior_sample.txt: its numbers of
    peaks, noise parameters, amorphous fraction, the shape of its wide
    component and the RMS of model - data; and the mean, the quantiles
    CURVE_QUANTILES and the first NUM_EXAMPLES samples of each curve.
    Returns the table, the curves and the maximum number of narrow peaks
    (None if the file does not say).
    """
    n = x.size
    names = column_names(filename)
    scalars = [s for s in SCALARS if s in names]
    present = [c for c in CURVES if c + "[0]" in names]
    wanted = scalars + sum((block(c, n) for c in present), [])

    rows = {"scalars": [], "fraction": [], "shape": [], "rms": []}
    curves = {c: [] for c in present}
    for values in read_rows(filename, names, wanted):
        s = values[:, :len(scalars)]
        parts = {c: values[:, len(scalars) + i * n:len(scalars) + (i + 1) * n]
                 for i, c in enumerate(present)}
        rows["scalars"].append(s)
        if "wide" in parts and "narrow" in parts:
            rows["fraction"].append(amorph_stats.amorphous_fraction(
                parts["wide"], parts["narrow"], x))
        if "wide" in parts:
            rows["shape"].append(np.column_stack(
                amorph_stats.wide_component_shape(x, parts["wide"])))
        if "model_curve" in parts:
            rows["rms"].append(np.sqrt(((parts["model_curve"] - y)**2)
                                       .mean(axis=1)))
        for c in present:
            curves[c].append(parts[c].astype(np.float32))

    s = np.vstack(rows["scalars"])
    column = {name: s[:, i] for i, name in enumerate(scalars)}
    table = pd.DataFrame()
    for name, label in (("num_peaks1", "num_narrow_peaks"),
                        ("num_peaks2", "num_wide_peaks"),
                        ("background", "background"),
                        ("sigma0", "sigma0"), ("sigma1", "sigma1"),
                        ("nu", "nu")):
        if name in column:
            table[label] = column[name]
    if "peak_shape" in column:
        table["nu_narrow"] = np.exp(column["peak_shape"])
    if rows["fraction"]:
        table["fraction"] = np.concatenate(rows["fraction"])
    if rows["shape"]:
        shape = np.vstack(rows["shape"])
        for i, name in enumerate(SHAPE):
            table[name] = shape[:, i]
    if rows["rms"]:
        table["rms"] = np.concatenate(rows["rms"])

    summary = {"x": x, "y": y}
    for c in present:
        a = np.vstack(curves[c])
        summary[c + "_mean"] = a.mean(axis=0, dtype=np.float64)
        summary[c + "_quantiles"] = np.quantile(a, CURVE_QUANTILES,
                                                axis=0).astype(np.float32)
        summary[c + "_examples"] = a[:NUM_EXAMPLES]

    # The standardised residuals of the posterior mean model curve, with
    # the posterior means of sigma0 and sigma1. This is not ideal: really
    # there is a posterior distribution over residuals.
    if "model_curve" in present and "sigma0" in column and "sigma1" in column:
        curve = summary["model_curve_mean"]
        sd = np.sqrt(column["sigma0"].mean()**2 + column["sigma1"].mean()
                     * curve)
        summary["residuals"] = (curve - y) / sd

    max_narrow = int(column["max_num_peaks1"][0]) \
        if "max_num_peaks1" in column else None
    return table, summary, max_narrow


def in_band(fraction, band):
    _, low, high = band
    if high == 0.0:
        return fraction == 0.0
    if high == 1.0:
        return fraction >= low
    return (fraction > low) & (fraction < high) if low == 0.0 \
        else (fraction >= low) & (fraction < high)


def diagnose(particles, posterior, max_narrow, max_wide):
    """
    Is the amorphous fraction well determined, or does part of the
    posterior describe the amorphous hump with narrow peaks instead? The
    posterior quantiles of the fraction, the weight with a fraction of 0,
    below 0.2 and below 0.45, the weight at the cap of narrow peaks, and per
    band of the fraction the weight and the weighted medians of the log
    likelihood, of the number of narrow peaks and of their nu, with the RMS
    of model - data of the posterior samples in the band.
    """
    weights = particles["weight"].to_numpy()
    fraction = particles["fraction"].to_numpy()
    defined = ~np.isnan(fraction)
    w = weights[defined]
    num_narrow = particles["num_peaks1"].to_numpy()
    at_cap = num_narrow >= AT_CAP * max_narrow

    def summarise(column):
        if column not in particles:
            return None
        return weighted_summary(particles[column].to_numpy(), weights)

    result = {
        "saves": int(len(particles)),
        "effective_sample_size": float(np.exp(-np.sum(
            weights * np.log(weights + 1E-300)))),
        "max_num_narrow_peaks": int(max_narrow),
        "max_num_wide_peaks": int(max_wide),
        "fraction": dict(zip(FRACTION_QUANTILE_NAMES,
                             weighted_quantiles(fraction[defined], w,
                                                FRACTION_QUANTILES))),
        "weight_fraction_0": float(weights[fraction == 0.0].sum()),
        "weight_fraction_below_0.2": float(weights[defined
                                                   & (fraction < 0.2)].sum()),
        "weight_fraction_below_0.45": float(weights[defined
                                                    & (fraction < 0.45)].sum()),
        "weight_narrow_at_cap": float(weights[at_cap].sum()),
        "nu_narrow": summarise("nu_narrow"),
        "nu": summarise("nu"),
        "sigma0": summarise("sigma0"),
        "sigma1": summarise("sigma1"),
        "num_narrow_peaks": summarise("num_peaks1"),
        "bands": [],
    }
    if "fraction_in_range" in particles:
        part = particles["fraction_in_range"].to_numpy()
        ok = ~np.isnan(part)
        result["fraction_in_range"] = dict(
            [("range", None)]
            + list(zip(FRACTION_QUANTILE_NAMES,
                       weighted_quantiles(part[ok], weights[ok],
                                          FRACTION_QUANTILES))))
    hist, edges = np.histogram(fraction[defined], bins=20, range=(0.0, 1.0),
                               weights=w)
    result["histogram"] = {"edges": edges.tolist(), "weights": hist.tolist()}

    # Within each band the medians are weighted by the posterior weight: the
    # saved particles come from all the levels of the sampler, and plain
    # medians would mix in the early, nearly prior ones.
    log_l = particles["log_likelihood"].to_numpy()
    for band in BANDS:
        sel = in_band(fraction, band)
        entry = {"band": band[0], "particles": int(sel.sum()),
                 "weight": float(weights[sel].sum())}
        if sel.any():
            entry["max_log_likelihood"] = float(log_l[sel].max())
        if weights[sel].sum() > 0.0:
            for key, column in (("log_likelihood", "log_likelihood"),
                                ("narrow_peaks", "num_peaks1"),
                                ("nu_narrow", "nu_narrow")):
                if column in particles:
                    entry[key] = weighted_summary(
                        particles[column].to_numpy()[sel],
                        weights[sel])["median"]
        if posterior is not None and "fraction" in posterior \
                and "rms" in posterior:
            post_sel = in_band(posterior["fraction"].to_numpy(), band)
            if post_sel.any():
                entry["rms"] = float(posterior["rms"].to_numpy()[post_sel]
                                     .mean())
                entry["posterior_samples"] = int(post_sel.sum())
        result["bands"].append(entry)
    return result


def from_run(folder=".", data_file=None, fraction_range=None):
    """
    The results of the run in folder. The data file is the one config.yaml
    names, unless data_file gives one (a path from the current directory).
    With fraction_range=(low, high), the particles and the diagnosis also
    give the amorphous fraction within that range of x.
    """
    def path(name):
        return os.path.join(folder, name)

    def read_bytes(name):
        with open(name, "rb") as f:
            return f.read()

    results = Results()
    config = {}
    if os.path.isfile(path("config.yaml")):
        results.attachments["input/config.yaml"] = \
            read_bytes(path("config.yaml"))
        config = yaml.safe_load(results.attachments["input/config.yaml"]) \
            or {}
    if data_file is None:
        if "data_file" not in config:
            raise ValueError("{0}: no config.yaml that names the data file"
                             .format(folder))
        data_file = path(config["data_file"])
    results.x, results.y = amorph_stats.load_data(data_file)
    x = results.x
    results.attachments["input/" + os.path.basename(data_file)] = \
        read_bytes(data_file)
    options = config.get("dnest4_options_file")
    if isinstance(options, str) and os.path.isfile(path(options)):
        results.attachments["input/" + os.path.basename(options)] = \
            read_bytes(path(options))

    results.info = {
        "data_file": os.path.basename(data_file),
        "num_points": int(x.size),
        "x_min": float(x[0]),
        "x_max": float(x[-1]),
        "config": config,
        "seed": amorph_stats.postprocessing_seed(path("config.yaml")),
        "fraction_range": None if fraction_range is None
        else [float(fraction_range[0]), float(fraction_range[1])],
    }
    if os.path.isfile(path("sample_info.txt")):
        results.info["last_save"] = datetime.datetime.fromtimestamp(
            os.path.getmtime(path("sample_info.txt"))).isoformat(
                timespec="seconds")
    for name, archived in (("levels.txt", "dnest4/levels.txt"),
                           ("sample_info.txt", "dnest4/sample_info.txt"),
                           ("weights.txt", "dnest4/weights.txt"),
                           ("run.log", "log/run.log")):
        if os.path.isfile(path(name)):
            results.attachments[archived] = read_bytes(path(name))

    # The sampler: log(X) and weights of the saved samples
    info_rows = None
    if "dnest4/sample_info.txt" in results.attachments:
        info_rows = parse_table(
            results.attachments["dnest4/sample_info.txt"].decode())
    if "dnest4/levels.txt" in results.attachments and info_rows is not None:
        levels = parse_table(results.attachments["dnest4/levels.txt"].decode())
        results.sampler = sampler_results(levels, info_rows)
        results.info["num_levels"] = int(levels.shape[0])

    # The saved samples, weighted as the sampler part says or as weights.txt
    if os.path.isfile(path("sample.txt")) and info_rows is not None:
        if results.sampler is not None:
            weights, log_x = results.sampler["weight"], \
                results.sampler["log_x"]
        elif os.path.isfile(path("weights.txt")):
            weights, log_x = np.atleast_1d(np.loadtxt(path("weights.txt"))), \
                None
        else:
            weights = None
        if weights is not None:
            results.particles, results.peaks, maxima = read_particles(
                path("sample.txt"), x, info_rows, weights, log_x,
                fraction_range)
            results.info["num_saves"] = int(len(results.particles))
            results.info["max_num_narrow_peaks"] = maxima[0]
            results.info["max_num_wide_peaks"] = maxima[1]

    # The posterior samples
    if os.path.isfile(path("posterior_sample.txt")):
        results.posterior, results.curves, max_narrow = read_posterior(
            path("posterior_sample.txt"), x, results.y)
        results.info["num_posterior_samples"] = int(len(results.posterior))
        if max_narrow is not None:
            results.info.setdefault("max_num_narrow_peaks", max_narrow)
    else:
        results.curves = {"x": x, "y": results.y}

    if results.particles is not None and "num_peaks1" in results.particles:
        results.diagnosis = diagnose(results.particles, results.posterior,
                                     results.info["max_num_narrow_peaks"],
                                     results.info["max_num_wide_peaks"])
        if fraction_range is not None:
            results.diagnosis["fraction_in_range"]["range"] = \
                results.info["fraction_range"]
    return results


def summary(results):
    """
    The numbers of the report, for a JSON file.
    """
    out = {"info": results.info}
    if results.sampler is not None:
        s = results.sampler
        out["sampler"] = {"log_z": s["log_z"],
                          "information": s["information"],
                          "effective_sample_size": s["effective_sample_size"],
                          "num_levels": int(s["levels"].shape[0]),
                          "num_saves": int(s["sample_info"].shape[0])}
    if results.posterior is not None:
        out["posterior"] = {"num_samples": int(len(results.posterior)),
                            "quantities": {
                                name: describe(results.posterior[name])
                                for name in results.posterior.columns}}
    if results.diagnosis is not None:
        out["diagnosis"] = results.diagnosis
    return out


# The quantities of the posterior samples that showresults.py reports
REPORTED = [("(amorph)/(amorph + crystal)", "fraction"),
            ("Center of mass", "wide_center_of_mass"),
            ("Half-width", "wide_halfwidth"),
            ("Skewness", "wide_skewness"),
            ("Nongaussianity", "wide_nongaussianity")]


def diagnosis_lines(d):
    """
    The diagnosis as text, as scripts/diagnose_posterior.py prints it.
    """
    lines = []
    f = d["fraction"]
    lines.append("Saved particles: {0}, effective sample size {1:.0f}".format(
        d["saves"], d["effective_sample_size"]))
    lines.append("Amorphous fraction: median {0:.3f}, 50% interval [{1:.3f}, "
                 "{2:.3f}], 90% interval [{3:.3f}, {4:.3f}]".format(
                     f["q50"], f["q25"], f["q75"], f["q05"], f["q95"]))
    if "fraction_in_range" in d:
        r = d["fraction_in_range"]
        lines.append("Amorphous fraction from {0:g} to {1:g}: median {2:.3f}, "
                     "50% interval [{3:.3f}, {4:.3f}], 90% interval "
                     "[{5:.3f}, {6:.3f}]".format(
                         r["range"][0], r["range"][1], r["q50"], r["q25"],
                         r["q75"], r["q05"], r["q95"]))
    lines.append("Posterior weight with fraction 0: {0:.2%}, below 0.2: "
                 "{1:.2%}, below 0.45: {2:.2%}".format(
                     d["weight_fraction_0"], d["weight_fraction_below_0.2"],
                     d["weight_fraction_below_0.45"]))
    lines.append("Posterior weight with at least {0:.0f} of {1} narrow peaks: "
                 "{2:.2%}".format(AT_CAP * d["max_num_narrow_peaks"],
                                  d["max_num_narrow_peaks"],
                                  d["weight_narrow_at_cap"]))
    lines.append("Per band of the fraction: posterior weight, and weighted "
                 "medians of logL, number of narrow peaks and their nu; the "
                 "highest logL; the mean RMS of model - data of the posterior "
                 "samples")
    lines.append("{0:12s} {1:>9s} {2:>8s} {3:>9s} {4:>9s} {5:>7s} {6:>9s} "
                 "{7:>7s}".format("fraction", "particles", "weight", "logL",
                                  "max logL", "narrow", "nu_narrow", "RMS"))

    def fmt(entry, key, form):
        return form.format(entry[key]) if key in entry else "-"

    for e in d["bands"]:
        lines.append("{0:12s} {1:9d} {2:8.2%} {3:>9s} {4:>9s} {5:>7s} {6:>9s} "
                     "{7:>7s}".format(e["band"], e["particles"], e["weight"],
                                      fmt(e, "log_likelihood", "{0:.1f}"),
                                      fmt(e, "max_log_likelihood", "{0:.1f}"),
                                      fmt(e, "narrow_peaks", "{0:.0f}"),
                                      fmt(e, "nu_narrow", "{0:.3g}"),
                                      fmt(e, "rms", "{0:.3f}")))
    for key in ("nu_narrow", "nu", "sigma0", "sigma1", "num_narrow_peaks"):
        s = d[key]
        if s is not None:
            lines.append("{0}: {1:.3g} [{2:.3g}, {3:.3g}]".format(
                key, s["median"], s["q16"], s["q84"]))
    return lines


def report_lines(results):
    """
    Everything that showresults.py and scripts/diagnose_posterior.py
    report about the run, as lines of text.
    """
    info = results.info
    lines = ["Data: {0}, {1} points from {2:g} to {3:g}".format(
        info["data_file"], info["num_points"], info["x_min"], info["x_max"])]
    if results.sampler is not None:
        s = results.sampler
        lines.append("log(Z) = " + str(s["log_z"]))
        lines.append("Information = " + str(s["information"]) + " nats.")
        lines.append("Effective sample size = "
                     + str(s["effective_sample_size"]))
    if results.posterior is not None:
        lines.append("Posterior samples: {0}".format(len(results.posterior)))
        for label, column in REPORTED:
            if column not in results.posterior:
                continue
            v = results.posterior[column].to_numpy()
            v = v[~np.isnan(v)]
            if v.size == 0:
                lines.append("{0}: undefined".format(label))
            else:
                lines.append("{0} = {1} +- {2}".format(label, v.mean(),
                                                       v.std()))
    if results.diagnosis is not None:
        lines.append("")
        lines += diagnosis_lines(results.diagnosis)
    return lines


# ------------------------------------------------------------------ figures
# Each function draws one figure of the results on a matplotlib Figure.

def draw_levels(fig, r):
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(r.sampler["sample_info"][:, 0], "k")
    ax.set_xlabel("Iteration")
    ax.set_ylabel("Level")


def draw_compression(fig, r):
    levels = r.sampler["levels"]
    ax = fig.add_subplot(2, 1, 1)
    ax.plot(np.diff(levels[:, 0]), "k")
    ax.set_ylabel("Compression")
    ax.set_xlabel("Level")
    xlim = ax.get_xlim()
    ax.axhline(-1., color="g")
    ax.axhline(-np.log(10.), color="g", linestyle="--")
    ax.set_ylim(top=0.05)

    ax = fig.add_subplot(2, 1, 2)
    good = np.nonzero(levels[:, 4] > 0)[0]
    ax.plot(levels[good, 3] / levels[good, 4], "ko-")
    ax.set_xlim(xlim)
    ax.set_ylim([0., 1.])
    ax.set_xlabel("Level")
    ax.set_ylabel("MH Acceptance")


def draw_likelihood(fig, r):
    s = r.sampler
    levels = s["levels"]
    log_l = s["sample_info"][:, 1]
    ax = fig.add_subplot(2, 1, 1)
    ax.plot(s["log_x"], log_l, "k.", label="Samples")
    ax.plot(levels[1:, 0], levels[1:, 1], "g.", label="Levels")
    ax.legend(numpoints=1, loc="lower left")
    ax.set_ylabel("log(L)")
    ax.set_title("log(Z) = " + str(s["log_z"]))
    # Use all plotted logl values to set ylim
    combined = np.sort(np.hstack([log_l, levels[1:, 1]]))
    lower = combined[int(0.1 * combined.size)]
    upper = combined[-1]
    diff = upper - lower
    if diff > 0.0:
        ax.set_ylim([lower - 0.05 * diff, upper + 0.05 * diff])
    xlim = ax.get_xlim()

    ax = fig.add_subplot(2, 1, 2)
    ax.plot(s["log_x"], s["weight"], "k.")
    ax.set_ylabel("Posterior Weights")
    ax.set_xlabel("log(X)")
    ax.set_xlim(xlim)


def draw_model(fig, r):
    # 50 posterior samples and the posterior mean of each part: the model
    # dark, the amorphous part blue, the crystalline part orange and the
    # background grey, as in the GUI
    c = r.curves
    ax = fig.add_subplot(1, 1, 1)
    styles = [("model_curve", "#1B2430", "-"), ("wide", "#1D4ED8", "--"),
              ("narrow", "#EA580C", "--"), ("bg", "#6B7280", "--")]
    for name, color, _ in styles:
        if name + "_examples" in c:
            for curve in c[name + "_examples"]:
                ax.plot(r.x, curve, color=color, linewidth=1, alpha=0.1)
    for name, color, style in styles:
        if name + "_mean" in c:
            ax.plot(r.x, c[name + "_mean"], style, color=color, linewidth=2.5,
                    alpha=1)
    ax.plot(r.x, r.y, "o", color="#4B5563", markersize=2.5, alpha=0.5)
    ax.set_ylim(0)
    ax.set_xlabel("$2\\theta$ (degrees)", fontsize=14)
    ax.set_ylabel("Intensity", fontsize=14)


def draw_residuals(fig, r):
    ax = fig.add_subplot(1, 1, 1)
    ax.plot(r.x, r.curves["residuals"], "-")
    ax.set_xlabel("$2\\theta$ (degrees)")
    ax.set_ylabel("Standardised residuals (of posterior mean model curve)")


def _histogram(fig, values, xlabel, **kwargs):
    ax = fig.add_subplot(1, 1, 1)
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if v.size == 0:
        ax.text(0.5, 0.5, "undefined: no posterior sample has it",
                ha="center", va="center", transform=ax.transAxes)
    else:
        ax.hist(v, kwargs.pop("bins", 100), color=[0.3, 0.3, 0.3], **kwargs)
    ax.set_xlabel(xlabel)
    return ax


def draw_narrow_peaks(fig, r):
    values = r.posterior["num_narrow_peaks"].to_numpy()
    maximum = r.info.get("max_num_narrow_peaks")
    if maximum is None:
        maximum = int(values.max())
    # One bin per count from 0 to the maximum
    ax = _histogram(fig, values, "Number of narrow components",
                    bins=np.arange(0, maximum + 2) - 0.5, rwidth=0.8)
    ax.set_ylabel("Number of posterior samples")


def draw_fraction(fig, r):
    ax = _histogram(fig, r.posterior["fraction"],
                    "(amorph)/(amorph + crystal)")
    ax.set_xlim([0, 1])


def draw_center(fig, r):
    _histogram(fig, r.posterior["wide_center_of_mass"],
               "Center of mass of wide component")


def draw_halfwidth(fig, r):
    _histogram(fig, r.posterior["wide_halfwidth"],
               "Half-width of wide component")


def draw_skewness(fig, r):
    _histogram(fig, r.posterior["wide_skewness"],
               "Skewness of wide component")


def draw_nongaussianity(fig, r):
    ax = _histogram(fig, r.posterior["wide_nongaussianity"],
                    "Nongaussianity of wide component")
    ax.set_xlim(0.0)


def _has_sampler(r):
    return r.sampler is not None


def _has_model(r):
    return r.curves is not None and "model_curve_examples" in r.curves


def _has_residuals(r):
    return r.curves is not None and "residuals" in r.curves


def _has_column(name):
    return lambda r: r.posterior is not None and name in r.posterior


# The figures, in the order showresults.py shows them: (name, title,
# whether the results have what it needs, the function that draws it)
FIGURES = [
    ("levels", "Level of each saved sample", _has_sampler, draw_levels),
    ("compression", "Compression and acceptance of the levels",
     _has_sampler, draw_compression),
    ("likelihood", "Likelihood and posterior weight against log(X)",
     _has_sampler, draw_likelihood),
    ("model", "The model, its parts and the data", _has_model, draw_model),
    ("residuals", "Standardised residuals", _has_residuals, draw_residuals),
    ("narrow_peaks", "Number of narrow peaks",
     _has_column("num_narrow_peaks"), draw_narrow_peaks),
    ("fraction", "Amorphous fraction", _has_column("fraction"),
     draw_fraction),
    ("center", "Center of mass of the wide component",
     _has_column("wide_center_of_mass"), draw_center),
    ("halfwidth", "Half-width of the wide component",
     _has_column("wide_halfwidth"), draw_halfwidth),
    ("skewness", "Skewness of the wide component",
     _has_column("wide_skewness"), draw_skewness),
    ("nongaussianity", "Nongaussianity of the wide component",
     _has_column("wide_nongaussianity"), draw_nongaussianity),
]


def available_figures(results):
    """
    The entries of FIGURES that the results have what they need for.
    """
    return [(name, title, draw) for name, title, has, draw in FIGURES
            if has(results)]
