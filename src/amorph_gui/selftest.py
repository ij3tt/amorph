"""
The self-test of the GUI, without a screen:

    python -m amorph_gui --self-test DIR [--amorph PATH]

opens the bundled easy_data.txt on «Данные и модель», runs two seeds with
tiny DNest4 options (those of scripts/smoke_test.sh) through the run
machinery of the GUI, post-processes them and writes their archives; then
runs a third seed without a limit on the saves and stops it, compares the
three archives and opens one again. It saves a screenshot of every screen
to DIR, and the runs go to DIR/runs. The exit status is 0 if all of it
worked.
"""

import os
import sys
import time
import traceback

# Before Qt starts: no screen is needed
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QSettings, QTimer  # noqa: E402

from amorph_gui.app import application  # noqa: E402

from amorph_gui import SRC_DIR, digest  # noqa: E402
from amorph_gui import runs as R  # noqa: E402
from amorph_gui import strings as S  # noqa: E402
from amorph_gui.main_window import COMPARE, DATA, RESULTS, RUNS  # noqa: E402
from amorph_gui.main_window import MainWindow  # noqa: E402
from amorph_gui.preferences import Preferences  # noqa: E402

# A sampler configuration that ends after a handful of levels, as in
# scripts/smoke_test.sh
SMOKE_OPTIONS_NAME = "OPTIONS_SMOKE"
SMOKE_OPTIONS = """# Smoke test options for DNest4
1	# Number of particles
50	# new level interval
50	# save interval
20	# threadSteps
5	# maximum number of levels
5	# Backtracking scale length (lambda in the paper)
100	# Strength of effect to force histogram to equal push
100	# Maximum number of saves
sample.txt	# file for the posterior samples
sample_info.txt	# file for information about the samples
levels.txt	# file for information about the levels
"""

# Seconds that each step may take
TIMEOUT = 600


class Failure(Exception):
    pass


def wait_until(condition, what, timeout=TIMEOUT):
    """
    Run the event loop until condition() is true.
    """
    if condition():
        return
    end = time.monotonic() + timeout
    loop = QEventLoop()
    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(
        lambda: loop.quit() if condition() or time.monotonic() > end
        else None)
    timer.start()
    loop.exec()
    timer.stop()
    if not condition():
        raise Failure("timed out waiting for " + what)


def settle(app, seconds=0.3):
    # Let the plots and the layouts catch up before a screenshot
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


class SelfTest(object):

    def __init__(self, app, window, out_dir):
        self.app = app
        self.window = window
        self.out_dir = out_dir
        self.shots = []
        self.batches = []
        window.queue.finished.connect(self.batches.append)

    def shot(self, name, screen=None, tab=None):
        if screen is not None:
            self.window.show_screen(screen)
        if tab is not None:
            self.window.results_screen.tabs.setCurrentIndex(tab)
        settle(self.app)
        path = os.path.join(self.out_dir, name + ".png")
        if not self.window.grab().save(path):
            raise Failure("could not save " + path)
        self.shots.append(path)
        print("self-test: screenshot " + path)

    def check(self, condition, text):
        if not condition:
            raise Failure(text)

    def run_batch(self, settings):
        data = self.window.data_screen
        data.set_settings(settings)
        self.check(not data.errors(), "the checks failed: {0}".format(
            data.errors()))
        count = len(self.batches)
        data.run_button.click()
        self.check(self.window.queue.busy(), "no runs started: {0}".format(
            self.window.errors))
        return count

    def run(self):
        w = self.window
        data = w.data_screen
        easy = os.path.join(SRC_DIR, "easy_data.txt")
        self.check(data.open_data(easy), "could not open " + easy)
        data.add_options(SMOKE_OPTIONS_NAME, SMOKE_OPTIONS)

        # What the checks say about doubtful settings
        s = data.settings()
        s.x_range = (12.0, 46.0)
        s.narrow_peak_nu = (0.1, 100.0)
        data.set_settings(s)
        self.check(data.errors() and data.warnings(),
                   "the checks found nothing wrong with control points "
                   "outside the range and nu from 0.1")
        self.shot("01-data-checks", DATA)

        # Two seeds that run to the end
        s = data.settings()
        s.x_range = (2.0, 48.0)
        s.narrow_peak_nu = (1.0, 100.0)
        s.num_threads = 2
        s.max_num_narrow_peaks = 20
        s.max_num_wide_peaks = 10
        s.dnest4_options_file = SMOKE_OPTIONS_NAME
        s.max_saves = 100
        s.seed = 1
        s.num_seeds = 2
        data.set_settings(s)
        self.shot("02-data", DATA)
        count = self.run_batch(s)
        wait_until(lambda: len(self.batches) > count, "the first runs")
        runs = self.batches[-1]
        for run in runs:
            print("self-test: {0}: {1}, {2} saves, {3} levels, {4}".format(
                run.name, R.STATUS_TEXT[run.status], run.saves, run.levels,
                run.archive))
            self.check(run.status == R.DONE, "{0} ended as {1}: {2}".format(
                run.name, run.status, run.error))
            self.check(run.archive and os.path.isfile(run.archive),
                       "no archive for " + run.name)
            self.check(run.saves == 100, "{0} has {1} saves, not 100".format(
                run.name, run.saves))
            self.check(run.sample is not None,
                       "no live sample was read for " + run.name)
            f = run.results.diagnosis["fraction"]
            print("self-test: {0}: fraction {1:.3f} [{2:.3f}, {3:.3f}]"
                  .format(run.name, f["q50"], f["q25"], f["q75"]))
        self.check(len(runs) == 2, "{0} runs, not 2".format(len(runs)))
        self.check(runs[0].seed == 1 and runs[1].seed == 2,
                   "the seeds are not 1 and 2")
        self.shot("03-runs", RUNS)
        for i, name in enumerate(["summary", "model", "distributions",
                                  "sampler", "report"]):
            self.shot("{0:02d}-results-{1}".format(4 + i, name), RESULTS, i)

        # A seed without a limit on the saves, stopped by «Остановить»
        s.max_saves = 0
        s.seed = 3
        s.num_seeds = 1
        count = self.run_batch(s)
        stopped = w.queue.current
        wait_until(lambda: stopped.saves >= 30, "30 saves of the run to stop")
        w.runs_screen.stop_button.click()
        wait_until(lambda: len(self.batches) > count, "the stopped run")
        print("self-test: {0}: {1}, {2} saves, {3}".format(
            stopped.name, R.STATUS_TEXT[stopped.status], stopped.saves,
            stopped.archive))
        self.check(stopped.status == R.INCOMPLETE,
                   "the stopped run ended as {0}: {1}".format(stopped.status,
                                                              stopped.error))
        self.check(stopped.archive and os.path.isfile(stopped.archive),
                   "no archive for the stopped run")
        cards = digest.diagnostic_cards(stopped.results, stopped=True)
        self.check(any(level == digest.AMBER and title == S.CARD_STOP_TITLE
                       for level, title, _ in cards),
                   "no card says that the run was stopped")
        self.shot("09-runs-stopped", RUNS)
        self.shot("10-results-stopped", RESULTS, 0)

        # The three archives side by side
        compare = w.compare_screen
        wait_until(lambda: compare.pending == 0, "the comparison")
        compare.add_archives([stopped.archive])
        wait_until(lambda: compare.pending == 0, "the comparison")
        self.check(compare.model.rowCount() == 3,
                   "{0} rows in the comparison, not 3".format(
                       compare.model.rowCount()))
        self.shot("11-compare", COMPARE)

        # «Открыть архив…»
        archive = runs[0].archive
        w.open_archive(archive)
        wait_until(lambda: w.results_screen.archive == archive,
                   "the archive to open")
        self.shot("12-results-archive", RESULTS, 0)
        self.check(not w.errors, "errors: {0}".format(w.errors))


def main(out_dir, amorph=None):
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    app = application(["amorph_gui", "--self-test"])
    store = QSettings(os.path.join(out_dir, "settings.ini"),
                      QSettings.IniFormat)
    prefs = Preferences(store, amorph=amorph,
                        runs=os.path.join(out_dir, "runs"))
    window = MainWindow(prefs, headless=True)
    window.resize(1440, 900)
    window.show()
    test = SelfTest(app, window, out_dir)
    try:
        test.run()
    except Failure as e:
        print("self-test: FAILED - {0}".format(e), file=sys.stderr)
        status = 1
    except Exception:
        traceback.print_exc()
        print("self-test: FAILED", file=sys.stderr)
        status = 1
    else:
        print("self-test: PASSED, {0} screenshots in {1}".format(
            len(test.shots), out_dir))
        status = 0
    window.close()
    return status
