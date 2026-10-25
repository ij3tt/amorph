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

from PySide6.QtCore import QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel,
                               QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

import amorph_archive

from amorph_gui import config, preferences, runfiles
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
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(theme.INK), 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawLine(QPointF(2, 19), QPointF(22, 19))
        hump = QPainterPath(QPointF(3, 18))
        hump.cubicTo(QPointF(6, 18), QPointF(6, 9), QPointF(9, 9))
        hump.cubicTo(QPointF(12, 9), QPointF(12, 18), QPointF(15, 18))
        p.drawPath(hump)
        spike = QPainterPath(QPointF(16, 18))
        spike.lineTo(QPointF(17.2, 6))
        spike.lineTo(QPointF(18.4, 18))
        p.drawPath(spike)
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
            QListWidgetItem("{0}   {1}".format(i + 1, name), self.nav)
        self.nav.setFixedWidth(224)
        self.stack = QStackedWidget()
        for screen in self.screens:
            self.stack.addWidget(screen)
            screen.openArchiveRequested.connect(self.open_archive_dialog)
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
