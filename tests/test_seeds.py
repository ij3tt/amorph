"""
Tests of several seeds of one sample together (src/amorph_seeds.py) and of
their figures for LaTeX (src/amorph_tex.py), on the fake run of
test_results.py. Run with pytest from the repository root:

    python -m pytest tests
"""

import copy
import os
import re
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import amorph_results
import amorph_seeds
import amorph_tex
from test_results import make_full_run

QUANTILES = ["q05", "q25", "q50", "q75", "q95"]


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    folder = tmp_path_factory.mktemp("run")
    make_full_run(folder)
    return amorph_results.from_run(str(folder))


def shifted(results, by):
    """
    A copy of the results whose fraction is larger by `by`, as another seed
    with another posterior.
    """
    other = copy.copy(results)
    other.particles = results.particles.copy()
    other.particles["fraction"] = other.particles["fraction"] + by
    other.info = dict(results.info, config=dict(results.info["config"],
                                                seed=99))
    return other


def test_one_run_is_its_own_report(results):
    pooled = amorph_seeds.pool([results])
    d = results.diagnosis["fraction"]
    assert pooled["quantiles"] == pytest.approx([d[q] for q in QUANTILES],
                                                abs=1E-12)
    assert pooled["spread"] is None
    assert pooled["seeds"] == [5]
    q = results.curves["model_curve_quantiles"]
    np.testing.assert_allclose(pooled["band"][0], q[0])
    np.testing.assert_allclose(pooled["band"][1], q[-1])
    for name in ("bg", "wide", "narrow", "model_curve"):
        np.testing.assert_allclose(pooled["curves"][name],
                                   results.curves[name + "_mean"])
    fraction = results.posterior["fraction"].to_numpy()
    assert pooled["mean"] == pytest.approx(np.nanmean(fraction))
    assert len(pooled["examples"]["model_curve"]) == \
        min(amorph_seeds.NUM_EXAMPLES,
            len(results.curves["model_curve_examples"]))
    h = pooled["histogram"]
    widths = np.diff(h["edges"])
    assert np.sum(h["pooled"] * widths) == pytest.approx(1.0)


def test_seeds_count_equally(results):
    other = shifted(results, 0.1)
    pooled = amorph_seeds.pool([results, other])
    medians = [q[2] for q in pooled["seed_quantiles"]]
    assert medians[1] - medians[0] == pytest.approx(0.1)
    assert pooled["spread"] == pytest.approx(0.1)
    assert pooled["seeds"] == [5, 99]
    assert medians[0] < pooled["quantiles"][2] < medians[1]
    # The faint curves come from the seeds in turn, as many as there are up
    # to NUM_EXAMPLES
    each = len(results.curves["model_curve_examples"])
    assert len(pooled["examples"]["model_curve"]) == \
        min(amorph_seeds.NUM_EXAMPLES, 2 * each)
    # Two copies of one run are that run
    twice = amorph_seeds.pool([results, results])
    assert twice["quantiles"] == pytest.approx(
        amorph_seeds.pool([results])["quantiles"], abs=1E-12)
    assert twice["spread"] == 0.0


def test_mixture_quantiles():
    # Two uniform distributions, on [0, 1] and [1, 2], at three points
    p = np.array([0.05, 0.16, 0.5, 0.84, 0.95])
    first = np.repeat(p[:, None], 3, axis=1)
    second = first + 1.0
    for wanted, expected in ((0.5, 1.0), (0.05, 0.1), (0.95, 1.9),
                             (0.25, 0.5)):
        value = amorph_seeds.mixture_quantile([first, second], p, wanted)
        np.testing.assert_allclose(value, expected, atol=1E-9)
    # One distribution: its own quantiles
    np.testing.assert_allclose(
        amorph_seeds.mixture_quantile([second], p, 0.16), second[1])


def test_runs_of_other_data_are_refused(results):
    other = copy.copy(results)
    other.x = results.x + 1.0
    with pytest.raises(ValueError, match="different data"):
        amorph_seeds.pool([results, other])
    with pytest.raises(ValueError):
        amorph_seeds.pool([])


def read_macros(path):
    with open(path) as f:
        return dict(re.findall(r"\\def\\(\w+)\{(.*?)\}(?=\\def|\n)", f.read()))


def test_tables_of_both_figures(results, tmp_path):
    pooled = amorph_seeds.pool([results, shifted(results, 0.05)])
    out = str(tmp_path / "pgf")
    amorph_tex.write_tables(pooled, out, "demo_data.txt")
    names = sorted(os.listdir(out))
    for name in ("xrd_data.dat", "xrd_mean.dat", "xrd_meta.tex",
                 "xrd_samples.tex", "xrd_samples_model.dat",
                 "xrd_samples_amorph.dat", "xrd_samples_xtal.dat",
                 "seeds_curves.dat", "seeds_halo.dat", "seeds_fraction.dat",
                 "seeds_halos.tex", "seeds_densities.tex", "seeds_meta.tex"):
        assert name in names

    # The tables of export_pgf.py
    with open(os.path.join(out, "xrd_mean.dat")) as f:
        assert f.readline() == "x model amorph xtal background\n"
    mean = np.loadtxt(os.path.join(out, "xrd_mean.dat"), skiprows=1)
    np.testing.assert_allclose(mean[:, 1], pooled["curves"]["model_curve"],
                               rtol=1E-5)
    meta = read_macros(os.path.join(out, "xrd_meta.tex"))
    assert meta["xrdtitle"] == "demo\\_data.txt"
    assert float(meta["xrdamorph"].rstrip("\\%")) == pytest.approx(
        100.0 * pooled["mean"], abs=0.051)
    assert meta["xrdnsamples"] == str(len(pooled["examples"]["model_curve"]))

    # The tables of the two-panel figure
    curves = np.loadtxt(os.path.join(out, "seeds_curves.dat"), skiprows=1)
    np.testing.assert_allclose(curves[:, 2], pooled["curves"]["bg"]
                               + pooled["curves"]["wide"], rtol=1E-5)
    np.testing.assert_allclose(curves[:, 5], pooled["band"][0], rtol=1E-5)
    with open(os.path.join(out, "seeds_fraction.dat")) as f:
        assert f.readline() == "f pooled seed1 seed2\n"
    with open(os.path.join(out, "seeds_densities.tex")) as f:
        text = f.read()
    assert "seed 5" in text and "seed 99" in text
    seeds = read_macros(os.path.join(out, "seeds_meta.tex"))
    assert seeds["seedsmedian"] == "{0:.3f}".format(pooled["quantiles"][2])
    assert "seeds 5, 99" in seeds["seedstitle"]


def test_folder_of_a_figure(results, tmp_path):
    pooled = amorph_seeds.pool([results])
    for figure, files in amorph_tex.FIGURES.items():
        folder = str(tmp_path / figure)
        tex = amorph_tex.write_figure(pooled, folder, figure, "demo")
        assert tex == os.path.join(folder, files[0])
        for name in files + ("build.sh", "build.bat"):
            assert os.path.isfile(os.path.join(folder, name))
        assert os.path.isfile(os.path.join(folder, "pgf", "xrd_meta.tex"))
        stem = os.path.splitext(files[0])[0]
        with open(os.path.join(folder, "build.sh")) as f:
            script = f.read()
        assert "pdflatex" in script and "dvisvgm" in script \
            and stem + ".tex" in script
        # The templates are those of doc/figures
        with open(os.path.join(ROOT, "doc", "figures", files[0])) as f, \
                open(tex) as g:
            assert f.read() == g.read()


def test_a_missing_program_is_named(results, tmp_path):
    pooled = amorph_seeds.pool([results])
    folder = str(tmp_path / "fit")
    amorph_tex.write_figure(pooled, folder, "fit", "demo")
    with pytest.raises(amorph_tex.BuildError, match="latex, dvisvgm"):
        amorph_tex.build(folder, "fit", "svg", {})


@pytest.mark.skipif(len(amorph_tex.find_latex()) < len(amorph_tex.TOOLS),
                    reason="LaTeX is not installed")
def test_latex_builds_pdf_and_svg(results, tmp_path):
    tools = amorph_tex.find_latex()
    pooled = amorph_seeds.pool([results, shifted(results, 0.05)])
    for figure in amorph_tex.FIGURES:
        folder = str(tmp_path / figure)
        amorph_tex.write_figure(pooled, folder, figure, "demo")
        for kind in ("pdf", "svg"):
            path = amorph_tex.build(folder, figure, kind, tools)
            assert os.path.getsize(path) > 1000
