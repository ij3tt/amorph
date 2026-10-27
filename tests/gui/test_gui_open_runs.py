"""
Runs opened from their folders («Открыть прогоны…», a folder chosen on
«Сравнение», or folders dropped on the window): each on «Прогоны» with its
output and estimate, its results on «Результаты» and a row on «Сравнение».
"""

import os
import shutil

import yaml

from amorph_gui import config
from amorph_gui import runs as R
from amorph_gui import strings as S
from amorph_gui.main_window import COMPARE, RUNS
from gui_helpers import SRC, full_config, write_archive


def run_folder(fake_run, to, seed, archived, planned):
    """
    A copy of the fake run in to, with the config.yaml of a run of the GUI
    and its options file for planned saves, and its archive if archived.
    """
    shutil.copytree(fake_run[0], str(to))
    if archived:
        write_archive(str(to), str(to / "run.amorph"), seed)
    else:
        with open(str(to / "config.yaml"), "w") as f:
            yaml.safe_dump(full_config(seed), f)
    with open(os.path.join(SRC, "OPTIONS")) as f:
        options = config.options_with_max_saves(f.read(), planned)
    with open(str(to / "OPTIONS"), "w") as f:
        f.write(options)
    return str(to)


def test_a_folder_of_runs_opens_everywhere(window, qtbot, fake_run,
                                           tmp_path):
    top = tmp_path / "work"
    # The first still runs (60 of 10000 saves), the second is done
    first = run_folder(fake_run, top / "a_seed5", 5, archived=True,
                       planned=10000)
    second = run_folder(fake_run, top / "b_seed6", 6, archived=False,
                        planned=60)
    window.open_paths([str(top)])
    screen = window.runs_screen
    assert [r.folder for r in screen.rows] == [first, second]
    assert window.stack.currentIndex() == RUNS
    qtbot.waitUntil(lambda: all(r.status != R.OPENING for r in screen.rows),
                    timeout=60000)
    for run, seed in zip(screen.rows, (5, 6)):
        assert run.error is None
        assert run.opened and run.seed == seed
        assert run.saves == 60 and run.levels == 4
        assert os.path.isfile(run.archive)
        assert run.results.diagnosis is not None
    assert [r.planned for r in screen.rows] == [10000, 60]
    assert [r.status for r in screen.rows] == [R.INCOMPLETE, R.DONE]
    # The first had its archive; the second was post-processed into one
    assert screen.rows[0].archive == os.path.join(first, "run.amorph")
    assert os.path.dirname(screen.rows[1].archive) == second
    assert screen.table.item(0, 1).text() == "5"
    assert screen.table.item(0, 5).text() == "—"

    # Both on «Сравнение», the last on «Результаты»
    compare = window.compare_screen
    qtbot.waitUntil(lambda: compare.model.rowCount() == 2, timeout=30000)
    assert window.results_screen.results is not None

    # Their joint report, and its figure as a folder for LaTeX
    compare.refresh_joint()
    assert sorted(compare.pooled["seeds"]) == [5, 6]
    tex = str(tmp_path / "tex")
    compare.export_tex(tex)
    qtbot.waitUntil(lambda: compare.tasks.active == 0, timeout=30000)
    for name in ("xrd_fit.tex", "xrd_fit_body.tex", "build.bat",
                 os.path.join("pgf", "xrd_meta.tex")):
        assert os.path.isfile(os.path.join(tex, name)), name

    # The first is chosen: its estimate is made from its saves
    run = screen.rows[0]
    assert screen.shown is run
    qtbot.waitUntil(lambda: run.estimate is not None, timeout=60000)
    assert run.estimate["saves"] == 60
    assert len(run.estimate["trace"]) > 1
    d = run.results.diagnosis["fraction"]
    assert abs(run.estimate["quantiles"][2] - d["q50"]) < 1E-9
    assert screen.fraction_value.text() == S.FRACTION_NOW.format(d["q50"])

    # Opened again: nothing new, no error, and their rows on «Сравнение»
    # are back after «Очистить»
    errors = list(window.errors)
    compare.clear()
    window.open_paths([str(top)])
    assert len(screen.rows) == 2
    assert window.errors == errors
    assert sorted(r["archive"] for r in compare.model.rows) == \
        sorted(r.archive for r in screen.rows)
    window.open_paths([str(top)])
    assert compare.model.rowCount() == 2


def test_no_runs_in_a_folder(window, tmp_path):
    (tmp_path / "empty").mkdir()
    window.open_paths([str(tmp_path / "empty")])
    assert window.errors == [S.NO_RUN_FOLDERS.format(
        str(tmp_path / "empty"))]
    assert window.runs_screen.rows == []


def test_loose_archives_go_to_the_comparison(window, qtbot, archives,
                                             tmp_path):
    folder = tmp_path / "ci"
    folder.mkdir()
    for name in ("seed5", "seed6"):
        shutil.copyfile(archives[name], str(folder / (name + ".amorph")))
    window.open_paths([str(folder)])
    compare = window.compare_screen
    qtbot.waitUntil(lambda: compare.model.rowCount() == 2, timeout=30000)
    assert window.stack.currentIndex() == COMPARE
    assert window.errors == []
    assert window.runs_screen.rows == []
