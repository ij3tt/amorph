"""
Several runs of one sample together: the seeds of the sampler on the same
data with the same settings. Each run is given by its results
(amorph_results.Results, from a run archive or a run folder).

    pooled = amorph_seeds.pool([results1, results2])

gives the posterior of all of them, each seed counting equally and the
saves of a seed keeping their posterior weights: the quantiles and the
mean of the amorphous fraction, the spread of the medians of the seeds
(the run-to-run error of the sampler), the mean curves and the 90% band of
the model, and the curves that the figures of amorph_tex draw. Nothing here
needs Qt.
"""

import numpy as np

import amorph_results

# The quantiles of the fraction that the report gives
QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]

# The faint sample curves of the figure in the style of xrd_fit.tex
NUM_EXAMPLES = 50

# Bins of the distributions of the fraction
NUM_BINS = 40


def seed_of(results):
    """
    The seed of a run, from its config.yaml, or None.
    """
    config = results.info.get("config")
    return config.get("seed") if isinstance(config, dict) else None


def fraction_samples(results):
    """
    The amorphous fraction of the saved samples of a run with a defined
    fraction, and their posterior weights, normalised.
    """
    if results.particles is None or "fraction" not in results.particles:
        raise ValueError("the results hold no saved samples")
    fraction = results.particles["fraction"].to_numpy(dtype=float)
    weight = results.particles["weight"].to_numpy(dtype=float)
    # As amorph_results.diagnose: the saves with a defined fraction
    ok = np.isfinite(fraction)
    if not ok.any() or weight[ok].sum() <= 0.0:
        raise ValueError("no saved sample has a defined fraction")
    return fraction[ok], weight[ok] / weight[ok].sum()


def posterior_mean_fraction(results):
    """
    The posterior mean of the fraction, as export_pgf.py reports it: the
    mean over the posterior samples with a defined fraction, or over the
    weighted saved samples if there are no posterior samples.
    """
    if results.posterior is not None and "fraction" in results.posterior:
        values = results.posterior["fraction"].to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if values.size:
            return float(values.mean())
    fraction, weight = fraction_samples(results)
    return float(np.sum(fraction * weight))


def mixture_quantile(quantile_sets, probabilities, p):
    """
    The p quantile, at each point, of an equal mixture of distributions
    known by their quantiles: quantile_sets[k][j] is the probabilities[j]
    quantile of distribution k at each point (arrays of the same shape).
    The distribution function of each is taken as linear between its
    quantiles and continued with the slope of the outer ones; the mixture
    quantile is found by bisection. For one distribution it is its own
    quantile at the given probabilities.
    """
    probabilities = np.asarray(probabilities, dtype=float)
    sets = [np.asarray(q, dtype=float) for q in quantile_sets]
    if len(sets) == 1:
        j = np.searchsorted(probabilities, p)
        if j < len(probabilities) and probabilities[j] == p:
            return sets[0][j].copy()

    lower = np.min([q[0] for q in sets], axis=0)
    upper = np.max([q[-1] for q in sets], axis=0)
    span = np.maximum(upper - lower, 1E-12)
    a, b = lower - span, upper + span
    for _ in range(50):
        middle = 0.5 * (a + b)
        value = np.mean([_cdf(q, probabilities, middle) for q in sets],
                        axis=0)
        below = value < p
        a = np.where(below, middle, a)
        b = np.where(below, b, middle)
    return 0.5 * (a + b)


def _cdf(q, p, v):
    """
    The distribution function at v (one value per point) of the
    distribution with the quantiles q (one row per probability in p) at
    each point: linear between the quantiles, continued with the slopes of
    the outer ones, within 0 and 1.
    """
    slope = (p[1:] - p[:-1])[:, None] / np.maximum(q[1:] - q[:-1], 1E-300)
    out = p[0] - slope[0] * (q[0] - v)
    for j in range(len(p) - 1):
        out = np.where(v >= q[j], p[j] + slope[j] * (v - q[j]), out)
    return np.clip(out, 0.0, 1.0)


def same_data(runs):
    """
    Whether the runs analysed the same points: the same x and y.
    """
    x, y = runs[0].x, runs[0].y
    return all(r.x is not None and r.x.size == x.size and np.allclose(r.x, x)
               and np.allclose(r.y, y) for r in runs[1:])


def pool(runs, num_examples=NUM_EXAMPLES, num_bins=NUM_BINS):
    """
    The runs (seeds) together, each counting equally. Raises ValueError if
    there are none, or they analysed different data. Returns a dict:

    seeds           the seed of each run (None where unknown)
    quantiles       QUANTILES of the fraction, pooled
    seed_quantiles  QUANTILES of the fraction of each run
    spread          the largest minus the smallest median of the runs
                    (None for one run)
    mean            the posterior mean of the fraction, the mean over the
                    runs of posterior_mean_fraction
    ess             the sum of the effective sample sizes
    x, y            the data
    curves          the mean curves bg, wide, narrow and model_curve, the
                    means of those of the runs
    band            the 5% and 95% quantiles of the model curve at each
                    point, of the mixture of the runs
    halos           the mean background plus amorphous part of each run
    examples        num_examples posterior samples of the model, wide and
                    narrow curves, taken from the runs in turn
    histogram       the edges of the bins of the fraction, the density of
                    each run and the pooled density
    """
    if not runs:
        raise ValueError("no runs to pool")
    if not same_data(runs):
        raise ValueError("the runs analysed different data")
    samples = [fraction_samples(r) for r in runs]
    fraction = np.concatenate([f for f, _ in samples])
    weight = np.concatenate([w / len(runs) for _, w in samples])
    quantiles = amorph_results.weighted_quantiles(fraction, weight,
                                                  QUANTILES)
    seed_quantiles = [amorph_results.weighted_quantiles(f, w, QUANTILES)
                      for f, w in samples]
    medians = [q[2] for q in seed_quantiles]

    ess = 0.0
    for r in runs:
        if r.sampler is not None and "effective_sample_size" in r.sampler:
            ess += float(r.sampler["effective_sample_size"])
        elif r.diagnosis is not None:
            ess += float(r.diagnosis["effective_sample_size"])

    names = ["bg", "wide", "narrow", "model_curve"]
    curves = {}
    for name in names:
        curves[name] = np.mean([np.asarray(r.curves[name + "_mean"],
                                           dtype=float) for r in runs],
                               axis=0)
    probabilities = amorph_results.CURVE_QUANTILES
    sets = [np.asarray(r.curves["model_curve_quantiles"], dtype=float)
            for r in runs]
    band = (mixture_quantile(sets, probabilities, 0.05),
            mixture_quantile(sets, probabilities, 0.95))
    halos = [np.asarray(r.curves["bg_mean"], dtype=float)
             + np.asarray(r.curves["wide_mean"], dtype=float) for r in runs]

    examples = {name: [] for name in ("model_curve", "wide", "narrow")}
    counts = [len(r.curves.get("model_curve_examples", []))
              for r in runs]
    k = 0
    while len(examples["model_curve"]) < num_examples and k < max(counts):
        for r, count in zip(runs, counts):
            if k < count and len(examples["model_curve"]) < num_examples:
                for name in examples:
                    examples[name].append(np.asarray(
                        r.curves[name + "_examples"][k], dtype=float))
        k += 1
    n = runs[0].x.size
    examples = {name: (np.array(v) if v else np.zeros((0, n)))
                for name, v in examples.items()}

    lo = max(0.0, np.floor(20.0 * min(q[0] for q in seed_quantiles + [
        quantiles]) - 1.0) / 20.0)
    hi = min(1.0, np.ceil(20.0 * max(q[4] for q in seed_quantiles + [
        quantiles]) + 1.0) / 20.0)
    edges = np.linspace(lo, hi, num_bins + 1)
    densities = [np.histogram(f, bins=edges, weights=w, density=True)[0]
                 for f, w in samples]
    pooled_density = np.histogram(fraction, bins=edges, weights=weight,
                                  density=True)[0]

    return {"seeds": [seed_of(r) for r in runs],
            "quantiles": quantiles,
            "seed_quantiles": seed_quantiles,
            "spread": (max(medians) - min(medians)) if len(runs) > 1
            else None,
            "mean": float(np.mean([posterior_mean_fraction(r)
                                   for r in runs])),
            "ess": ess,
            "x": np.asarray(runs[0].x, dtype=float),
            "y": np.asarray(runs[0].y, dtype=float),
            "curves": curves,
            "band": band,
            "halos": halos,
            "examples": examples,
            "histogram": {"edges": edges, "densities": densities,
                          "pooled": pooled_density}}
