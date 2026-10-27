"""
The report for LaTeX (src/amorph_gui/report.py): its folder and its text
for one run and for two seeds, in Russian and in English, on the fake run
of test_results.py and a shifted copy of it, and its build where pdflatex
is installed. Run with
pytest from the repository root:
    python -m pytest tests
"""

import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import amorph_results
import amorph_tex

from amorph_gui import digest, report, strings_en
from amorph_gui import strings as S
from test_results import make_full_run
from test_seeds import shifted


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    folder = tmp_path_factory.mktemp("run")
    make_full_run(folder)
    return amorph_results.from_run(str(folder))


def rows_of(*runs):
    rows = [digest.comparison_row(r, "seed{0}.amorph".format(i))
            for i, r in enumerate(runs)]
    digest.mark_log_z(rows)
    # Ticked, whatever the checks of the fake run say
    for row in rows:
        row["chosen"] = True
    return rows


def test_text_as_latex():
    assert report.latex("a_b 50% Δ log Z −0.8, ν ≤ 2, 2θ") == (
        r"a\_b 50\% $\Delta$ log Z $-$0.8, $\nu$ $\le$ 2, 2$\theta$")
    # Cyrillic, dashes and guillemets are printed by T2A as they are
    assert report.latex("доля — «гало»") == "доля — «гало»"


def test_the_report_of_two_seeds(results, tmp_path):
    rows = rows_of(results, shifted(results, 0.05))
    path = report.write_report(rows, str(tmp_path / "report"),
                               date="2026-10-27")
    folder = os.path.dirname(path)
    for name in ("report.tex", "xrd_fit_body.tex", "xrd_seeds_body.tex",
                 "build.bat", "build.sh",
                 os.path.join("pgf", "xrd_meta.tex"),
                 os.path.join("pgf", "xrd_samples.tex"),
                 os.path.join("pgf", "seeds_meta.tex")):
        assert os.path.isfile(os.path.join(folder, name)), name
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert text.count(r"\begin{document}") == 1
    assert text.rstrip().endswith(r"\end{document}")
    assert r"\input{xrd_fit_body.tex}" in text
    assert r"\input{xrd_seeds_body.tex}" in text
    assert "2026-10-27" in text
    # The pooled fraction, the line for a paper, both seeds in the table
    # and their diagnostic cards
    pooled, notes, paper = digest.joint_report(rows)
    assert "{0:.3f}".format(pooled["quantiles"][2]) in text
    assert report.latex(paper) in text
    assert "\n5 & " in text and "\n99 & " in text
    assert text.count(r"\subsection*{seed ") == 2
    for _, title, _ in digest.diagnostic_cards(rows[0]["results"]):
        assert report.latex(title) in text
    # Nothing that LaTeX with T2A cannot print as it is
    assert not any(c in text for c in report.UNICODE)


def test_the_report_of_one_run(results, tmp_path):
    rows = report.results_rows(results, "run.amorph")
    path = report.write_report(rows, str(tmp_path / "one"))
    with open(path, encoding="utf-8") as f:
        text = f.read()
    assert report.latex(S.JOINT_ONE) in text
    assert r"\subsection*" not in text
    d = results.diagnosis["fraction"]
    assert report.latex(S.REPORT_FRACTION.format(
        q05=d["q05"], q25=d["q25"], q50=d["q50"], q75=d["q75"],
        q95=d["q95"])) in text


def test_the_report_in_english(results, tmp_path):
    rows = rows_of(results, shifted(results, 0.05))
    path = report.write_report(rows, str(tmp_path / "en"), language="en")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    # Every text in English: the report, the cards, the checks, the notes
    # and the line for a paper
    assert not re.search("[А-Яа-яЁё]", text)
    assert r"\usepackage[russian,english]{babel}" in text
    assert "2 seeds together" in text
    assert report.latex(digest.check_text(rows[0], strings_en)) in text
    _, notes, paper = digest.joint_report(rows, strings_en)
    assert paper.endswith(strings_en.PAPER_SEEDS.format(
        2, "seeds", digest.joint_report(rows)[0]["spread"]))
    assert report.latex(paper) in text
    for name, _ in strings_en.REPORT_NOTE_ITEMS:
        assert report.latex(name) in text
    # The texts of the two languages have the same names (the Russian
    # notes are the tooltips of helptext)
    for name in dir(strings_en):
        if name.isupper() and name != "REPORT_NOTE_ITEMS":
            assert hasattr(S, name), name


def test_nothing_to_report(results, tmp_path):
    rows = rows_of(results)
    rows[0]["chosen"] = False
    with pytest.raises(ValueError):
        report.write_report(rows, str(tmp_path / "none"))


@pytest.mark.skipif("pdflatex" not in amorph_tex.find_latex(),
                    reason="LaTeX is not installed")
@pytest.mark.parametrize("language", ["ru", "en"])
def test_pdflatex_builds_the_report(results, tmp_path, language):
    path = report.write_report(rows_of(results, shifted(results, 0.05)),
                               str(tmp_path / language), language=language)
    folder = os.path.dirname(path)
    run = subprocess.run([amorph_tex.find_latex()["pdflatex"],
                          "-interaction=nonstopmode", "-halt-on-error",
                          report.REPORT], cwd=folder,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         timeout=amorph_tex.TIMEOUT)
    assert run.returncode == 0, run.stdout.decode(errors="replace")[-3000:]
    assert os.path.getsize(os.path.join(folder, "report.pdf")) > 10000
