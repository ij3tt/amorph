"""
The screen «Прогоны»: the runs and their state, the progress of the
sampler, its output, and a live plot of the model curve of its last saved
sample.
"""

import os

import pyqtgraph as pg
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontDatabase, QTextCursor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QLabel, QPlainTextEdit, QProgressBar,
                               QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from amorph_gui import runs as R
from amorph_gui import strings as S
from amorph_gui.widgets import Screen, bold

# The curves of the live plot, as draw_model of amorph_results colours them
CURVE_STYLE = [("model_curve", S.LEGEND_MODEL, (46, 125, 50), 2),
               ("wide", S.LEGEND_WIDE, (21, 101, 192), 2),
               ("narrow", S.LEGEND_NARROW, (198, 40, 40), 1),
               ("bg", S.LEGEND_BACKGROUND, (175, 150, 0), 1)]

COLUMNS = [S.COLUMN_FOLDER, S.COLUMN_SEED, S.COLUMN_STATUS, S.COLUMN_SAVES,
           S.COLUMN_LEVELS, S.COLUMN_TIME]


class RunsScreen(Screen):
    """
    showResults(run) asks for the results of a run on «Результаты».
    """

    showResults = Signal(object)

    def __init__(self, queue, parent=None):
        super().__init__(S.SCREEN_RUNS, parent)
        self.queue = queue
        self.rows = []
        self.shown = None
        self._data_of = None
        self.stop_button = self.add_button(S.STOP, queue.stop, S.STOP_TIP)
        self.stop_button.setEnabled(False)
        self.folder_button = self.add_button(S.OPEN_FOLDER, self.open_folder)
        self.folder_button.setEnabled(False)

        self.hint = QLabel(S.NO_RUNS)
        self.body.addWidget(self.hint)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.setMaximumHeight(170)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.cellDoubleClicked.connect(self._double_clicked)
        self.body.addWidget(self.table)

        row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setMaximumWidth(260)
        self.progress_text = QLabel()
        row.addWidget(self.progress)
        row.addWidget(self.progress_text, 1)
        self.body.addLayout(row)
        self.error = QLabel()
        self.error.setStyleSheet("color: #b71c1c")
        self.error.setWordWrap(True)
        self.error.hide()
        self.body.addWidget(self.error)

        splitter = QSplitter(Qt.Horizontal)
        plot_panel = QWidget()
        layout = QVBoxLayout(plot_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot_title = bold(QLabel(S.LIVE_PLOT))
        layout.addWidget(self.plot_title)
        self.plot = pg.PlotWidget(background="w")
        item = self.plot.getPlotItem()
        item.setLabel("bottom", S.AXIS_X)
        item.setLabel("left", S.AXIS_Y)
        item.showGrid(x=True, y=True, alpha=0.15)
        item.addLegend(offset=(-10, 10))
        self.data_curve = item.plot([], [], pen=None, symbol="o",
                                    symbolSize=3, symbolPen=None,
                                    symbolBrush=(90, 90, 90, 120),
                                    name=S.LEGEND_DATA)
        self.curves = {}
        for name, label, color, width in CURVE_STYLE:
            self.curves[name] = item.plot([], [], name=label,
                                          pen=pg.mkPen(color, width=width))
        layout.addWidget(self.plot, 1)
        splitter.addWidget(plot_panel)

        log_panel = QWidget()
        layout = QVBoxLayout(log_panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(bold(QLabel(S.LOG)))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log.setMaximumBlockCount(20000)
        self.log.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        layout.addWidget(self.log, 1)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 460])
        self.body.addWidget(splitter, 1)

        queue.changed.connect(self.update_run)
        queue.output.connect(self._output)

    # ---------------------------------------------------------------- rows

    def update_run(self, run):
        if run not in self.rows:
            self.rows.append(run)
            self.table.insertRow(self.table.rowCount())
            self.hint.hide()
        i = self.rows.index(run)
        planned = str(run.planned) if run.planned else "∞"
        cells = [run.name, str(run.seed), R.STATUS_TEXT[run.status],
                 "{0} / {1}".format(run.saves, planned), str(run.levels),
                 R.format_time(run.elapsed())]
        for j, text in enumerate(cells):
            item = self.table.item(i, j)
            if item is None:
                item = QTableWidgetItem()
                self.table.setItem(i, j, item)
            item.setText(text)
            if j == 0:
                item.setToolTip(run.folder)
        # Follow the run that is running, unless another one is chosen
        if run.status == R.RUNNING and (self.shown is None
                                        or self.shown.status != R.RUNNING):
            self.table.selectRow(i)
        if run is self.shown:
            self._show_progress(run)
        self.stop_button.setEnabled(self.queue.process is not None)

    def _selected(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        run = self.rows[rows[0].row()]
        self.shown = run
        self.log.setPlainText(run.log_text())
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum())
        self.folder_button.setEnabled(True)
        self._show_progress(run)

    def _double_clicked(self, row, column):
        run = self.rows[row]
        if run.results is not None:
            self.showResults.emit(run)

    def _output(self, run, text):
        if run is self.shown:
            self.log.moveCursor(QTextCursor.End)
            self.log.insertPlainText(text)
            self.log.verticalScrollBar().setValue(
                self.log.verticalScrollBar().maximum())

    def _show_progress(self, run):
        values = {"saves": run.saves, "planned": run.planned,
                  "levels": run.levels, "time": R.format_time(run.elapsed())}
        if run.planned:
            self.progress.setRange(0, run.planned)
            self.progress.setValue(min(run.saves, run.planned))
            self.progress_text.setText(S.PROGRESS.format(**values))
        else:
            self.progress.setRange(0, 0 if run.status == R.RUNNING else 1)
            self.progress_text.setText(S.PROGRESS_UNLIMITED.format(**values))
        if run.error:
            self.error.setText(run.error)
            self.error.show()
        else:
            self.error.hide()
        self._show_sample(run)

    def _show_sample(self, run):
        sample = run.sample
        if sample is None or run.x is None:
            self.plot_title.setText(S.LIVE_PLOT)
            for curve in self.curves.values():
                curve.setData([], [])
            self.data_curve.setData([], [])
            self._data_of = None
            return
        self.plot_title.setText(S.LIVE_TITLE.format(run.saves))
        x = run.x
        for name, curve in self.curves.items():
            values = sample.get(name)
            if values is not None and values.size == x.size:
                curve.setData(x, values)
        if self._data_of is not run:
            self.data_curve.setData(x, run.y)
            self._data_of = run

    def open_folder(self):
        if self.shown is not None and os.path.isdir(self.shown.folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.shown.folder))
