"""
The main window: the navigation on the left and the four screens. It
starts the runs that «Данные и модель» asks for, shows the results of
each run when it has been post-processed, and opens archives for every
screen's «Открыть архив…».
"""

import datetime
import os
import sys
import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

import amorph_archive

from amorph_gui import config, live, preferences, runfiles
from amorph_gui import runs as R
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.compare_screen import CompareScreen
from amorph_gui.data_screen import DataScreen
from amorph_gui.results_screen import ResultsScreen
from amorph_gui.runs import Run, RunQueue
from amorph_gui.runs_screen import RunsScreen
from amorph_gui.tasks import Tasks
from amorph_gui.widgets import HEADER_HEIGHT

DATA, RUNS, RESULTS, COMPARE = range(4)


class Logo(QWidget):
    """
    The mark of AMORPH: a broad hump and a sharp peak on a baseline.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(24, 24))

    def paintEvent(self, event):
        p = QPainter(self)
        theme.paint_logo(p)
        p.end()


class Brand(QWidget):
    """
    The name of the program above the navigation, as high as the header of
    a screen, so that the two make one bar.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("brand")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(HEADER_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 12, 0)
        layout.setSpacing(10)
        layout.addWidget(Logo())
        name = QLabel(S.APP_NAME)
        name.setObjectName("brandName")
        layout.addWidget(name)
        layout.addStretch(1)


class MainWindow(QMainWindow):
    """
    headless: report errors on stderr (and in self.errors) instead of in
    message boxes, for the tests and the self-test.
    """

    def __init__(self, prefs=None, headless=False, parent=None):
        super().__init__(parent)
        self.prefs = prefs if prefs is not None else preferences.Preferences()
        self.headless = headless
        self.errors = []
        self.last_archive_dir = None
        self.last_runs_dir = None
        self.setWindowTitle(S.WINDOW_TITLE)
        self.tasks = Tasks(parent=self)
        self.queue = RunQueue(self.tasks, parent=self)

        self.data_screen = DataScreen()
        self.runs_screen = RunsScreen(self.queue)
        self.results_screen = ResultsScreen(self.tasks)
        self.compare_screen = CompareScreen(self.tasks)
        self.screens = [self.data_screen, self.runs_screen,
                        self.results_screen, self.compare_screen]

        # The steps, numbered as in the design
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        for i, name in enumerate([S.SCREEN_DATA, S.SCREEN_RUNS,
                                  S.SCREEN_RESULTS, S.SCREEN_COMPARE]):
            item = QListWidgetItem("{0}   {1}".format(i + 1, name), self.nav)
            item.setSizeHint(QSize(0, 44))
        self.nav.setFixedWidth(224)
        self.stack = QStackedWidget()
        for screen in self.screens:
            self.stack.addWidget(screen)
            screen.openArchiveRequested.connect(self.open_archive_dialog)
            screen.openRunsRequested.connect(self.open_runs_dialog)
            screen.errorReported.connect(self.error)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)

        side = QWidget()
        side.setObjectName("side")
        side.setAttribute(Qt.WA_StyledBackground, True)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 8)
        side_layout.setSpacing(0)
        side_layout.addWidget(Brand())
        side_layout.addWidget(self.nav, 1)
        prefs_button = QPushButton(S.PREFERENCES)
        prefs_button.setObjectName("flat")
        prefs_button.clicked.connect(self.show_preferences)
        prefs_row = QHBoxLayout()
        prefs_row.setContentsMargins(8, 0, 8, 0)
        prefs_row.addWidget(prefs_button)
        side_layout.addLayout(prefs_row)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(side)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.nav.setCurrentRow(DATA)

        self.data_screen.runRequested.connect(self.start_runs)
        self.runs_screen.showResults.connect(self.show_run_results)
        self.compare_screen.showArchive.connect(self.open_archive)
        self.compare_screen.folderChosen.connect(
            lambda folder: self.open_paths([folder]))
        self.runs_screen.estimateWanted.connect(self.replay_run)
        # Folders of runs and archives dropped on the window open
        self.setAcceptDrops(True)
        self.results_screen.message.connect(self.status)
        self.compare_screen.message.connect(self.status)
        self.queue.postprocessed.connect(self._postprocessed)
        self.queue.finished.connect(self._batch_finished)

    def sizeHint(self):
        return QSize(1360, 860)

    def show_screen(self, index):
        self.nav.setCurrentRow(index)

    def status(self, text):
        self.statusBar().showMessage(text, 10000)

    def error(self, title, text):
        self.errors.append(text)
        if self.headless:
            print("amorph_gui: {0}: {1}".format(title, text), file=sys.stderr)
        else:
            QMessageBox.warning(self, title, text)

    def show_preferences(self):
        preferences.PreferencesDialog(self.prefs, self).exec()

    # ------------------------------------------------------------ archives

    def open_archive_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, S.CHOOSE_ARCHIVE,
                                              self.last_archive_dir or "",
                                              S.FILTER_ARCHIVE)
        if path:
            self.open_archive(path)

    def open_archive(self, path):
        """
        Read an archive in a worker thread and show it on «Результаты».
        """
        path = os.path.abspath(path)
        self.last_archive_dir = os.path.dirname(path)
        self.status(S.READING_ARCHIVE.format(path))

        def done(results):
            self.results_screen.show_results(
                results, S.SOURCE_ARCHIVE.format(path), archive=path)
            self.show_screen(RESULTS)
            self.status(S.ARCHIVE_OPENED.format(path))

        self.tasks.run(lambda: amorph_archive.read(path), done,
                       lambda e: self.error(S.ERROR, S.CANNOT_READ_ARCHIVE
                                            .format(path) + ":\n" + e))

    # ------------------------------------------- runs done elsewhere

    def open_runs_dialog(self):
        folder = QFileDialog.getExistingDirectory(
            self, S.CHOOSE_RUNS, self.last_runs_dir or self.prefs.runs_folder)
        if folder:
            self.open_paths([folder])

    def open_paths(self, paths):
        """
        Open what paths name: the run folders among them and in their
        subfolders (open_runs), and the run archives that are not in a run
        folder, on «Сравнение» (one archive alone on «Результаты»).
        """
        folders = [p for p in paths if os.path.isdir(p)]
        archives = [p for p in paths if os.path.isfile(p)
                    and p.lower().endswith(".amorph")]
        for folder in folders:
            archives += runfiles.loose_archives(folder)
        runs = self.open_runs(folders, quiet=bool(archives)) if folders             else []
        if len(archives) == 1 and not runs:
            self.open_archive(archives[0])
        elif archives:
            self.compare_screen.add_archives(archives)
            if not runs:
                self.show_screen(COMPARE)

    def open_runs(self, paths, quiet=False):
        """
        Open the run folders among paths and in their subfolders, each as a
        run on «Прогоны» with its output and its estimate, its results on
        «Результаты» and a row on «Сравнение». Its results come from its
        archive, or from the post-processing (runfiles.open_run). Folders
        already shown are left out. Returns the runs.
        """
        folders = []
        for path in paths:
            folders += runfiles.run_folders(path)
        shown = {os.path.normcase(r.folder) for r in self.runs_screen.rows}
        folders = [f for f in dict.fromkeys(folders)
                   if os.path.normcase(f) not in shown]
        if not folders:
            if not quiet:
                self.error(S.OPEN_RUNS, S.NO_RUN_FOLDERS.format(
                    ", ".join(paths)))
            return []
        self.last_runs_dir = os.path.dirname(folders[0])
        runs = []
        for folder in folders:
            run = Run(folder, None, 0, None, None)
            run.opened = True
            run.status = R.OPENING
            self.runs_screen.update_run(run)
            runs.append(run)
            self.queue.post_tasks.run(
                lambda folder=folder: runfiles.open_run(folder),
                lambda info, run=run: self._run_opened(run, info),
                lambda e, run=run: self._run_not_opened(run, e))
        if self.runs_screen.shown is None:
            self.runs_screen.show_run(runs[0])
        self.show_screen(RUNS)
        self.status(S.RUNS_OPENED.format(len(runs)))
        return runs

    def _run_opened(self, run, info):
        run.seed, run.planned = info["seed"], info["planned"]
        run.x, run.y = info["x"], info["y"]
        run.saves, run.levels = info["saves"], info["levels"]
        run.log = [info["log"]]
        run.results, run.archive = info["results"], info["archive"]
        run.status = R.INCOMPLETE if run.planned and \
            run.saves < run.planned else R.DONE
        self.runs_screen.update_run(run)
        self.results_screen.show_results(
            run.results, S.SOURCE_RUN.format(run.folder),
            archive=run.archive, stopped=run.status == R.INCOMPLETE)
        self.compare_screen.add_results(run.results, run.archive)
        if self.runs_screen.shown is run:
            self.replay_run(run)

    def _run_not_opened(self, run, error):
        run.status = R.FAILED
        run.error = S.OPEN_RUN_FAILED.format(run.folder, error)
        self.runs_screen.update_run(run)
        self.error(S.ERROR, run.error)

    def replay_run(self, run):
        """
        The estimate of a run opened from its folder, with its trace
        (live.replay), once: it reads all its saves.
        """
        if not run.opened or run.x is None or run.estimate is not None                 or getattr(run, "_replaying", False):
            return
        run._replaying = True
        folder, x = run.folder, run.x

        def done(estimate):
            run._replaying = False
            run.estimate = estimate
            self.runs_screen.update_run(run)

        def failed(error):
            run._replaying = False
            self.status(S.OPEN_RUN_FAILED.format(run.folder, error))

        self.tasks.run(lambda: live.replay(folder, x), done, failed)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls()
                 if u.isLocalFile()]
        if paths:
            event.acceptProposedAction()
            self.open_paths(paths)

    # ---------------------------------------------------------------- runs

    def start_runs(self, settings, data_path, x, y, options_template):
        """
        Make a folder for each seed and queue the runs of the sampler.
        """
        configured = self.prefs.amorph
        program = preferences.find_amorph(configured)
        if program is None:
            self.error(S.ERROR, S.AMORPH_SET_NOT_FOUND.format(configured)
                       if configured else S.AMORPH_NOT_FOUND.format(
                           ", ".join(preferences.search_folders())))
            return []
        seeds = config.run_seeds(settings, time.time())
        when = datetime.datetime.now()
        keep = config.selected(x, settings.x_range)
        runs = []
        try:
            for seed in seeds:
                folder = runfiles.prepare_run(self.prefs.runs_folder,
                                              settings, data_path, x, y, seed,
                                              options_template, when)
                runs.append(Run(folder, seed, settings.max_saves, x[keep],
                                y[keep]))
        except OSError as e:
            self.error(S.CANNOT_CREATE_RUN, str(e))
            return []
        if settings.seed is None:
            self.status(S.SEED_FROM_TIME.format(seeds[0]))
        self.queue.start(runs, program)
        self.show_screen(RUNS)
        return runs

    def show_run_results(self, run):
        self.results_screen.show_results(
            run.results, S.SOURCE_RUN.format(run.folder), archive=run.archive,
            stopped=run.stopped)
        self.show_screen(RESULTS)

    def _postprocessed(self, run):
        if run.results is None:
            self.status(run.error or "")
            return
        self.results_screen.show_results(
            run.results, S.SOURCE_RUN.format(run.folder), archive=run.archive,
            stopped=run.stopped)
        self.status(S.POSTPROCESSED.format(run.name, run.archive))

    def _batch_finished(self, runs):
        # The seeds of one batch side by side
        archives = [r.archive for r in runs if r.archive]
        if len(archives) > 1:
            self.compare_screen.add_archives(archives)
        self.status(S.QUEUE_DONE)
        if self.stack.currentIndex() == RUNS and archives:
            self.show_screen(RESULTS)

    def closeEvent(self, event):
        if self.queue.process is not None and not self.headless:
            answer = QMessageBox.question(self, S.APP_NAME, S.CLOSE_RUNNING)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
        self.queue.shutdown()
        self.tasks.wait()
        super().closeEvent(event)
