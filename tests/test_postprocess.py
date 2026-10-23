"""
Tests of the Python post-processing: src/amorph_stats.py, src/display.py
and src/export_pgf.py. Run with pytest from the repository root:

    python -m pytest tests
"""

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
import export_pgf


def make_run(folder, samples=20, without_wide=5):
    """
    A fake AMORPH run in folder: the data, posterior_sample.txt and
    config.yaml, made with scripts/make_demo_posterior.py. The wide
    component is removed from the first `without_wide` posterior samples.
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

    with open(os.path.join(str(folder), "posterior_sample.txt"), "w") as f:
        f.write(header)
        np.savetxt(f, rows, fmt="%.7e")
    with open(os.path.join(str(folder), "config.yaml"), "w") as f:
        f.write('data_file: "demo_data.txt"\n')


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

    with open(os.path.join("pgf", "xrd_meta.tex")) as f:
        meta = f.read()
    match = re.search(r"\\xrdamorph\{([0-9.]+)\\%\}", meta)
    assert match is not None
    assert float(match.group(1)) == pytest.approx(100.0 * fraction.mean(),
                                                  abs=0.051)
