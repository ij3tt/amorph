"""
The screen «Прогоны»: the runs and their state, the progress of the
sampler and its output, and the estimate of the run while it works
(live.LiveEstimate): the amorphous fraction with its intervals and how it
moved, and the model with its parts, the background, the amorphous halo
and the crystalline peaks, for the posterior mean, the best sample or the
last saved one, each part a layer that can be hidden; and where these are
among the levels of the sampler.
"""

import os

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QRectF, Qt, QUrl, Signal
from PySide6.QtGui import (QColor, QDesktopServices, QPainter, QPen,
                           QTextCursor)
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton,
                               QScrollArea, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from amorph_gui import helptext
from amorph_gui import runs as R
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.widgets import (Banner, HelpButton, Screen, card,
                                styled_label, title_row, tooltip)

COLUMNS = [S.COLUMN_FOLDER, S.COLUMN_SEED, S.COLUMN_STATUS, S.COLUMN_SAVES,
           S.COLUMN_LEVELS, S.COLUMN_TIME]
STATUS_COLUMN = 2

# What the model plot shows: the posterior mean, the best sample so far or
# the last saved one
VIEWS = [("mean", S.VIEW_MEAN), ("best", S.VIEW_BEST), ("last", S.VIEW_LAST)]

# The layers of the model plot, in the order of their chips
LAYERS = [("data", S.LAYER_DATA), ("bg", S.LAYER_BG),
          ("halo", S.LAYER_HALO), ("xtal", S.LAYER_XTAL),
          ("model", S.LAYER_MODEL), ("band", S.LAYER_BAND)]


def _brush(color, alpha):
    return pg.mkBrush(theme.qcolor(color, alpha))


def _hidden():
    # A curve that only bounds a fill
    return pg.PlotDataItem([], [], pen=pg.mkPen(None))


class LevelGauge(QWidget):
    """
    The levels of the sampler as a bar: where the posterior weight is, and
    the levels of the last saved sample and of the best one.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = None
        self.setMinimumHeight(46)

    def set_levels(self, num_levels, last=None, best=None, posterior=None):
        self.state = (num_levels, last, best, posterior) if num_levels > 1 \
            else None
        self.update()

    def paintEvent(self, event):
        if self.state is None:
            return
        num_levels, last, best, posterior = self.state
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        margin = 6.0
        track = QRectF(margin, 9.0, self.width() - 2 * margin, 6.0)

        def at(level):
            return track.left() + track.width() * min(
                max(level / float(num_levels - 1), 0.0), 1.0)

        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E5E9EF"))
        p.drawRoundedRect(track, 3, 3)
        if posterior is not None:
            p.setBrush(QColor(theme.BAND_LINE))
            left = at(posterior[0])
            p.drawRoundedRect(QRectF(left, 6.0, max(at(posterior[1]) - left,
                                                    3.0), 12.0), 3, 3)
        for level, color in ((best, theme.INK), (last, theme.AMBER)):
            if level is not None:
                p.setBrush(QColor(color))
                p.drawRoundedRect(QRectF(at(level) - 2.0, 2.0, 4.0, 20.0),
                                  2, 2)
        p.setFont(theme.mono(8.5))
        p.setPen(QPen(QColor(theme.MUTED), 1))
        box = QRectF(margin, 26.0, track.width(), 16.0)
        p.drawText(box, Qt.AlignLeft | Qt.AlignVCenter, "0")
        p.drawText(box, Qt.AlignRight | Qt.AlignVCenter,
                   str(num_levels - 1))
        p.end()


class RunsScreen(Screen):
    """
    showResults(run) asks for the results of a run on «Результаты»;
    estimateWanted(run), for the estimate of a run opened from its folder
    that has none yet (main_window.replay_run).
    """

    showResults = Signal(object)
    estimateWanted = Signal(object)

    def __init__(self, queue, parent=None):
        super().__init__(S.SCREEN_RUNS, parent)
        self.queue = queue
        self.rows = []
        self.shown = None
        self._data_of = None
        # What the plots were last drawn from (_show_progress)
        self._drawn = None
        self.view = "mean"
        self.layers = {key: True for key, _ in LAYERS}
        self.set_header("", S.NO_RUNS)
        self.stop_button = self.add_button(S.STOP, queue.stop, S.STOP_TIP,
                                           kind="danger")
        self.stop_button.setEnabled(False)
        self.folder_button = self.add_button(S.OPEN_FOLDER, self.open_folder)
        self.folder_button.setEnabled(False)
        self.add_button(S.OPEN_RUNS, self.openRunsRequested, S.OPEN_RUNS_TIP)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(16)
        splitter.addWidget(self._make_queue())
        splitter.addWidget(self._make_live())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([480, 720])
        self.body.addWidget(splitter, 1)
        self._apply_layers()

        queue.changed.connect(self.update_run)
        queue.output.connect(self._output)

    # -------------------------------------------------------------- layout

    def _make_queue(self):
        queue_card, layout = card(S.QUEUE_TITLE, help="queue")
        self.hint = styled_label(S.NO_RUNS, "muted")
        layout.addWidget(self.hint)
        self.table = QTableWidget(0, len(COLUMNS))
        for i, (name, tip) in enumerate(zip(COLUMNS, S.RUNS_COLUMN_TIPS)):
            item = QTableWidgetItem(name)
            item.setToolTip(tooltip(tip))
            self.table.setHorizontalHeaderItem(i, item)
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
        outer.setContentsMargins(0, 0, 4, 0)
        outer.setSpacing(16)
        outer.addWidget(self._make_estimate())
        outer.addWidget(self._make_model())

        log_card, layout = card(S.LOG, help="log")
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log.setMaximumBlockCount(20000)
        self.log.setFont(theme.mono(9.0))
        self.log.setMinimumHeight(140)
        layout.addWidget(self.log, 1)
        outer.addWidget(log_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(column)
        return scroll

    def _make_estimate(self):
        estimate_card, layout = card(S.ESTIMATE_TITLE, help="estimate")
        row = QHBoxLayout()
        row.setSpacing(16)
        self.fraction_value = QLabel("—")
        self.fraction_value.setObjectName("liveFraction")
        self.fraction_value.setToolTip(tooltip(S.FRACTION_NOW_TIP))
        row.addWidget(self.fraction_value)
        self.fraction_intervals = QLabel()
        self.fraction_intervals.setObjectName("mono")
        self.fraction_intervals.setWordWrap(True)
        self.fraction_intervals.setToolTip(tooltip(S.INTERVALS_TIP))
        row.addWidget(self.fraction_intervals, 1, Qt.AlignBottom)
        self.settled = QLabel()
        self.settled.hide()
        row.addWidget(self.settled, 0, Qt.AlignTop)
        layout.addLayout(row)

        stats = QGridLayout()
        stats.setHorizontalSpacing(16)
        self.stat_values = []
        self.stat_captions = []
        tips = (S.STAT_SHIFT_TIP, helptext.short("ess"),
                helptext.short("log_z"))
        for i, caption in enumerate((S.STAT_SHIFT_NONE, S.STAT_ESS,
                                     S.STAT_LOG_Z)):
            value = QLabel("—")
            value.setObjectName("stat")
            value.setToolTip(tooltip(tips[i]))
            text = styled_label(caption, "muted")
            text.setToolTip(tooltip(tips[i]))
            stats.addWidget(value, 0, i)
            stats.addWidget(text, 1, i)
            stats.setColumnStretch(i, 1)
            self.stat_values.append(value)
            self.stat_captions.append(text)
        layout.addLayout(stats)

        legend = QLabel(theme.swatches([
            ("line", theme.ACCENT, S.LEGEND_MEDIAN),
            ("box", theme.BAND_LINE, S.LEGEND_50),
            ("box", theme.BAND, S.LEGEND_90),
            ("dash", theme.MUTED, S.LEGEND_LEVELS_DONE)]))
        legend.setTextFormat(Qt.RichText)
        legend.setObjectName("muted")
        layout.addWidget(legend)
        self.trace_plot = pg.PlotWidget()
        item = theme.style_plot(self.trace_plot, S.AXIS_SAVES)
        self.trace = {}
        for name in ("q05", "q25", "q50", "q75", "q95"):
            self.trace[name] = item.plot([], [], pen=pg.mkPen(
                theme.ACCENT, width=2) if name == "q50" else pg.mkPen(None))
        item.addItem(pg.FillBetweenItem(self.trace["q05"], self.trace["q95"],
                                        brush=_brush(theme.BAND, 255)))
        item.addItem(pg.FillBetweenItem(self.trace["q25"], self.trace["q75"],
                                        brush=_brush(theme.BAND_LINE, 220)))
        self.trace["q50"].setZValue(10)
        self.levels_done = pg.InfiniteLine(angle=90, pen=pg.mkPen(
            theme.MUTED, width=1, style=Qt.DashLine))
        self.levels_done.hide()
        item.addItem(self.levels_done)
        self.trace_plot.setMinimumHeight(170)
        self._empty_trace_range()
        layout.addWidget(self.trace_plot)
        self.estimate_note = styled_label(S.ESTIMATE_WAITING, "muted")
        layout.addWidget(self.estimate_note)
        return estimate_card

    def _make_model(self):
        model_card, layout = card()
        top = title_row(S.MODEL_TITLE, "model_views")
        top.addStretch(1)
        self.view_buttons = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        segments = QHBoxLayout()
        segments.setSpacing(0)
        for key, label in VIEWS:
            button = QPushButton(label)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setChecked(key == self.view)
            button.setToolTip(tooltip(S.VIEW_TIPS[key]))
            button.clicked.connect(lambda checked, k=key: self.set_view(k))
            group.addButton(button)
            segments.addWidget(button)
            self.view_buttons[key] = button
        top.addLayout(segments)
        layout.addLayout(top)

        chips = QHBoxLayout()
        chips.setSpacing(8)
        self.layer_buttons = {}
        for key, label in LAYERS:
            button = QPushButton(label)
            button.setObjectName("chip")
            button.setCheckable(True)
            button.setChecked(True)
            button.setToolTip(tooltip(S.LAYER_TIPS[key] + ". " +
                                       S.LAYER_SWITCH))
            button.toggled.connect(
                lambda on, k=key: self.set_layer(k, on))
            chips.addWidget(button)
            self.layer_buttons[key] = button
        chips.addWidget(HelpButton("layers"), 0, Qt.AlignVCenter)
        chips.addStretch(1)
        layout.addLayout(chips)

        self.model_plot = pg.PlotWidget()
        item = theme.style_plot(self.model_plot, S.AXIS_X, S.AXIS_Y)
        self.helpers = {name: _hidden() for name in
                        ("lo", "hi", "bg", "halo", "model")}
        for helper in self.helpers.values():
            item.addItem(helper)
        self.fills = {
            "band": pg.FillBetweenItem(self.helpers["lo"], self.helpers["hi"],
                                       brush=_brush(theme.BAND, 255)),
            "halo": pg.FillBetweenItem(self.helpers["bg"],
                                       self.helpers["halo"],
                                       brush=_brush(theme.WIDE_FILL, 190)),
            "xtal": pg.FillBetweenItem(self.helpers["halo"],
                                       self.helpers["model"],
                                       brush=_brush(theme.NARROW_FILL, 150)),
        }
        for fill in self.fills.values():
            item.addItem(fill)
        self.lines = {
            "bg": item.plot([], [], pen=pg.mkPen(theme.BACKGROUND, width=1.4,
                                                 style=Qt.DashLine)),
            "halo": item.plot([], [], pen=pg.mkPen(theme.WIDE, width=1.6)),
            "data": item.plot([], [], pen=None, symbol="o", symbolSize=3,
                              symbolPen=None,
                              symbolBrush=pg.mkBrush(theme.DATA_LIGHT)),
            "model": item.plot([], [], pen=pg.mkPen(theme.INK, width=1.8)),
        }
        self.model_plot.setMinimumHeight(260)
        layout.addWidget(self.model_plot)
        self.view_text = styled_label("", "muted")
        layout.addWidget(self.view_text)
        self.view_banner = Banner()
        layout.addWidget(self.view_banner)

        levels_row = QHBoxLayout()
        levels_row.setSpacing(6)
        self.levels_text = styled_label(S.LEVELS_TITLE, "muted")
        levels_row.addWidget(self.levels_text)
        levels_row.addWidget(HelpButton("levels"), 0, Qt.AlignVCenter)
        levels_row.addStretch(1)
        layout.addLayout(levels_row)
        self.gauge = LevelGauge()
        self.gauge.setToolTip(tooltip(helptext.short("levels")))
        layout.addWidget(self.gauge)
        self.gauge_legend = QLabel()
        self.gauge_legend.setTextFormat(Qt.RichText)
        self.gauge_legend.setObjectName("muted")
        layout.addWidget(self.gauge_legend)
        return model_card

    # ---------------------------------------------------------------- rows

    def update_run(self, run):
        if run not in self.rows:
            self.rows.append(run)
            self.table.insertRow(self.table.rowCount())
            self.hint.hide()
            self.set_header("", S.RUNS_HEADER.format(len(self.rows)))
        i = self.rows.index(run)
        planned = str(run.planned) if run.planned else "∞"
        # A run opened from its folder has no time of its own here
        elapsed = R.format_time(run.elapsed()) if run.started is not None \
            else "—"
        seed = "—" if run.seed is None else str(run.seed)
        cells = [run.name, seed, R.STATUS_TEXT[run.status],
                 "{0} / {1}".format(run.saves, planned), str(run.levels),
                 elapsed]
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
        if run.opened and run.estimate is None:
            self.estimateWanted.emit(run)

    def show_run(self, run):
        """
        Choose run in the table.
        """
        if run in self.rows:
            self.table.selectRow(self.rows.index(run))

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
        # The plots are redrawn only when what they show has changed: the
        # estimate, or the last sample while there is no estimate. A poll
        # that brought no new estimate leaves them, which spares a slow
        # computer the drawing
        drawn = (run, run.status, run.planned, run.estimate,
                 run.sample if run.estimate is None else None)
        if self._drawn is not None and all(
                a is b for a, b in zip(drawn, self._drawn)):
            return
        self._drawn = drawn
        self._show_estimate(run)
        self._show_model(run)

    # ------------------------------------------------------ the estimate

    def _show_estimate(self, run):
        e = run.estimate
        q = None if e is None else e.get("quantiles")
        for curve in self.trace.values():
            curve.setData([], [])
        self.levels_done.hide()
        if q is None:
            self.fraction_value.setText("—")
            self.fraction_intervals.setText("")
            self.settled.hide()
            for value in self.stat_values:
                value.setText("—")
            self.stat_captions[0].setText(S.STAT_SHIFT_NONE)
            self.estimate_note.setText(
                S.ESTIMATE_REPLAYING if run.opened and e is None
                else S.ESTIMATE_WAITING)
            self._empty_trace_range(run.planned)
            return
        self.fraction_value.setText(S.FRACTION_NOW.format(q[2]))
        self.fraction_intervals.setText(S.FRACTION_NOW_INTERVALS.format(
            q[1], q[3], q[0], q[4]))
        self.settled.setText(S.SETTLED if e["settled"] else S.UNSETTLED)
        self.settled.setToolTip(tooltip(S.SETTLED_TIP if e["settled"]
                                        else S.UNSETTLED_TIP))
        self.settled.setObjectName("okBadge" if e["settled"]
                                   else "waitBadge")
        # The style sheet looks at the name only when the label is polished
        self.settled.style().unpolish(self.settled)
        self.settled.style().polish(self.settled)
        self.settled.show()
        if e["shift"] is None:
            self.stat_values[0].setText("—")
            self.stat_captions[0].setText(S.STAT_SHIFT_NONE)
        else:
            self.stat_values[0].setText("{0:.3f}".format(e["shift"]))
            self.stat_captions[0].setText(S.STAT_SHIFT.format(e["window"]))
        self.stat_values[1].setText("{0:.0f}".format(
            e["effective_sample_size"]))
        self.stat_values[2].setText("{0:.1f}".format(e["log_z"]))
        self.estimate_note.setText(S.ESTIMATE_NOTE)

        trace = e["trace"]
        for j, name in enumerate(("q05", "q25", "q50", "q75", "q95")):
            self.trace[name].setData(trace[:, 0], trace[:, j + 1])
        if e["levels_done_at"] is not None:
            self.levels_done.setValue(e["levels_done_at"])
            self.levels_done.show()
        item = self.trace_plot.getPlotItem()
        right = max(run.planned or 0, run.saves, int(trace[-1, 0]), 1)
        item.setXRange(0, right, padding=0.01)
        low = max(0.0, float(trace[:, 1].min()) - 0.05)
        high = min(1.0, float(trace[:, 5].max()) + 0.05)
        item.setYRange(low, high, padding=0.0)

    def _empty_trace_range(self, planned=0):
        # The fraction lies within 0 and 1, over the planned saves
        item = self.trace_plot.getPlotItem()
        item.setXRange(0, max(planned or 0, 1), padding=0.01)
        item.setYRange(0.0, 1.0, padding=0.0)

    # --------------------------------------------------------- the model

    def set_view(self, view):
        self.view = view
        self.view_buttons[view].setChecked(True)
        if self.shown is not None:
            self._show_model(self.shown)

    def set_layer(self, layer, on):
        self.layers[layer] = on
        if self.layer_buttons[layer].isChecked() != on:
            self.layer_buttons[layer].setChecked(on)
        self._apply_layers()

    def _apply_layers(self):
        mean = self.view == "mean"
        self.layer_buttons["band"].setVisible(mean)
        self.lines["data"].setVisible(self.layers["data"])
        self.lines["bg"].setVisible(self.layers["bg"])
        self.lines["halo"].setVisible(self.layers["halo"])
        self.fills["halo"].setVisible(self.layers["halo"])
        self.fills["xtal"].setVisible(self.layers["xtal"])
        self.lines["model"].setVisible(self.layers["model"])
        self.fills["band"].setVisible(mean and self.layers["band"])

    def _sample_of(self, run):
        """
        The curves the model plot shows for run, and what to say of them.
        """
        e = run.estimate
        if self.view == "mean":
            if e is None or "mean" not in e:
                return None, S.VIEW_MEAN_WAITING, None
            return e["mean"], S.VIEW_MEAN_TEXT.format(e["saves"]), None
        if e is None:
            # Before the first estimate, the last sample that a poll read
            if self.view == "last" and run.sample is not None:
                return run.sample, "", None
            return None, "", None
        s = e[self.view]
        values = dict(s, levels=max(e["num_levels"] - 1, 0))
        if self.view == "best":
            return s["curves"], S.VIEW_BEST_TEXT.format(**values), None
        text = S.VIEW_LAST_TEXT.format(**values)
        posterior = e.get("posterior_levels")
        if posterior is not None and s["level"] < posterior[0]:
            return s["curves"], None, text + S.VIEW_LAST_LOW.format(
                *posterior)
        return s["curves"], text, None

    def _show_model(self, run):
        x = run.x
        if x is None:
            return
        if self._data_of is not run:
            self.lines["data"].setData(x, run.y)
            self._data_of = run
            # The scale of the data: samples near the prior have peaks
            # thousands of times higher, which would hide the data
            item = self.model_plot.getPlotItem()
            item.setXRange(float(x[0]), float(x[-1]), padding=0.01)
            item.setYRange(min(0.0, float(run.y.min())),
                           float(run.y.max()) * 1.25, padding=0.0)
        curves, text, warning = self._sample_of(run)
        empty = np.array([])
        if curves is None or curves.get("model_curve") is None \
                or len(curves["model_curve"]) != x.size:
            for name in ("bg", "halo", "model"):
                self.helpers[name].setData(empty, empty)
                self.lines[name].setData(empty, empty)
        else:
            bg = np.asarray(curves["bg"], dtype=float)
            halo = bg + np.asarray(curves["wide"], dtype=float)
            model = np.asarray(curves["model_curve"], dtype=float)
            for name, values in (("bg", bg), ("halo", halo),
                                 ("model", model)):
                self.helpers[name].setData(x, values)
                self.lines[name].setData(x, values)
        e = run.estimate
        band = None if (e is None or self.view != "mean") else e.get("band")
        if band is None:
            self.helpers["lo"].setData(empty, empty)
            self.helpers["hi"].setData(empty, empty)
        else:
            self.helpers["lo"].setData(x, band[0])
            self.helpers["hi"].setData(x, band[1])
        self.lines["model"].setPen(pg.mkPen(
            theme.AMBER if self.view == "last" else theme.INK, width=1.8))
        self._apply_layers()

        self.view_text.setText(text or "")
        self.view_text.setVisible(bool(text))
        if warning:
            self.view_banner.show_message(warning, "warning")
        else:
            self.view_banner.hide()
        self._show_levels(e)

    def _show_levels(self, e):
        if e is None or e["num_levels"] < 2:
            self.gauge.set_levels(0)
            self.levels_text.setText(S.LEVELS_TITLE)
            self.gauge_legend.setText("")
            return
        posterior = e.get("posterior_levels")
        self.gauge.set_levels(e["num_levels"], e["last"]["level"],
                              e["best"]["level"], posterior)
        items = [("line", theme.AMBER, S.GAUGE_LAST.format(
            e["last"]["level"]))]
        if posterior is not None:
            items.append(("box", theme.BAND_LINE,
                          S.GAUGE_WEIGHT.format(*posterior)))
            self.levels_text.setText(S.LEVELS_TITLE + " · "
                                     + S.LEVELS_POSTERIOR.format(*posterior))
        else:
            self.levels_text.setText(S.LEVELS_TITLE)
        items.append(("line", theme.INK, S.GAUGE_BEST.format(
            e["best"]["level"])))
        self.gauge_legend.setText(theme.swatches(items))

    def open_folder(self):
        if self.shown is not None and os.path.isdir(self.shown.folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.shown.folder))
