"""
The estimate of a run while the sampler works, for «Прогоны»: the
amorphous fraction with its intervals, computed from every save so far
with its posterior weight as the post-processing computes it, and how it
moved; the posterior mean of the curves with the 90% band of the model;
the best sample so far and the last saved one; and where they and the
posterior weight are among the levels.

The last saved sample alone says little: once the levels are built, the
sampler sends its particles down to low levels on purpose, and most saves
fit worse than the posterior. Nothing here needs Qt; update() reads the new
saves and runs in a worker thread, and replay() makes the estimate of a
run that has ended, opened from its folder.
"""

import os

import numpy as np

import amorph_results
import amorph_stats

from amorph_gui import runfiles

# The quantiles of the fraction
QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]

# The curves of a sample, in the order they are kept
CURVES = ["bg", "wide", "narrow", "model_curve"]

# The curves of at most this many saves are kept, those of the highest
# log likelihood; the others carry next to no posterior weight
MAX_KEPT = 3000

# The curves of saves whose log likelihood is below the 0.1% quantile of
# the posterior by more than this are dropped
KEEP_MARGIN = 10.0

# The estimate has settled when, since the levels were built, its median
# has moved by less than SETTLE_SHIFT over the last SETTLE_FRACTION of the
# saves (at least SETTLE_SAVES of them), with an effective sample size of
# at least SETTLE_ESS
SETTLE_SHIFT = 0.005
SETTLE_FRACTION = 0.2
SETTLE_SAVES = 1000
SETTLE_ESS = 100

# The number of draws for the band of the model
BAND_DRAWS = 400

# The trace keeps at most this many updates: beyond, every other one of
# all but the last is dropped
MAX_TRACE = 2000

# The steps in which replay() reads the saves of a run that has ended
REPLAY_STEPS = 40

# The buffer of the reads of sample.txt, in bytes
READ_BUFFER = 1 << 22

# What the sampler prints when it has built its last level, and at a save
DONE_LEVELS = "Done creating levels"
SAVING = "# Saving particle"


class LiveEstimate(object):
    """
    The estimate of the run in folder, which analyses the points x.
    update() reads what the sampler has added and returns the estimate.
    """

    def __init__(self, folder, x):
        self.folder = folder
        self.x = np.asarray(x, dtype=float)
        self.offset = 0
        self.columns = None
        self.num_values = None
        self.fractions = []
        self.log_likelihoods = []
        self.kept = {}
        self.best = None
        self.last = None
        self.trace = []
        self.levels_done_at = None
        self.threshold = -np.inf
        # sample.txt, kept open by replay() between its steps; a sampler at
        # work gets it opened at each update, which leaves the files of the
        # run free between them
        self.handle = None

    # ---------------------------------------------------------- reading

    def _read_header(self, path):
        names = amorph_results.column_names(path)
        if "model_curve[0]" not in names:
            return False
        self.num_values = len(names)
        self.columns = {}
        for name in CURVES:
            first = names.index(name + "[0]")
            n = sum(1 for c in names if c.startswith(name + "["))
            self.columns[name] = slice(first, first + n)
        return True

    def _read_saves(self, wanted, info):
        """
        Read the saves of sample.txt from self.offset up to save number
        wanted (the saves sample_info.txt has a row for).
        """
        path = os.path.join(self.folder, "sample.txt")
        if not os.path.isfile(path):
            return
        if self.columns is None and not self._read_header(path):
            return
        # Large reads: on a network or cloud drive small ones are slow
        held = self.handle is not None
        f = self.handle if held else open(path, "rb", buffering=READ_BUFFER)
        try:
            f.seek(self.offset)
            while len(self.fractions) < wanted:
                start = f.tell()
                line = f.readline()
                if not line.endswith(b"\n"):
                    f.seek(start)
                    break
                if line.startswith(b"#"):
                    continue
                values = line.split()
                if len(values) != self.num_values:
                    f.seek(start)
                    break
                values = np.array(values, dtype=float)
                curves = np.array([values[self.columns[name]]
                                   for name in CURVES])
                self._add(curves, info)
            self.offset = f.tell()
        finally:
            if not held:
                f.close()

    def _add(self, curves, info):
        k = len(self.fractions)
        wide, narrow = curves[1], curves[2]
        fraction = amorph_stats.amorphous_fraction(wide[None, :],
                                                   narrow[None, :],
                                                   self.x)[0]
        log_l = float(info[k, 1])
        self.fractions.append(fraction)
        self.log_likelihoods.append(log_l)
        stored = curves.astype(np.float32)
        if log_l >= self.threshold:
            self.kept[k] = stored
        if self.best is None or log_l > self.best[1]:
            self.best = (k, log_l, stored)
        self.last = (k, stored)

    def _read_levels_done(self):
        if self.levels_done_at is not None:
            return
        try:
            with open(os.path.join(self.folder, runfiles.LOG_FILE),
                      encoding="utf-8", errors="replace") as f:
                saves = 0
                for line in f:
                    if line.startswith(SAVING):
                        saves += 1
                    elif DONE_LEVELS in line:
                        self.levels_done_at = saves
                        return
        except OSError:
            pass

    # -------------------------------------------------------- the estimate

    def update(self, limit=None, info=None, levels=None, curves=True):
        """
        Read the new saves, up to save number limit if given, and return
        the estimate (see estimate()), or None while there is no save.
        info and levels are the rows of sample_info.txt and levels.txt, if
        already read; without curves, the mean curves and the band are
        left out.
        """
        if info is None:
            try:
                with open(os.path.join(self.folder, "sample_info.txt")) as f:
                    info = amorph_results.parse_table(f.read())
            except OSError:
                return None
        if info.size == 0 or info.shape[1] < 2:
            return None
        if limit is not None:
            info = info[:limit]
        self._read_saves(info.shape[0], info)
        self._read_levels_done()
        if not self.fractions:
            return None
        if levels is None:
            text = runfiles.levels_text(self.folder)
            levels = None if text is None \
                else amorph_results.parse_table(text.decode())
        return self.estimate(info[:len(self.fractions)], levels, curves)

    def estimate(self, info, levels, curves=True):
        """
        The estimate from the rows of sample_info.txt of the saves read so
        far and the levels (None if levels.txt is not complete): a dict of

        saves           the number of saves read
        levels_done_at  the save at which the last level was built, or None
        last, best      the last saved sample and the one of the highest
                        log likelihood: its curves (CURVES), save number
                        (from 1), level, log likelihood and fraction
        num_levels      the number of levels (0 if unknown)
        window          the number of last saves that shift looks at

        and, once the levels give weights: quantiles (QUANTILES of the
        fraction), effective_sample_size, log_z, trace (one row per update:
        saves and the quantiles), shift (how far the median moved over the
        last window saves, None while there are too few) and settled; mean (the
        posterior mean of each curve) and band (the 5% and 95% quantiles
        of the model curve), unless curves is false; posterior_levels (the
        5% and 95% quantiles of the level of the saves, by weight).
        """
        m = len(self.fractions)
        fractions = np.array(self.fractions)

        def sample(k, curves):
            return {"curves": {name: curves[i].astype(float)
                               for i, name in enumerate(CURVES)},
                    "save": k + 1, "level": int(info[k, 0]),
                    "log_likelihood": float(info[k, 1]),
                    "fraction": float(fractions[k])}

        window = int(max(SETTLE_SAVES, SETTLE_FRACTION * m))
        out = {"saves": m, "levels_done_at": self.levels_done_at,
               "last": sample(*self.last),
               "best": sample(self.best[0], self.best[2]),
               "num_levels": 0 if levels is None else int(levels.shape[0]),
               "quantiles": None, "settled": False, "shift": None,
               "window": window}
        if levels is None or levels.shape[0] < 2 or m < 2:
            return out

        s = amorph_results.sampler_results(levels, info)
        w = s["weight"]
        # As amorph_results.diagnose: the saves with a defined fraction
        ok = np.isfinite(fractions)
        if not ok.any() or w[ok].sum() <= 0.0:
            return out
        q = amorph_results.weighted_quantiles(fractions[ok], w[ok],
                                              QUANTILES)
        if not self.trace or self.trace[-1][0] < m:
            self.trace.append([m] + q)
            if len(self.trace) > MAX_TRACE:
                self.trace = self.trace[:-1:2] + self.trace[-1:]
        trace = np.array(self.trace)
        out.update(quantiles=q, effective_sample_size=float(
            s["effective_sample_size"]), log_z=float(s["log_z"]),
            trace=trace)

        # How far the median moved over the last saves
        recent = trace[trace[:, 0] >= m - window]
        if self.levels_done_at is not None \
                and m - self.levels_done_at >= window \
                and trace[0, 0] <= m - 0.9 * window and len(recent) > 1:
            out["shift"] = float(np.ptp(recent[:, 3]))
            out["settled"] = (out["shift"] < SETTLE_SHIFT
                              and s["effective_sample_size"] >= SETTLE_ESS)

        # Keep the curves of the saves that can carry weight
        log_l = info[:, 1]
        floor = amorph_results.weighted_quantiles(log_l, w, [0.001])[0]
        self.threshold = floor - KEEP_MARGIN
        for k in [k for k in self.kept if log_l[k] < self.threshold]:
            del self.kept[k]
        if len(self.kept) > MAX_KEPT:
            order = sorted(self.kept, key=lambda k: log_l[k])
            for k in order[:len(self.kept) - MAX_KEPT]:
                del self.kept[k]

        kept = np.array(sorted(self.kept), dtype=int)
        weights = w[kept]
        if curves and weights.sum() > 0.0:
            weights = weights / weights.sum()
            stack = np.array([self.kept[k] for k in kept], dtype=float)
            out["mean"] = {name: np.tensordot(weights, stack[:, i, :], 1)
                           for i, name in enumerate(CURVES)}
            rng = np.random.default_rng(0)
            draws = rng.choice(len(kept), size=BAND_DRAWS, p=weights)
            out["band"] = tuple(np.quantile(stack[draws, 3, :],
                                            [0.05, 0.95], axis=0))
        out["posterior_levels"] = amorph_results.weighted_quantiles(
            info[:, 0], w, [0.05, 0.95])
        return out


def replay(folder, x, steps=REPLAY_STEPS):
    """
    The estimate of a run that has ended, with its trace: the saves are
    read in steps, as if the sampler were writing them, so that the trace
    shows how the fraction moved. The weights of each step come from the
    levels the run ended with.
    """
    estimate = LiveEstimate(folder, x)
    with open(os.path.join(folder, "sample_info.txt")) as f:
        info = amorph_results.parse_table(f.read())
    text = runfiles.levels_text(folder)
    levels = None if text is None \
        else amorph_results.parse_table(text.decode())
    result = None
    path = os.path.join(folder, "sample.txt")
    if os.path.isfile(path):
        estimate.handle = open(path, "rb", buffering=READ_BUFFER)
    try:
        for k in range(1, steps + 1):
            result = estimate.update(
                limit=int(np.ceil(len(info) * k / steps)), info=info,
                levels=levels, curves=(k == steps))
    finally:
        if estimate.handle is not None:
            estimate.handle.close()
            estimate.handle = None
    return result
