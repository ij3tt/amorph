"""
The screen «Прогоны»: the runs and their state, the progress of the
sampler, its output, and a live plot of the model curve of its last saved
sample.
"""

import os

import pyqtgraph as pg
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QTextCursor
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QHeaderView,
                               QLabel, QPlainTextEdit, QProgressBar,
                               QSplitter, QTableWidget, QTableWidgetItem,
                               QVBoxLayout, QWidget)

from amorph_gui import runs as R
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.widgets import Screen, card, styled_label

# The curves of the live plot: name in the sample, legend, colour, width,
# dashed
CURVE_STYLE = [("model_curve", S.LEGEND_MODEL, theme.ACCENT, 2.2, False),
               ("wide", S.LEGEND_WIDE, "#60A5FA", 1.5, False),
               ("narrow", S.LEGEND_NARROW, theme.NARROW, 1.2, False),
               ("bg", S.LEGEND_BACKGROUND, theme.AMBER, 1.2, True)]

COLUMNS = [S.COLUMN_FOLDER, S.COLUMN_SEED, S.COLUMN_STATUS, S.COLUMN_SAVES,
           S.COLUMN_LEVELS, S.COLUMN_TIME]
STATUS_COLUMN = 2


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
        self.set_header("", S.NO_RUNS)
        self.stop_button = self.add_button(S.STOP, queue.stop, S.STOP_TIP,
                                           kind="danger")
        self.stop_button.setEnabled(False)
        self.folder_button = self.add_button(S.OPEN_FOLDER, self.open_folder)
        self.folder_button.setEnabled(False)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(16)
        splitter.addWidget(self._make_queue())
        splitter.addWidget(self._make_live())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([480, 720])
        self.body.addWidget(splitter, 1)

        queue.changed.connect(self.update_run)
        queue.output.connect(self._output)

    # -------------------------------------------------------------- layout

    def _make_queue(self):
        queue_card, layout = card(S.QUEUE_TITLE)
        self.hint = styled_label(S.NO_RUNS, "muted")
        layout.addWidget(self.hint)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        for i in range(1, len(COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._selected)
        self.table.cellDoubleClicked.connect(self._double_clicked)
        layout.addWidget(self.table, 1)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.progress_text = QLabel()
        self.progress_text.setObjectName("mono")
        self.progress_text.setWordWrap(True)
        layout.addWidget(self.progress_text)
        self.error = QLabel()
        self.error.setStyleSheet("color: {0}".format(theme.RED))
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        layout.addWidget(styled_label(S.RUNS_NOTE, "muted"))
        return queue_card

    def _make_live(self):
        column = QWidget()
        outer = QVBoxLayout(column)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)

        legend = QLabel(theme.swatches(
            [("line", theme.DATA_LIGHT, S.LEGEND_DATA)]
            + [("dash" if dashed else "line", color, label)
               for _, label, color, _, dashed in CURVE_STYLE]))
        legend.setTextFormat(Qt.RichText)
        legend.setObjectName("muted")
        live_card, layout = card()
        self.plot_title = QLabel(S.LIVE_PLOT)
        self.plot_title.setObjectName("cardTitle")
        layout.addWidget(self.plot_title)
        layout.addWidget(legend)
        self.plot = pg.PlotWidget()
        item = theme.style_plot(self.plot, S.AXIS_X, S.AXIS_Y)
        self.data_curve = item.plot([], [], pen=pg.mkPen(theme.DATA_LIGHT,
                                                         width=1))
        self.curves = {}
        for name, _, color, width, dashed in CURVE_STYLE:
            pen = pg.mkPen(color, width=width,
                           style=Qt.DashLine if dashed else Qt.SolidLine)
            self.curves[name] = item.plot([], [], pen=pen)
        self.plot.setMinimumHeight(260)
        layout.addWidget(self.plot, 1)
        layout.addWidget(styled_label(S.LIVE_HINT, "muted"))
        outer.addWidget(live_card, 3)

        log_card, layout = card(S.LOG)
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log.setMaximumBlockCount(20000)
        self.log.setFont(theme.mono(9.0))
        layout.addWidget(self.log, 1)
        outer.addWidget(log_card, 2)
        return column

    # ---------------------------------------------------------------- rows

    def update_run(self, run):
        if run not in self.rows:
            self.rows.append(run)
            self.table.insertRow(self.table.rowCount())
            self.hint.hide()
            self.set_header("", S.RUNS_HEADER.format(len(self.rows)))
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
                if j > 0:
                    item.setFont(theme.mono(9.5))
            item.setText(text)
            if j == 0:
                item.setToolTip(run.folder)
        status = self.table.item(i, STATUS_COLUMN)
        status.setForeground(QColor(theme.STATUS_COLORS.get(run.status,
                                                            theme.INK)))
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
            # The scale of the data: early samples, near the prior, have
            # peaks thousands of times higher, which would hide the data
            item = self.plot.getPlotItem()
            item.setXRange(float(x[0]), float(x[-1]), padding=0.01)
            item.setYRange(min(0.0, float(run.y.min())),
                           float(run.y.max()) * 1.25, padding=0.0)

    def open_folder(self):
        if self.shown is not None and os.path.isdir(self.shown.folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.shown.folder))
