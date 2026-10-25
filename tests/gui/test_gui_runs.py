"""
The runs of the sampler, with a fake sampler that writes the output of the
fake run of tests/test_results.py one save at a time: progress, the live
sample, the seeds one after another, the post-processing and the archive,
«Остановить», and a sampler that fails or is missing. The self-test
(python -m amorph_gui --self-test) does the same with the real AMORPH.
"""

import os
import stat
import sys

import numpy as np
import pytest

import amorph_results

from amorph_gui import digest, runfiles
from amorph_gui import runs as R
from amorph_gui import strings as S

FAKE_SAMPLER = '''#!{python}
# A fake AMORPH: copies the output of a finished run, one save at a time
import os, sys, time

source = {source!r}
assert os.path.isfile("config.yaml")


def read(name):
    with open(os.path.join(source, name)) as f:
        lines = f.readlines()
    return ([l for l in lines if l.startswith("#")],
            [l for l in lines if not l.startswith("#")])


sample_head, samples = read("sample.txt")
info_head, infos = read("sample_info.txt")
with open(os.path.join(source, "levels.txt")) as f:
    levels = f.read()
with open("sample.txt", "w") as f:
    f.writelines(sample_head)
with open("sample_info.txt", "w") as f:
    f.writelines(info_head)
print("# Read the data.", flush=True)
for k in range({saves}):
    with open("sample.txt", "a") as f:
        f.write(samples[k])
    with open("sample_info.txt", "a") as f:
        f.write(infos[k])
    with open("levels.txt", "w") as f:
        f.write(levels)
    print("# Saving particle to disk. N = {{0}}.".format(k + 1), flush=True)
    time.sleep(0.005)
if {forever}:
    # Half a save, then wait to be killed
    with open("sample.txt", "a") as f:
        f.write(samples[{saves}][:40])
    while True:
        time.sleep(0.1)
sys.exit({status})
'''


def fake_sampler(folder, source, saves, forever=False, status=0):
    path = os.path.join(str(folder), "AMORPH")
    with open(path, "w") as f:
        f.write(FAKE_SAMPLER.format(python=sys.executable, source=source,
                                    saves=saves, forever=forever,
                                    status=status))
    os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR)
    return path


pytestmark = pytest.mark.skipif(os.name == "nt",
                                reason="the fake sampler is a script")


def start(window, fake_run, sampler, seeds=2, max_saves=60):
    window.prefs._amorph = sampler
    form = window.data_screen
    assert form.open_data(os.path.join(fake_run[0], "demo_data.txt"))
    s = form.settings()
    s.control_points = (34.0, 45.0)
    s.narrow_peak_nu = (1.0, 100.0)
    s.dnest4_options_file = "OPTIONS"
    s.max_saves = max_saves
    s.seed = 5
    s.num_seeds = seeds
    form.set_settings(s)
    assert not form.errors()
    form.run_button.click()
    return window.queue.batch[:]


def test_the_seeds_run_one_after_another(window, qtbot, fake_run, tmp_path):
    folder, names, rows = fake_run
    sampler = fake_sampler(tmp_path, folder, 60)
    with qtbot.waitSignal(window.queue.finished, timeout=60000) as blocker:
        runs = start(window, fake_run, sampler)
        assert len(runs) == 2
        assert window.stack.currentIndex() == window.screens.index(
            window.runs_screen)
    assert blocker.args[0] == runs
    first, second = runs
    assert [r.seed for r in runs] == [5, 6]
    assert second.started >= first.ended
    for run in runs:
        assert run.status == R.DONE, run.error
        assert run.saves == 60 and run.levels == 4
        assert os.path.basename(run.folder).endswith(
            "_demo_data_seed{0}".format(run.seed))
        # The live sample is the last line of sample.txt
        last = rows[-1]
        first_column = names.index("model_curve[0]")
        np.testing.assert_allclose(
            run.sample["model_curve"],
            last[first_column:first_column + run.x.size])
        # Post-processed as showresults.py does, and archived
        assert os.path.isfile(os.path.join(run.folder,
                                           "posterior_sample.txt"))
        assert os.path.isfile(run.archive)
        assert len(run.results.particles) == 60
        assert "Saving particle to disk. N = 60." in run.log_text()
        assert "log/run.log" in run.results.attachments
        # The control points and the end of the run; the effective sample
        # size of a fake run is small and comes last
        assert [level for level, _, _ in digest.diagnostic_cards(
            run.results)][2:4] == [digest.OK, digest.OK]

    # The runs on «Прогоны», the last results on «Результаты», both seeds
    # on «Сравнение»
    table = window.runs_screen.table
    assert table.rowCount() == 2
    assert table.item(1, 2).text() == S.STATUS_DONE
    assert table.item(0, 3).text() == "60 / 60"
    assert window.results_screen.archive == second.archive
    assert window.stack.currentIndex() == window.screens.index(
        window.results_screen)
    qtbot.waitUntil(lambda: window.compare_screen.model.rowCount() == 2,
                    timeout=30000)


def test_stop_keeps_the_complete_saves(window, qtbot, fake_run, tmp_path):
    sampler = fake_sampler(tmp_path, fake_run[0], 30, forever=True)
    runs = start(window, fake_run, sampler, seeds=2)
    run = runs[0]
    qtbot.waitUntil(lambda: run.saves == 30, timeout=30000)
    assert window.runs_screen.stop_button.isEnabled()
    with qtbot.waitSignal(window.queue.finished, timeout=60000):
        window.runs_screen.stop_button.click()
    assert run.status == R.INCOMPLETE, run.error
    assert runs[1].status == R.CANCELLED
    assert not os.path.exists(os.path.join(runs[1].folder, "sample.txt"))
    assert len(run.results.particles) == 30
    assert S.RUN_STOPPED_LOG.format(30) in run.log_text()
    with open(os.path.join(run.folder, runfiles.LOG_FILE),
              encoding="utf-8") as f:
        assert S.RUN_STOPPED_LOG.format(30) in f.read()
    cards = digest.diagnostic_cards(run.results, stopped=True)
    assert (digest.AMBER, S.CARD_STOP_TITLE,
            S.CARD_STOP_BAD.format(30, 60)) in cards
    # Shown so on «Результаты»
    assert window.results_screen.stopped
    assert window.runs_screen.table.item(0, 2).text() == S.STATUS_INCOMPLETE


def test_closing_the_window_leaves_the_complete_saves(window, qtbot,
                                                     fake_run, tmp_path):
    sampler = fake_sampler(tmp_path, fake_run[0], 30, forever=True)
    run = start(window, fake_run, sampler, seeds=1)[0]
    qtbot.waitUntil(lambda: run.saves == 30, timeout=30000)
    window.close()
    assert run.status == R.INCOMPLETE
    assert window.queue.process is None
    with open(os.path.join(run.folder, "sample.txt"), "rb") as f:
        assert f.read().endswith(b"\n")
    assert runfiles.count_data_lines(os.path.join(run.folder,
                                                  "sample.txt")) == 30
    with open(os.path.join(run.folder, runfiles.LOG_FILE),
              encoding="utf-8") as f:
        assert S.RUN_STOPPED_LOG.format(30) in f.read()


def test_a_failing_sampler(window, qtbot, fake_run, tmp_path):
    sampler = fake_sampler(tmp_path, fake_run[0], 3, status=1)
    with qtbot.waitSignal(window.queue.finished, timeout=60000):
        runs = start(window, fake_run, sampler, seeds=2)
    for run in runs:
        assert run.status == R.FAILED
        assert run.error == S.RUN_FAILED.format(1)
        assert run.results is None


def test_a_missing_sampler(window, fake_run, tmp_path):
    missing = str(tmp_path / "no" / "AMORPH")
    runs = start(window, fake_run, missing)
    assert runs == []
    assert window.errors == [S.AMORPH_SET_NOT_FOUND.format(missing)]
    assert not os.path.exists(window.prefs.runs_folder)


def test_progress_of_the_files(fake_run, tmp_path):
    folder, names, rows = fake_run
    with open(os.path.join(folder, "sample.txt"), "rb") as f:
        data = f.read()
    path = tmp_path / "sample.txt"
    # A save cut off at the end, as by a kill
    path.write_bytes(data + b"1 2 3")
    assert runfiles.count_data_lines(str(path)) == len(rows)
    assert runfiles.last_line(str(path), block_size=64) == \
        data.splitlines()[-1]
    reader = runfiles.SampleReader(str(path))
    curves = reader.read()
    first = names.index("wide[0]")
    n = sum(1 for c in names if c.startswith("wide["))
    np.testing.assert_allclose(curves["wide"], rows[-1, first:first + n])
    assert sorted(curves) == sorted(amorph_results.CURVES)

    # Nothing saved yet
    path.write_bytes(data.splitlines(keepends=True)[0])
    assert runfiles.SampleReader(str(path)).read() is None
    assert runfiles.count_data_lines(str(tmp_path / "missing.txt")) == 0


def test_levels_cut_by_a_kill_are_put_back(fake_run, tmp_path):
    folder = tmp_path / "run"
    folder.mkdir()
    with open(os.path.join(fake_run[0], "levels.txt"), "rb") as f:
        levels = f.read()
    (folder / "levels.txt").write_bytes(levels)
    saved = runfiles.levels_text(str(folder))
    assert saved == levels
    # Nothing to put back
    assert not runfiles.restore_levels(str(folder), saved)
    # Killed while the sampler rewrote it
    (folder / "levels.txt").write_bytes(levels[:levels.index(b"\n") + 1])
    assert runfiles.levels_text(str(folder)) is None
    assert runfiles.restore_levels(str(folder), saved)
    assert (folder / "levels.txt").read_bytes() == levels
    (folder / "levels.txt").write_bytes(levels[:-20])
    assert runfiles.restore_levels(str(folder), saved)
    assert not runfiles.restore_levels(str(folder), None)
