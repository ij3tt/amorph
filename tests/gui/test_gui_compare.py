"""
The comparison table of «Сравнение»: one row per archive, the interval bar
drawn by its delegate, and the export as CSV and Markdown.
"""

import io
import os
import shutil

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import amorph_archive
import amorph_results

from amorph_gui import digest
from amorph_gui import strings as S
from amorph_gui.compare_screen import INTERVAL_COLUMN, QUANTILES_ROLE
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
        assert cell(model, row, 4) == "{0:.3f} [{1:.3f}, {2:.3f}]".format(
            f["q50"], f["q25"], f["q75"])
        assert cell(model, row, 6) == "{0:.1%}".format(
            d["weight_fraction_below_0.2"])
        assert cell(model, row, 7) == "{0:.1%}".format(
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


def test_the_screen_shows_the_summary(window, qtbot, archives):
    screen = loaded(window, qtbot, [archives["seed5"], archives["seed6"]])
    assert screen.summary.text() == "\n".join(
        digest.comparison_summary(screen.model.rows))
    screen.clear()
    assert screen.summary.text() == S.SUMMARY_EMPTY
