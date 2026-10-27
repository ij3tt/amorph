"""
Tests of the Python post-processing: src/amorph_stats.py, src/display.py,
src/export_pgf.py, the resampling of src/dnest_functions.py and
scripts/diagnose_posterior.py. Run with pytest from the repository root:

    python -m pytest tests
"""

import json
import os
import re
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import amorph_stats
import display
import dnest_functions
import export_pgf


def make_run(folder, samples=20, without_wide=5, without_narrow=0):
    """
    A fake AMORPH run in folder: the data, posterior_sample.txt and
    config.yaml, made with scripts/make_demo_posterior.py. The wide
    component is removed from the first `without_wide` posterior samples,
    and the narrow one from the first `without_narrow`.
    """
    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts", "make_demo_posterior.py"),
                    "--out", str(folder), "--samples", str(samples)],
                   check=True)

    demo = os.path.join(str(folder), "demo_posterior_sample.txt")
    with open(demo) as f:
        header = f.readline()
    names = header.lstrip("#").strip().split(",")
    rows = np.loadtxt(demo)
    n = np.loadtxt(os.path.join(str(folder), "demo_data.txt")).shape[0]

    first = names.index("wide[0]")
    rows[:without_wide, first:first + n] = 0.0
    first = names.index("narrow[0]")
    rows[:without_narrow, first:first + n] = 0.0

    with open(os.path.join(str(folder), "posterior_sample.txt"), "w") as f:
        f.write(header)
        np.savetxt(f, rows, fmt="%.7e")
    with open(os.path.join(str(folder), "config.yaml"), "w") as f:
        f.write('data_file: "demo_data.txt"\n')


def make_dnest4_output(folder, num_samples=300):
    """
    A small fake DNest4 output in folder (levels.txt, sample_info.txt,
    sample.txt), enough for dnest_functions.postprocess.
    """
    rng = np.random.default_rng(1)
    # log_X, log_likelihood, tiebreaker, accepts, tries, exceeds, visits
    levels = np.array([[0.0, -1E300, 0.0, 0, 0, 0, 0],
                       [-1.0, -50.0, 0.5, 10, 20, 0, 0],
                       [-2.0, -20.0, 0.5, 10, 20, 0, 0],
                       [-3.0, -10.0, 0.5, 10, 20, 0, 0]])
    np.savetxt(os.path.join(str(folder), "levels.txt"), levels,
               header="log_X, log_likelihood, tiebreaker, accepts, tries, "
                      "exceeds, visits")

    log_likelihood = rng.uniform(-60.0, -5.0, num_samples)
    level = np.searchsorted(levels[:, 1], log_likelihood) - 1
    info = np.column_stack([level, log_likelihood,
                            rng.uniform(size=num_samples),
                            np.zeros(num_samples)])
    np.savetxt(os.path.join(str(folder), "sample_info.txt"), info,
               header="level assignment, log likelihood, tiebreaker, ID.")
    np.savetxt(os.path.join(str(folder), "sample.txt"),
               rng.normal(size=(num_samples, 3)), header="a, b, c")


def write_lines(path, lines):
    with open(str(path), "w") as f:
        f.write("\n".join(lines) + "\n")


def data_lines(n, x0=10.0):
    return ["{0:.2f} {1}".format(x0 + 0.02 * i, 40 + i) for i in range(n)]


def test_load_data_follows_the_rules_of_the_sampler(tmp_path):
    # As in tests/test_input.cpp: a byte order mark, CRLF line endings,
    # comments and blank lines anywhere, tabs and commas as separators
    lines = (["# Scan Data", "", "10.00 41", "10.02\t42", "10.04, 43",
              "10.06 ,44", "   # a comment in between", "10.08 , 45"]
             + data_lines(6, x0=10.10))
    path = tmp_path / "data.txt"
    path.write_bytes(("﻿" + "\r\n".join(lines) + "\r\n").encode("utf-8"))

    x, y = amorph_stats.load_data(str(path))
    assert x.size == 11
    assert x[0] == 10.0 and y[0] == 41.0
    assert x[2] == 10.04 and y[2] == 43.0
    assert x[4] == 10.08 and y[4] == 45.0
    assert x[-1] == pytest.approx(10.20)


@pytest.mark.parametrize("lines, message", [
    (["10.00 41", "10.02 abc"] + data_lines(10, x0=10.04),
     "line 2: expected two numbers (x and y), got '10.02 abc'"),
    (["10.00 41 5"] + data_lines(10, x0=10.02),
     "line 1: expected two numbers (x and y), got '10.00 41 5'"),
    (["1_000 41"] + data_lines(10, x0=10.02), "line 1: expected two numbers"),
    (["nan 41"] + data_lines(10, x0=10.02), "line 1: expected two numbers"),
    (["10.00 41", "10.02 42", "10.01 43"] + data_lines(10, x0=10.04),
     "line 3: the x values must be strictly increasing, but x = 10.01 "
     "follows x = 10.02 (line 2)"),
    (data_lines(5), "found 5 data points, at least 10 are needed"),
])
def test_load_data_rejects_what_the_sampler_rejects(tmp_path, lines, message):
    path = tmp_path / "data.txt"
    write_lines(path, lines)
    with pytest.raises(ValueError, match=re.escape(message)):
        amorph_stats.load_data(str(path))


def test_load_data_reads_the_bundled_datasets():
    # The same counts and ranges as tests/test_input.cpp finds
    datasets = {"0%glass_rhyolite_Emperyon.txt": (1731, 5.01313028, 49.99313028),
                "50% glass .02step3secdwell.txt": (1501, 10.0, 40.0),
                "90%_glass_basalt_Emperyon.txt": (1731, 5.01313028, 49.99313028),
                "easy_data.txt": (1001, 0.0, 50.0),
                "G30RAW.txt": (3251, 5.0, 70.0),
                "G30RAW_15-70.txt": (2751, 15.0, 70.0),
                "G30RAW_20-50.txt": (1501, 20.0, 50.0),
                "G30RAW_amorph.txt": (1001, 26.0, 46.0),
                "N3RAW.txt": (3251, 5.0, 70.0),
                "N3RAW_15-70.txt": (2751, 15.0, 70.0),
                "N3RAW_20-50.txt": (1501, 20.0, 50.0),
                "N3RAW_amorph.txt": (1001, 26.0, 46.0)}
    for name, (n, x_min, x_max) in datasets.items():
        x, _ = amorph_stats.load_data(os.path.join(ROOT, "src", name))
        assert (x.size, x[0], x[-1]) == (n, x_min, x_max), name


def test_fraction_on_a_non_uniform_grid():
    # Dense points on the left, sparse on the right; two Gaussians of equal
    # area, the wide component on the left and the narrow one on the right
    x = np.concatenate([np.arange(0.0, 10.0, 0.01), np.arange(10.0, 20.0, 0.1)])
    wide = np.exp(-0.5 * (x - 5.0)**2)
    narrow = np.exp(-0.5 * (x - 15.0)**2)

    assert amorph_stats.amorphous_fraction(wide, narrow, x)[0] == \
        pytest.approx(0.5, abs=1E-4)
    # Plain sums count the dense points ten times over
    assert amorph_stats.amorphous_fraction(wide, narrow)[0] > 0.9


def test_shape_on_a_non_uniform_grid():
    x = np.concatenate([np.arange(0.0, 25.0, 0.01), np.arange(25.0, 50.0, 0.2)])
    gaussian = np.exp(-0.5 * (x - 25.0)**2 / 3.0**2)
    center, width, skewness, nongaussianity = \
        amorph_stats.wide_component_shape(x, gaussian)
    assert center[0] == pytest.approx(25.0, abs=1E-3)
    assert width[0] == pytest.approx(3.0, rel=1E-3)
    assert skewness[0] == pytest.approx(0.0, abs=1E-3)
    assert nongaussianity[0] == pytest.approx(0.0, abs=1E-4)


def test_postprocessing_seed(tmp_path):
    config = tmp_path / "config.yaml"
    write_lines(config, ['data_file: "data.txt"', "seed: 7"])
    assert amorph_stats.postprocessing_seed(str(config)) == 7
    write_lines(config, ['data_file: "data.txt"'])
    assert amorph_stats.postprocessing_seed(str(config)) == 0
    assert amorph_stats.postprocessing_seed(str(tmp_path / "missing.yaml")) == 0


def test_postprocessing_is_reproducible(tmp_path, monkeypatch):
    make_dnest4_output(tmp_path)
    monkeypatch.chdir(tmp_path)

    def posterior(seed):
        np.random.seed(seed)
        dnest_functions.postprocess(plot=False)
        plt.close("all")
        with open("posterior_sample.txt") as f:
            return f.read()

    first = posterior(7)
    assert posterior(7) == first
    assert posterior(8) != first


def test_fraction_without_wide_component_is_zero():
    wide = np.array([[1.0, 2.0, 1.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]])
    narrow = np.array([[1.0, 1.0, 0.0], [2.0, 2.0, 2.0], [0.0, 0.0, 0.0]])
    fraction = amorph_stats.amorphous_fraction(wide, narrow)
    assert fraction[0] == pytest.approx(4.0 / 6.0)
    assert fraction[1] == 0.0
    assert np.isnan(fraction[2])


def test_shape_of_a_gaussian_wide_component():
    x = np.linspace(0.0, 50.0, 2001)
    gaussian = 7.0 * np.exp(-0.5 * (x - 25.0)**2 / 3.0**2)
    wide = np.vstack([gaussian, np.zeros_like(x)])
    center, width, skewness, nongaussianity = \
        amorph_stats.wide_component_shape(x, wide)

    assert center[0] == pytest.approx(25.0, abs=1E-9)
    assert width[0] == pytest.approx(3.0, rel=1E-6)
    assert skewness[0] == pytest.approx(0.0, abs=1E-9)
    assert nongaussianity[0] == pytest.approx(0.0, abs=1E-9)

    # No wide component, no shape
    for value in (center[1], width[1], skewness[1], nongaussianity[1]):
        assert np.isnan(value)


def test_shape_of_a_skewed_wide_component():
    # Gamma distribution with shape 2: skewness sqrt(2)
    x = np.linspace(0.0, 80.0, 4001)
    gamma = np.where(x > 10.0, (x - 10.0) * np.exp(-(x - 10.0) / 3.0), 0.0)
    _, _, skewness, nongaussianity = amorph_stats.wide_component_shape(x, gamma)
    assert skewness[0] == pytest.approx(np.sqrt(2.0), rel=1E-2)
    assert nongaussianity[0] > 0.01


def test_display_counts_samples_without_wide_component(tmp_path, monkeypatch):
    make_run(tmp_path, samples=20, without_wide=5)
    monkeypatch.chdir(tmp_path)

    display.display()
    plt.close("all")

    table = pd.read_csv("macroquantities.csv")
    fraction = table["amorph/(amorph + crystal)"].to_numpy()
    assert np.all(fraction[:5] == 0.0)
    assert np.all((fraction[5:] > 0.0) & (fraction[5:] < 1.0))
    assert np.all(np.isnan(table["wide_center_of_mass"].to_numpy()[:5]))
    assert np.all(np.isfinite(table["wide_center_of_mass"].to_numpy()[5:]))


def test_export_pgf_reports_the_fraction_of_display(tmp_path, monkeypatch):
    make_run(tmp_path, samples=20, without_wide=5)
    monkeypatch.chdir(tmp_path)

    display.display()
    plt.close("all")
    fraction = pd.read_csv("macroquantities.csv")["amorph/(amorph + crystal)"]

    monkeypatch.setattr(sys, "argv",
                        ["export_pgf.py", "--data", "demo_data.txt",
                         "--posterior", "posterior_sample.txt",
                         "--out", "pgf", "--samples", "2"])
    export_pgf.main()

    with open(os.path.join("pgf", "xrd_data.dat")) as f:
        assert f.readline() == "x intensity\n"
    with open(os.path.join("pgf", "xrd_mean.dat")) as f:
        assert f.readline() == "x model amorph xtal background\n"
    with open(os.path.join("pgf", "xrd_samples_model.dat")) as f:
        assert f.readline() == "x sample1 sample2\n"

    # The figure gives the median of the fraction with its 50% interval
    with open(os.path.join("pgf", "xrd_meta.tex")) as f:
        meta = f.read()
    for name, q in (("median", 50.0), ("lo", 25.0), ("hi", 75.0)):
        match = re.search(r"\\xrdamorph" + name + r"\{([0-9.]+)\}", meta)
        assert match is not None, name
        assert float(match.group(1)) == pytest.approx(
            np.percentile(100.0 * fraction, q), abs=0.051)
    assert "\\def\\xrdamorph{$" in meta


def test_the_fraction_on_the_figure_stays_within_0_and_100():
    # Not symmetric, and near 100% within it, where 98 +- 10 would not be
    assert export_pgf.fraction_label(62.1434, 58.2101, 65.1488) == \
        r"$62.1^{+3.0}_{-3.9}$\,\%"
    assert export_pgf.fraction_label(98.03, 93.0, 99.52) == \
        r"$98.0^{+1.5}_{-5.0}$\,\%"
    fractions = np.array([0.6, 0.85, 0.93, 0.97, 0.98, 0.99, 0.995, 1.0])
    x = np.linspace(0.0, 1.0, 11)
    wide = np.outer(fractions, np.ones(x.size))
    narrow = np.outer(1.0 - fractions, np.ones(x.size))
    median, lo, hi = export_pgf.fraction_quantiles(wide, narrow, x)
    assert lo < median < hi <= 100.0
    assert median == pytest.approx(100.0 * np.median(fractions))
    # Undefined without either component, not 0%
    assert all(np.isnan(export_pgf.fraction_quantiles(
        np.zeros((2, 5)), np.zeros((2, 5)))))


def test_export_pgf_refuses_an_undefined_fraction(tmp_path, monkeypatch):
    # No posterior sample has either component: the fraction is undefined,
    # and must not be reported as 0%
    make_run(tmp_path, samples=4, without_wide=4, without_narrow=4)
    monkeypatch.chdir(tmp_path)
    assert np.isnan(export_pgf.amorphous_fraction(np.zeros((4, 5)),
                                                  np.zeros((4, 5))))

    monkeypatch.setattr(sys, "argv",
                        ["export_pgf.py", "--data", "demo_data.txt",
                         "--posterior", "posterior_sample.txt",
                         "--out", "pgf", "--samples", "2"])
    with pytest.raises(SystemExit, match="amorphous fraction is undefined"):
        export_pgf.main()


def test_export_pgf_takes_the_data_file_of_config_yaml(tmp_path, monkeypatch):
    # Without --data, the data file is the one config.yaml names, from the
    # folder of config.yaml, and the title is its name
    run = tmp_path / "run"
    run.mkdir()
    make_run(run, samples=6, without_wide=0)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "argv",
                        ["export_pgf.py", "--config", "run/config.yaml",
                         "--posterior", "run/posterior_sample.txt",
                         "--out", "pgf", "--samples", "0"])
    export_pgf.main()

    data = np.loadtxt(os.path.join("run", "demo_data.txt"))
    exported = np.loadtxt(os.path.join("pgf", "xrd_data.dat"), skiprows=1)
    assert exported == pytest.approx(data, rel=1E-5)
    with open(os.path.join("pgf", "xrd_meta.tex")) as f:
        assert "\\def\\xrdtitle{demo\\_data.txt}\n" in f.read()


def test_export_pgf_keeps_a_given_title(tmp_path, monkeypatch):
    make_run(tmp_path, samples=6, without_wide=0)
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(sys, "argv",
                        ["export_pgf.py", "--out", "pgf", "--samples", "0",
                         "--title", r"$\mathbf{Zr_{48}}$ 50%"])
    export_pgf.main()

    with open(os.path.join("pgf", "xrd_meta.tex")) as f:
        assert "\\def\\xrdtitle{$\\mathbf{Zr_{48}}$ 50\\%}\n" in f.read()


def test_export_pgf_needs_a_data_file(tmp_path, monkeypatch):
    make_run(tmp_path, samples=6, without_wide=0)
    monkeypatch.chdir(tmp_path)
    argv = ["export_pgf.py", "--out", "pgf", "--samples", "0"]

    os.remove("config.yaml")
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit, match="config.yaml not found"):
        export_pgf.main()

    with open("config.yaml", "w") as f:
        f.write("seed: 1\n")
    with pytest.raises(SystemExit, match="names no data_file"):
        export_pgf.main()


def test_latex_text_prints_a_file_name_as_it_is():
    assert export_pgf.latex_text("easy_data.txt") == r"easy\_data.txt"
    assert export_pgf.latex_text("50% glass #2 {a}&b.txt") == \
        r"50\% glass \#2 \{a\}\&b.txt"
    assert export_pgf.latex_text("~^$\\") == \
        r"\~{}\^{}\$\textbackslash{}"


def test_diagnose_gives_the_fraction_within_a_range(tmp_path):
    # Every particle has the wide component inside [20, 30] and the narrow
    # one outside: the fraction within the range is 1, over all the data less
    x = np.arange(10.0, 40.0, 0.02)
    n = x.size
    wide = np.exp(-0.5 * ((x - 25.0) / 1.5)**2)
    narrow = np.exp(-0.5 * ((x - 35.0) / 0.2)**2)
    names = (["num_peaks1", "num_peaks2", "max_num_peaks1", "max_num_peaks2",
              "peak_shape", "nu", "sigma0", "sigma1", "background"]
             + ["wide[{0}]".format(i) for i in range(n)]
             + ["narrow[{0}]".format(i) for i in range(n)]
             + ["model_curve[{0}]".format(i) for i in range(n)])
    row = np.concatenate([[1, 1, 10, 10, 0.0, 10.0, 1.0, 0.1, 0.0],
                          wide, narrow, wide + narrow])
    samples = np.tile(row, (20, 1))
    for name in ("sample.txt", "posterior_sample.txt"):
        np.savetxt(str(tmp_path / name), samples, header=", ".join(names))
    np.savetxt(str(tmp_path / "sample_info.txt"),
               np.column_stack([np.zeros(20), np.linspace(-10.0, -1.0, 20),
                                np.zeros(20), np.zeros(20)]),
               header="level assignment, log likelihood, tiebreaker, ID.")
    np.savetxt(str(tmp_path / "weights.txt"), np.full(20, 0.05))
    np.savetxt(str(tmp_path / "data.txt"), np.column_stack([x, wide + narrow]))

    subprocess.run([sys.executable,
                    os.path.join(ROOT, "scripts", "diagnose_posterior.py"),
                    str(tmp_path), "--data", str(tmp_path / "data.txt"),
                    "--json", str(tmp_path / "diagnosis.json"),
                    "--range", "20", "30"], check=True)
    with open(str(tmp_path / "diagnosis.json")) as f:
        diagnosis = json.load(f)

    whole = amorph_stats.amorphous_fraction(wide, narrow, x)[0]
    assert whole < 0.9
    assert diagnosis["fraction"]["q50"] == pytest.approx(whole)
    assert diagnosis["fraction_in_range"]["range"] == [20.0, 30.0]
    assert diagnosis["fraction_in_range"]["q50"] == pytest.approx(1.0)
