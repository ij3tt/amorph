"""
Tests of the estimate of a run while the sampler works
(src/amorph_gui/live.py), on the fake run of test_results.py written one
part at a time, as the sampler writes it. It does not need Qt. Run with
pytest from the repository root:

    python -m pytest tests
"""

import os
import shutil
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import amorph_results
import amorph_stats
from amorph_gui import live, runfiles
from test_results import make_full_run

QUANTILES = ["q05", "q25", "q50", "q75", "q95"]


@pytest.fixture(scope="module")
def finished(tmp_path_factory):
    """
    The fake run, finished: (folder, column names, rows of sample.txt).
    """
    folder = str(tmp_path_factory.mktemp("finished"))
    names, rows = make_full_run(folder)
    return folder, names, rows


def lines(path):
    with open(path) as f:
        text = f.readlines()
    return ([l for l in text if l.startswith("#")],
            [l for l in text if not l.startswith("#")])


class Sampler(object):
    """
    Writes the files of the finished run into folder a few saves at a
    time, as the sampler does: a save in sample.txt, then in
    sample_info.txt, and levels.txt and the log of the GUI.
    """

    def __init__(self, source, folder, done_at=None):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)
        self.sample_head, self.samples = lines(
            os.path.join(source, "sample.txt"))
        self.info_head, self.infos = lines(
            os.path.join(source, "sample_info.txt"))
        shutil.copyfile(os.path.join(source, "levels.txt"),
                        os.path.join(folder, "levels.txt"))
        shutil.copyfile(os.path.join(source, "demo_data.txt"),
                        os.path.join(folder, "demo_data.txt"))
        for name, head in (("sample.txt", self.sample_head),
                           ("sample_info.txt", self.info_head)):
            with open(os.path.join(folder, name), "w") as f:
                f.writelines(head)
        open(os.path.join(folder, runfiles.LOG_FILE), "w").close()
        self.saves = 0
        self.done_at = done_at

    def save(self, count, half=False):
        for _ in range(count):
            k = self.saves
            with open(os.path.join(self.folder, "sample.txt"), "a") as f:
                f.write(self.samples[k])
            with open(os.path.join(self.folder, "sample_info.txt"), "a") as f:
                f.write(self.infos[k])
            with open(os.path.join(self.folder, runfiles.LOG_FILE), "a") as f:
                f.write("# Saving particle to disk. N = {0}.\n".format(k + 1))
                if self.done_at == k + 1:
                    f.write("# Done creating levels.\n")
            self.saves += 1
        if half:
            # The next save, cut off, as while the sampler writes it
            with open(os.path.join(self.folder, "sample.txt"), "a") as f:
                f.write(self.samples[self.saves][:50])


def data_x(folder):
    return amorph_stats.load_data(os.path.join(folder, "demo_data.txt"))[0]


def test_the_estimate_of_all_saves_is_the_post_processing(finished,
                                                          tmp_path):
    source, names, rows = finished
    sampler = Sampler(source, str(tmp_path / "run"), done_at=10)
    estimate = live.LiveEstimate(sampler.folder, data_x(source))
    assert estimate.update() is None

    # Part of the saves, and half of the next one
    sampler.save(25, half=True)
    e = estimate.update()
    assert e["saves"] == 25
    assert e["last"]["save"] == 25
    assert e["levels_done_at"] == 10

    # Then the rest
    with open(os.path.join(sampler.folder, "sample.txt")) as f:
        text = f.read()
    with open(os.path.join(sampler.folder, "sample.txt"), "w") as f:
        f.write(text[:text.rindex("\n") + 1])
    sampler.save(len(rows) - 25)
    e = estimate.update()
    m = len(rows)
    assert e["saves"] == m
    assert len(e["trace"]) == 2 and e["trace"][-1][0] == m

    results = amorph_results.from_run(source)
    d = results.diagnosis["fraction"]
    assert e["quantiles"] == pytest.approx([d[q] for q in QUANTILES],
                                           abs=1E-12)
    assert e["effective_sample_size"] == pytest.approx(
        results.sampler["effective_sample_size"])
    assert e["log_z"] == pytest.approx(results.sampler["log_z"])

    # The mean of the curves with the weights of the saves: the curves of
    # saves far below the posterior are dropped, with next to no weight
    w = results.sampler["weight"]
    for name in ("model_curve", "wide", "bg"):
        first = names.index(name + "[0]")
        curves = rows[:, first:first + results.x.size]
        expected = np.average(curves, axis=0, weights=w)
        assert np.max(np.abs(e["mean"][name] - expected)) <= \
            5E-3 * np.max(np.abs(expected))
    lo, hi = e["band"]
    assert np.all(lo <= hi)

    # The last and the best saves
    info = amorph_results.parse_table(open(os.path.join(
        source, "sample_info.txt")).read())
    assert e["last"]["save"] == m
    assert e["best"]["save"] == int(np.argmax(info[:, 1])) + 1
    first = names.index("model_curve[0]")
    np.testing.assert_allclose(e["last"]["curves"]["model_curve"],
                               rows[-1, first:first + results.x.size],
                               rtol=1E-6)
    assert e["num_levels"] == 4
    lo, hi = e["posterior_levels"]
    assert 0 <= lo <= hi <= 3


def test_the_estimate_settles(finished, tmp_path, monkeypatch):
    source, names, rows = finished
    monkeypatch.setattr(live, "SETTLE_SAVES", 10)
    monkeypatch.setattr(live, "SETTLE_ESS", 1)
    sampler = Sampler(source, str(tmp_path / "run"), done_at=1)
    estimate = live.LiveEstimate(sampler.folder, data_x(source))
    sampler.save(5)
    e = estimate.update()
    assert e["shift"] is None and not e["settled"]
    while sampler.saves < len(rows):
        sampler.save(min(5, len(rows) - sampler.saves))
        e = estimate.update()
    assert e["window"] == max(10, int(0.2 * len(rows)))
    recent = e["trace"][e["trace"][:, 0] >= len(rows) - e["window"]]
    assert e["shift"] == pytest.approx(np.ptp(recent[:, 3]))
    assert e["settled"] == (e["shift"] < live.SETTLE_SHIFT)


def test_the_trace_is_thinned(finished, tmp_path, monkeypatch):
    # An update at each save, as of a fast sampler
    source, names, rows = finished
    monkeypatch.setattr(live, "MAX_TRACE", 4)
    sampler = Sampler(source, str(tmp_path / "run"))
    estimate = live.LiveEstimate(sampler.folder, data_x(source))
    first = None
    while sampler.saves < len(rows):
        sampler.save(1)
        e = estimate.update()
        assert len(estimate.trace) <= 4
        if first is None and "trace" in e:
            first = e["trace"][0, 0]
    # The first update and the last are kept, in order
    saves = e["trace"][:, 0]
    assert saves[0] == first and saves[-1] == len(rows)
    assert np.all(np.diff(saves) > 0)


def test_no_estimate_without_levels(finished, tmp_path):
    source, names, rows = finished
    sampler = Sampler(source, str(tmp_path / "run"))
    os.remove(os.path.join(sampler.folder, "levels.txt"))
    estimate = live.LiveEstimate(sampler.folder, data_x(source))
    sampler.save(5)
    e = estimate.update()
    assert e["saves"] == 5 and e["quantiles"] is None
    assert e["levels_done_at"] is None and e["num_levels"] == 0
    assert "mean" not in e
