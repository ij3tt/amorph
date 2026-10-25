"""
Tests of the results of a run (src/amorph_results.py), the run archives
(src/amorph_archive.py) and what display.py does with them, on a fake run
with the layout of the real output of AMORPH. Run with pytest from the
repository root:

    python -m pytest tests
"""

import os
import subprocess
import sys
import zipfile

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import amorph_archive
import amorph_results
import amorph_stats
import display
import dnest_functions

NUM_SAMPLES = 60


def make_full_run(folder, samples=NUM_SAMPLES):
    """
    A fake run in folder with everything that the sampler and the DNest4
    post-processing write: sample.txt with the columns of the sampler (the
    samples of scripts/make_demo_posterior.py), sample_info.txt and
    levels.txt, and posterior_sample.txt and weights.txt from
    dnest_functions.postprocess. The first 10 samples have one narrow peak
    fewer than the others. Returns the column names and the rows of
    sample.txt.
    """
    folder = str(folder)
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts", "make_demo_posterior.py"),
                    "--out", folder, "--samples", str(samples)],
                   check=True, stdout=subprocess.DEVNULL)
    demo = os.path.join(folder, "demo_posterior_sample.txt")
    with open(demo) as f:
        names = f.readline().lstrip("#").strip().split(",")
    rows = np.loadtxt(demo)
    os.remove(demo)

    k = names.index("num_peaks1")
    count = int(rows[0, k])
    rows[:10, k] = count - 1
    for quantity in ("center1", "log_amplitude1", "width1"):
        rows[:10, names.index("{0}[{1}]".format(quantity, count - 1))] = 0.0

    # As the sampler writes it: each value followed by a space
    with open(os.path.join(folder, "sample.txt"), "w") as f:
        f.write("# " + ", ".join(names) + "\n")
        for row in rows:
            f.write("".join("{0:.10g} ".format(v) for v in row) + "\n")
    rows = np.loadtxt(os.path.join(folder, "sample.txt"))

    rng = np.random.default_rng(2)
    # log_X, log_likelihood, tiebreaker, accepts, tries, exceeds, visits
    levels = np.array([[0.0, -1E300, 0.0, 0, 0, 0, 0],
                       [-1.0, -50.0, 0.5, 10, 20, 0, 0],
                       [-2.0, -20.0, 0.5, 10, 20, 0, 0],
                       [-3.0, -10.0, 0.5, 10, 20, 0, 0]])
    np.savetxt(os.path.join(folder, "levels.txt"), levels,
               header="log_X, log_likelihood, tiebreaker, accepts, tries, "
                      "exceeds, visits")
    log_likelihood = rng.uniform(-60.0, -5.0, samples)
    level = np.searchsorted(levels[:, 1], log_likelihood) - 1
    np.savetxt(os.path.join(folder, "sample_info.txt"),
               np.column_stack([level, log_likelihood,
                                rng.uniform(size=samples),
                                np.zeros(samples)]),
               header="level assignment, log likelihood, tiebreaker, ID.")
    with open(os.path.join(folder, "config.yaml"), "w") as f:
        f.write('data_file: "demo_data.txt"\nseed: 5\n')

    cwd = os.getcwd()
    os.chdir(folder)
    try:
        np.random.seed(5)
        dnest_functions.postprocess(plot=False, verbose=False)
    finally:
        os.chdir(cwd)
    return names, rows


@pytest.fixture
def run(tmp_path):
    names, rows = make_full_run(tmp_path)
    return str(tmp_path), names, rows


def curve(names, rows, name, n):
    first = names.index(name + "[0]")
    return rows[:, first:first + n]


def test_sampler_numbers_are_those_of_postprocess(run, monkeypatch):
    folder, _, _ = run
    results = amorph_results.from_run(folder)

    monkeypatch.chdir(folder)
    weights = np.loadtxt("weights.txt")
    log_z, information, log_x = dnest_functions.postprocess(
        plot=False, save=False, verbose=False)
    sampler = results.sampler
    assert sampler["weight"] == pytest.approx(weights / weights.sum())
    assert sampler["log_z"] == pytest.approx(log_z)
    assert sampler["information"] == pytest.approx(information)
    assert sampler["log_x"] == pytest.approx(log_x[:, 0])


def test_particles_and_their_peaks(run):
    folder, names, rows = run
    results = amorph_results.from_run(folder)
    x = results.x
    wide = curve(names, rows, "wide", x.size)
    narrow = curve(names, rows, "narrow", x.size)

    particles = results.particles
    assert len(particles) == NUM_SAMPLES
    assert particles["weight"].sum() == pytest.approx(1.0)
    assert particles["fraction"].to_numpy() == pytest.approx(
        amorph_stats.amorphous_fraction(wide, narrow, x))
    center, width, _, _ = amorph_stats.wide_component_shape(x, wide)
    assert particles["wide_center_of_mass"].to_numpy() == pytest.approx(center)
    assert particles["wide_halfwidth"].to_numpy() == pytest.approx(width)

    # Only the peaks that are switched on, in the order of the sampler
    peaks = results.peaks
    count = int(rows[-1, names.index("num_peaks1")])
    narrow_peaks = peaks["component"] == 1
    assert narrow_peaks.sum() == count * NUM_SAMPLES - 10
    assert (peaks["component"] == 2).sum() == \
        int(rows[0, names.index("num_peaks2")]) * NUM_SAMPLES
    first = names.index("center1[0]")
    assert peaks["center"][narrow_peaks & (peaks["particle"] == 0)] == \
        pytest.approx(rows[0, first:first + count - 1])
    assert peaks["center"][narrow_peaks & (peaks["particle"] == 10)] == \
        pytest.approx(rows[10, first:first + count])
    assert results.info["max_num_narrow_peaks"] == \
        int(rows[0, names.index("max_num_peaks1")])


def test_posterior_samples_and_curves(run):
    folder, names, _ = run
    results = amorph_results.from_run(folder)
    posterior = np.atleast_2d(np.loadtxt(os.path.join(folder,
                                                      "posterior_sample.txt")))
    n = results.x.size
    assert len(results.posterior) == posterior.shape[0]
    assert results.posterior["fraction"].to_numpy() == pytest.approx(
        amorph_stats.amorphous_fraction(curve(names, posterior, "wide", n),
                                        curve(names, posterior, "narrow", n),
                                        results.x))
    assert results.curves["model_curve_mean"] == pytest.approx(
        curve(names, posterior, "model_curve", n).mean(axis=0), rel=1E-6)
    assert results.curves["wide_quantiles"].shape == (5, n)
    assert results.curves["bg_examples"].shape == \
        (min(amorph_results.NUM_EXAMPLES, posterior.shape[0]), n)
    assert np.all(np.isfinite(results.curves["residuals"]))


def test_report_has_what_showresults_and_the_diagnosis_print(run):
    folder, _, _ = run
    text = "\n".join(amorph_results.report_lines(
        amorph_results.from_run(folder)))
    for phrase in ("Data: demo_data.txt", "log(Z) = ", "Information = ",
                   "Effective sample size = ",
                   "(amorph)/(amorph + crystal) = ", "Center of mass = ",
                   "Half-width = ", "Skewness = ", "Nongaussianity = ",
                   "Saved particles: {0}".format(NUM_SAMPLES),
                   "Posterior weight with fraction 0",
                   "Per band of the fraction"):
        assert phrase in text


def test_every_figure_draws(run):
    folder, _, _ = run
    results = amorph_results.from_run(folder)
    available = amorph_results.available_figures(results)
    assert [name for name, _, _ in available] == \
        [name for name, _, _, _ in amorph_results.FIGURES]
    for name, _, draw in available:
        fig = Figure()
        draw(fig, results)
        assert fig.axes, name


def test_archive_keeps_the_results(run, tmp_path_factory):
    folder, _, _ = run
    results = amorph_results.from_run(folder)
    path = os.path.join(str(tmp_path_factory.mktemp("archive")),
                        "run.amorph")
    amorph_archive.write(results, path)
    back = amorph_archive.read(path)

    assert amorph_results.report_lines(back) == \
        amorph_results.report_lines(results)
    pd.testing.assert_frame_equal(back.particles, results.particles)
    pd.testing.assert_frame_equal(back.posterior, results.posterior)
    assert sorted(back.curves) == sorted(results.curves)
    for key in results.curves:
        np.testing.assert_array_equal(back.curves[key], results.curves[key])
    for key in ("levels", "sample_info", "log_x", "weight"):
        np.testing.assert_array_equal(back.sampler[key],
                                      results.sampler[key])
    for key in ("particle", "component"):
        np.testing.assert_array_equal(back.peaks[key], results.peaks[key])
    for key in ("center", "log_amplitude", "width"):
        np.testing.assert_allclose(back.peaks[key], results.peaks[key],
                                   rtol=1E-6)
    assert [f[0] for f in amorph_results.available_figures(back)] == \
        [f[0] for f in amorph_results.available_figures(results)]

    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        report = z.read("report.html").decode()
    for name in ("README.txt", "manifest.json", "summary.json", "report.txt",
                 "report.html", "input/config.yaml", "input/demo_data.txt",
                 "dnest4/levels.txt", "dnest4/sample_info.txt",
                 "dnest4/weights.txt", "sampler.csv", "particles.csv",
                 "posterior.csv", "peaks.npz", "curves.npz"):
        assert name in names
    assert report.count("data:image/png;base64,") == \
        len(amorph_results.FIGURES)
    assert os.path.getsize(path) < os.path.getsize(
        os.path.join(folder, "sample.txt"))


def test_archive_from_the_command_line(run, tmp_path_factory):
    folder, _, _ = run
    out = str(tmp_path_factory.mktemp("cli"))
    archive = os.path.join(out, "run.amorph")
    script = os.path.join(ROOT, "src", "amorph_archive.py")
    env = dict(os.environ, MPLBACKEND="Agg")
    subprocess.run([sys.executable, script, folder, "--out", archive],
                   check=True, env=env)
    shown = subprocess.run([sys.executable, script, "--show", archive],
                           check=True, env=env, capture_output=True,
                           text=True).stdout
    assert "log(Z) = " in shown
    subprocess.run([sys.executable, script, "--figures",
                    os.path.join(out, "figures"), archive],
                   check=True, env=env)
    for name, _, _, _ in amorph_results.FIGURES:
        assert os.path.isfile(os.path.join(out, "figures", name + ".png"))


def test_display_reports_and_archives(run, monkeypatch, capsys):
    folder, _, _ = run
    monkeypatch.chdir(folder)
    display.display()
    plt.close("all")

    out = capsys.readouterr().out
    assert "Effective sample size = " in out
    assert "Saved the results of the run in" in out
    archives = [f for f in os.listdir(".") if f.endswith(".amorph")]
    assert len(archives) == 1 and archives[0].startswith("demo_data_")
    table = pd.read_csv("macroquantities.csv")
    assert list(table.columns) == [
        "Sample number", "num_narrow_peaks", "amorph/(amorph + crystal)",
        "wide_center_of_mass", "wide_halfwidth", "wide_skewness",
        "wide_nongaussianity"]


def test_trim_outputs_keeps_the_complete_samples(run):
    # A sampler stopped while writing: half a line of sample.txt with no
    # line of sample_info.txt yet, and half a line of levels.txt
    folder, _, _ = run
    with open(os.path.join(folder, "sample.txt"), "a") as f:
        f.write("1 2 3")
    with open(os.path.join(folder, "levels.txt"), "a") as f:
        f.write("-4.0 -5.0")
    assert amorph_stats.trim_outputs(folder) == NUM_SAMPLES
    assert np.loadtxt(os.path.join(folder, "levels.txt")).shape[0] == 4
    results = amorph_results.from_run(folder)
    assert len(results.particles) == NUM_SAMPLES
