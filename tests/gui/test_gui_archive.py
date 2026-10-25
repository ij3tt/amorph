"""
Archives on «Результаты»: an archive of the fake run of
tests/test_results.py, opened from every screen, its tabs and exports,
and the diagnostic cards.
"""

import os
import zipfile

import pandas as pd
from PySide6.QtWidgets import QFileDialog, QLabel, QPlainTextEdit

import amorph_archive
import amorph_results

from amorph_gui import digest
from amorph_gui import strings as S
from amorph_gui.main_window import RESULTS
from amorph_gui.results_screen import (DISTRIBUTION_FIGURES, MODEL_FIGURES,
                                       SAMPLER_FIGURES)


def open_archive(window, qtbot, path):
    window.open_archive(path)
    qtbot.waitUntil(lambda: window.results_screen.archive == path,
                    timeout=20000)
    return window.results_screen


def test_archive_of_the_fake_run(window, qtbot, archives):
    path = archives["seed5"]
    screen = open_archive(window, qtbot, path)
    assert window.stack.currentIndex() == RESULTS
    results = amorph_archive.read(path)
    d = results.diagnosis

    # Итог: the fraction with its intervals, the cards, the notes
    summary = screen.tabs.widget(0)
    fraction = summary.findChild(QLabel, "fraction")
    assert fraction.text() == "{0:.3f}".format(d["fraction"]["q50"])
    texts = [label.text() for label in summary.findChildren(QLabel)]
    f = d["fraction"]
    assert S.FRACTION_INTERVALS.format(f["q25"], f["q75"], f["q05"],
                                       f["q95"]) in texts
    assert S.NOTE_FRACTION in texts and S.NOTE_SEEDS in texts
    assert any(t.startswith("Эффективный размер выборки: {0:.0f}".format(
        d["effective_sample_size"])) for t in texts)
    for level, title, text in digest.diagnostic_cards(results):
        assert title in texts and text in texts

    # The figures of each tab, drawn when it is shown
    for tab, names in ((1, MODEL_FIGURES), (2, DISTRIBUTION_FIGURES),
                       (3, SAMPLER_FIGURES)):
        screen.tabs.setCurrentIndex(tab)
        for name in names:
            view = screen.figure_views[name]
            assert view.figure.axes, name
    assert len(DISTRIBUTION_FIGURES) == 6
    sampler = screen.tabs.widget(3).findChild(QLabel, "sampler_numbers")
    assert "log(Z) = {0:.6g}".format(results.sampler["log_z"]) in \
        sampler.text()

    screen.tabs.setCurrentIndex(4)
    report = screen.tabs.widget(4).findChild(QPlainTextEdit, "report")
    assert report.toPlainText() == "\n".join(
        amorph_results.report_lines(results))


def test_every_screen_opens_an_archive(window, qtbot, archives, monkeypatch):
    paths = [archives["seed5"], archives["seed6"], archives["plain"],
             archives["seed5"]]
    for screen, path in zip(window.screens, paths):
        monkeypatch.setattr(QFileDialog, "getOpenFileName",
                            lambda *args, path=path, **kwargs: (path, ""))
        window.results_screen.archive = None
        window.show_screen(window.screens.index(screen))
        screen.archive_button.click()
        qtbot.waitUntil(lambda: window.results_screen.archive == path,
                        timeout=20000)
        assert window.stack.currentIndex() == RESULTS


def test_an_unreadable_archive_is_reported(window, qtbot, tmp_path):
    path = str(tmp_path / "broken.amorph")
    with open(path, "wb") as f:
        f.write(b"not a zip file")
    window.open_archive(path)
    qtbot.waitUntil(lambda: bool(window.errors), timeout=20000)
    assert "broken.amorph" in window.errors[0]


def test_exports(window, qtbot, archives, tmp_path, monkeypatch):
    path = archives["seed5"]
    screen = open_archive(window, qtbot, path)
    results = screen.results

    out = str(tmp_path / "posterior.csv")
    screen.write_posterior(out)
    qtbot.waitUntil(lambda: os.path.isfile(out), timeout=20000)
    qtbot.waitUntil(lambda: screen.tasks.active == 0, timeout=20000)
    pd.testing.assert_frame_equal(pd.read_csv(out), results.posterior,
                                  check_exact=False, rtol=1E-12)

    copy = str(tmp_path / "copy.amorph")
    screen.write_archive(copy)
    qtbot.waitUntil(lambda: screen.tasks.active == 0, timeout=20000)
    with open(copy, "rb") as f, open(path, "rb") as g:
        assert f.read() == g.read()

    folder = tmp_path / "figures"
    folder.mkdir()
    screen.write_figures(str(folder))
    qtbot.waitUntil(lambda: screen.tasks.active == 0, timeout=60000)
    assert sorted(os.listdir(folder)) == sorted(
        "demo_data_{0}.png".format(name) for name, _, _
        in amorph_results.available_figures(results))

    # One figure, from its button
    screen.tabs.setCurrentIndex(1)
    png = str(tmp_path / "model.png")
    monkeypatch.setattr(QFileDialog, "getSaveFileName",
                        lambda *args, **kwargs: (png, ""))
    screen.figure_views["model"].save_png()
    with open(png, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_results_of_a_folder_are_archived_on_export(window, qtbot,
                                                    fake_run, tmp_path):
    # Results without an archive (straight from a run folder) are written
    results = amorph_results.from_run(fake_run[0])
    window.results_screen.show_results(results, "test")
    out = str(tmp_path / "written.amorph")
    window.results_screen.write_archive(out)
    qtbot.waitUntil(lambda: window.results_screen.tasks.active == 0,
                    timeout=60000)
    with zipfile.ZipFile(out) as z:
        assert "summary.json" in z.namelist()


class FakeResults(object):

    def __init__(self, below=0.0, at_cap=0.0, cps=(34.0, 45.0), saves=100,
                 planned=100):
        options = "# options\n" + "1\n" * 7 + "{0}\n".format(planned) + \
            "sample.txt\nsample_info.txt\nlevels.txt\n"
        self.info = {"x_min": 33.0, "x_max": 46.0, "num_saves": saves,
                     "config": {"dnest4_options_file": "OPTIONS",
                                "inference_assumptions": {
                                    "control_points": list(cps)}}}
        self.attachments = {"input/OPTIONS": options.encode()}
        self.diagnosis = {"weight_fraction_below_0.2": below,
                          "weight_narrow_at_cap": at_cap,
                          "max_num_narrow_peaks": 500, "saves": saves}


def levels(results, stopped=False):
    return [level for level, _, _ in digest.diagnostic_cards(results,
                                                             stopped)]


def test_diagnostic_cards():
    assert levels(FakeResults()) == [digest.OK] * 4
    # Weight below 0.2 over 5%: red
    assert levels(FakeResults(below=0.051))[0] == digest.RED
    assert levels(FakeResults(below=0.05))[0] == digest.OK
    # Weight at the cap over 5%: amber
    assert levels(FakeResults(at_cap=0.2))[1] == digest.AMBER
    # Control points outside the data: amber
    assert levels(FakeResults(cps=(10.0, 40.0)))[2] == digest.AMBER
    assert levels(FakeResults(cps=(33.0, 46.0)))[2] == digest.OK
    # Stopped early: amber
    assert levels(FakeResults(saves=50))[3] == digest.AMBER
    assert levels(FakeResults(planned=0))[3] == digest.AMBER
    assert levels(FakeResults(), stopped=True)[3] == digest.AMBER


def test_cards_without_the_settings(archives):
    # The config.yaml of the fake run has no control points
    results = amorph_archive.read(archives["plain"])
    titles = [title for _, title, _ in digest.diagnostic_cards(results)]
    assert S.CARD_CP_TITLE not in titles
    assert len(titles) == 2
