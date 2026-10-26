"""
The comparison table of «Сравнение»: one row per archive, the interval bar
drawn by its delegate, and the export as CSV and Markdown.
"""

import glob
import io
import os
import shutil

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import amorph_archive
import amorph_results
import amorph_seeds

from amorph_gui import digest, theme
from amorph_gui import strings as S
from amorph_gui.compare_screen import (INTERVAL_COLUMN, LOG_Z_COLUMN,
                                       QUANTILES_ROLE)
from amorph_gui.main_window import RESULTS
from amorph_gui.widgets import ACCENT


def loaded(window, qtbot, paths):
    screen = window.compare_screen
    screen.add_archives(paths)
    qtbot.waitUntil(lambda: screen.pending == 0, timeout=30000)
    return screen


def cell(model, row, column):
    return model.data(model.index(row, column))


def test_comparison_table(window, qtbot, archives):
    paths = [archives["seed5"], archives["seed6"]]
    screen = loaded(window, qtbot, paths)
    model = screen.model
    assert model.rowCount() == 2

    for row, path in enumerate(paths):
        d = amorph_archive.read(path).diagnosis
        f = d["fraction"]
        assert cell(model, row, 0) == "{0}/{1}".format(
            os.path.basename(os.path.dirname(path)), os.path.basename(path))
        assert cell(model, row, 1) == "demo_data.txt"
        assert cell(model, row, 3) == str(5 + row)
        assert cell(model, row, 4).startswith("OPTIONS · ")
        assert cell(model, row, 5) == "{0:.0f}".format(
            d["effective_sample_size"])
        assert cell(model, row, 7) == "{0:.3f} [{1:.3f}, {2:.3f}]".format(
            f["q50"], f["q25"], f["q75"])
        assert cell(model, row, 9) == "{0:.1%}".format(
            d["weight_fraction_below_0.2"])
        assert cell(model, row, 10) == "{0:.1%}".format(
            d["weight_narrow_at_cap"])
        assert model.data(model.index(row, INTERVAL_COLUMN),
                          QUANTILES_ROLE) == [f[q] for q in (
                              "q05", "q25", "q50", "q75", "q95")]
    assert "ν [1, 100]" in cell(model, 0, 2)
    assert "ν [0.1, 100]" in cell(model, 1, 2)
    assert "фон [34, 45]" in cell(model, 0, 2)

    # The common scale covers the 90% intervals of both rows
    lo, hi = model.scale()
    for row in model.rows:
        assert lo <= row["q05"] and row["q95"] <= hi
    assert model.headerData(INTERVAL_COLUMN, Qt.Horizontal) == \
        "Интервал {0:.2f}–{1:.2f}".format(lo, hi)


def test_the_delegate_draws_the_interval(window, qtbot, archives):
    screen = loaded(window, qtbot, [archives["seed5"]])
    window.show_screen(window.screens.index(screen))
    qtbot.wait(100)
    rect = screen.view.visualRect(screen.model.index(0, INTERVAL_COLUMN))
    image = screen.view.viewport().grab().toImage()
    ratio = image.devicePixelRatio()
    colors = {image.pixelColor(int(x * ratio), int(rect.center().y() * ratio))
              .name() for x in range(rect.left(), rect.right())}
    assert ACCENT.name() in colors or QColor("#0d2b52").name() in colors


def test_export(window, qtbot, archives):
    paths = [archives["seed5"], archives["seed6"]]
    screen = loaded(window, qtbot, paths)
    rows = screen.model.rows

    table = pd.read_csv(io.StringIO(digest.rows_csv(rows)))
    assert list(table["archive"]) == paths
    assert list(table["seed"]) == [5, 6]
    assert list(table["narrow_peak_nu_min"]) == [1.0, 0.1]
    assert list(table["control_point_1"]) == [34.0, 34.0]
    for i, path in enumerate(paths):
        f = amorph_archive.read(path).diagnosis["fraction"]
        for q in ("q05", "q25", "q50", "q75", "q95"):
            assert table["fraction_" + q][i] == f[q]

    lines = digest.rows_markdown(rows).splitlines()
    assert lines[0].startswith("| Архив | Данные | Настройки | seed |")
    assert lines[1].startswith("| --- |")
    assert len(lines) == 4
    assert lines[2].count("|") == lines[0].count("|")
    assert digest.fraction_text(rows[0]) in lines[2]

    # The buttons write the same
    out = os.path.dirname(paths[0])
    screen.save_file_name = lambda *args: os.path.join(out, "table.md")
    screen.export_markdown_dialog()
    with open(os.path.join(out, "table.md"), encoding="utf-8") as f:
        assert f.read() == digest.rows_markdown(rows)
    screen.save_file_name = lambda *args: os.path.join(out, "table.csv")
    screen.export_csv_dialog()
    with open(os.path.join(out, "table.csv"), encoding="utf-8") as f:
        assert f.read() == digest.rows_csv(rows)


def test_archives_of_the_workflows(window, qtbot, fake_run, tmp_path):
    # validate and experiment upload run.amorph, written by
    # scripts/ci/summarize_run.py with the data file given apart
    folders = []
    for name in ("run-N3RAW-seed1", "run-N3RAW-seed2"):
        folder = tmp_path / name
        folder.mkdir()
        data = os.path.join(fake_run[0], "demo_data.txt")
        amorph_archive.write(amorph_results.from_run(fake_run[0],
                                                     data_file=data),
                             str(folder / "run.amorph"))
        folders.append(str(folder / "run.amorph"))
    screen = loaded(window, qtbot, folders)
    assert [cell(screen.model, i, 0) for i in range(2)] == \
        ["run-N3RAW-seed1/run.amorph", "run-N3RAW-seed2/run.amorph"]
    # The fake run has a seed but no other settings
    assert cell(screen.model, 0, 3) == "5"


def test_rows_go_and_open_on_results(window, qtbot, archives):
    paths = [archives["seed5"], archives["seed6"], archives["plain"]]
    screen = loaded(window, qtbot, paths)
    assert screen.model.rowCount() == 3

    screen.view.selectRow(1)
    screen.remove_selected()
    assert [r["archive"] for r in screen.model.rows] == [paths[0], paths[2]]

    screen._double_clicked(screen.model.index(1, 0))
    qtbot.waitUntil(lambda: window.results_screen.archive == paths[2],
                    timeout=20000)
    assert window.stack.currentIndex() == RESULTS

    screen.clear()
    assert screen.model.rowCount() == 0


def test_a_broken_archive_is_reported_in_the_table(window, qtbot, archives,
                                                   tmp_path):
    broken = str(tmp_path / "broken.amorph")
    shutil.copyfile(archives["seed5"], broken)
    with open(broken, "r+b") as f:
        f.truncate(100)
    screen = loaded(window, qtbot, [broken, archives["seed6"]])
    assert screen.model.rowCount() == 1
    assert not screen.errors.isHidden() and "broken.amorph" in \
        screen.errors.text()


def test_comparison_summary():
    def row(data, settings, q50):
        return {"data_file": data, "settings": settings, "q50": q50}

    assert digest.comparison_summary([]) == [S.SUMMARY_EMPTY]
    # Two seeds of one setting: their spread, nothing about settings
    lines = digest.comparison_summary([row("a.txt", "A", 0.70),
                                       row("a.txt", "A", 0.72)])
    assert lines == [S.SUMMARY_SEEDS.format(0.02)]
    # The settings move the fraction more than the seeds do
    lines = digest.comparison_summary([
        row("a.txt", "A", 0.718), row("a.txt", "A", 0.722),
        row("a.txt", "B", 0.630), row("a.txt", "B", 0.634)])
    assert lines[0] == S.SUMMARY_SEEDS.format(0.004)
    assert lines[1] == S.SUMMARY_SETTINGS.format(0.632, 0.720, 0.088)
    assert lines[2] == S.SUMMARY_BIGGER
    # One run per setting: the spread of the seeds is unknown
    lines = digest.comparison_summary([row("a.txt", "A", 0.7),
                                       row("a.txt", "B", 0.6)])
    assert lines[0] == S.SUMMARY_ONE_SEED and len(lines) == 2
    # Two data files: each on its own
    lines = digest.comparison_summary([
        row("a.txt", "A", 0.70), row("a.txt", "A", 0.71),
        row("b.txt", "A", 0.50), row("b.txt", "A", 0.52)])
    assert lines[0] == S.SUMMARY_DATA.format("a.txt")
    assert lines[2] == S.SUMMARY_DATA.format("b.txt")


def test_a_run_with_a_low_log_z_is_left_out(window, qtbot, archives):
    # Two runs of the same data and settings, one with a log(Z) 10 nats
    # lower: it did not converge
    results = amorph_archive.read(archives["seed5"])
    good = digest.comparison_row(results, os.path.join("a", "good.amorph"))
    bad = digest.comparison_row(results, os.path.join("b", "bad.amorph"))
    bad["log_z"] = good["log_z"] - 10.0
    model = window.compare_screen.model
    model.add(good)
    model.add(bad)
    assert good["dlog_z"] == 0.0
    assert bad["dlog_z"] == pytest.approx(-10.0)
    assert S.CHECK_LOG_Z.format(10.0) in digest.check_text(bad)
    assert digest.check_level(bad) == digest.RED
    assert not bad["chosen"]
    assert good["chosen"] == (digest.check_level(good) != digest.RED)
    assert cell(model, 1, LOG_Z_COLUMN) == "−10.0"
    assert model.data(model.index(1, LOG_Z_COLUMN), Qt.ForegroundRole) == \
        QColor(theme.RED)
    assert model.data(model.index(1, 0), Qt.CheckStateRole) == Qt.Unchecked

    # Ticked by the user, it stays ticked, and the report warns
    model.setData(model.index(1, 0), Qt.Checked, Qt.CheckStateRole)
    assert bad["chosen"] and bad["chosen_by_user"]
    model.add(digest.comparison_row(results, os.path.join("c", "c.amorph")))
    assert bad["chosen"]
    model.choose(0, True)
    _, notes, _ = digest.joint_report(model.rows)
    assert (digest.RED, S.JOINT_BAD_LOG_Z.format(10.0)) in notes
    # The summary leaves out the runs that are not ticked
    model.choose(1, False)
    assert digest.comparison_summary(model.rows) == \
        digest.comparison_summary([r for r in model.rows if r is not bad])


def test_the_joint_report_and_its_figure(window, qtbot, archives, tmp_path):
    paths = [archives["seed5"], archives["seed6"]]
    screen = loaded(window, qtbot, paths)
    for i in range(2):
        screen.model.choose(i, True)
    screen.refresh_joint()
    expected = amorph_seeds.pool([amorph_archive.read(p) for p in paths])
    pooled = screen.pooled
    assert pooled["seeds"] == [5, 6]
    assert pooled["quantiles"] == pytest.approx(expected["quantiles"])
    assert screen.joint_value.text() == "{0:.3f}".format(
        expected["quantiles"][2])
    # Seeds 5 and 6 have different ranges of nu: the report says so
    _, notes, paper = digest.joint_report(screen.model.rows)
    assert (digest.AMBER, S.JOINT_SETTINGS) in notes
    assert paper.startswith("demo_data: ") and "2 сида" in paper
    assert screen.paper.text() == paper
    assert screen.title() == "demo_data.txt"

    # The figure in both styles, and what the buttons write
    for style in ("fit", "seeds"):
        screen.set_style(style)
        assert screen.figure.axes
    data = str(tmp_path / "pgf")
    screen.export_data(data)
    tex = str(tmp_path / "tex")
    screen.export_tex(tex)
    png = str(tmp_path / "figure.png")
    screen.export_file("png", png)
    qtbot.waitUntil(lambda: screen.tasks.active == 0, timeout=30000)
    for name in ("xrd_meta.tex", "xrd_mean.dat", "seeds_meta.tex",
                 "seeds_curves.dat"):
        assert os.path.isfile(os.path.join(data, name))
    for name in ("xrd_seeds.tex", "xrd_seeds_body.tex", "build.sh",
                 "build.bat", os.path.join("pgf", "seeds_meta.tex")):
        assert os.path.isfile(os.path.join(tex, name))
    with open(png, "rb") as f:
        assert f.read(8) == b"\x89PNG\r\n\x1a\n"

    # Nothing ticked: no report and nothing to export
    for i in range(2):
        screen.model.choose(i, False)
    screen.refresh_joint()
    assert screen.pooled is None
    assert screen.joint_value.text() == "—"
    assert not screen.export_buttons["data"].isEnabled()


def test_a_folder_of_archives(window, qtbot, archives):
    folder = os.path.dirname(archives["seed5"])
    screen = window.compare_screen
    screen.add_folder(folder)
    qtbot.waitUntil(lambda: screen.pending == 0, timeout=30000)
    assert screen.model.rowCount() == len(glob.glob(
        os.path.join(folder, "**", "*.amorph"), recursive=True))
    screen.clear()
    screen.add_folder(os.path.join(folder, "run"))
    assert not screen.errors.isHidden()
    assert screen.model.rowCount() == 0


def test_the_screen_shows_the_summary(window, qtbot, archives):
    screen = loaded(window, qtbot, [archives["seed5"], archives["seed6"]])
    assert screen.summary.text() == "\n".join(
        digest.comparison_summary(screen.model.rows))
    screen.clear()
    assert screen.summary.text() == S.SUMMARY_EMPTY
