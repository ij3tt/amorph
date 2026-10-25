"""
The screen «Данные и модель»: open a data file, choose the range to
analyse and the background control points on the plot, fill in the
settings of config.yaml, and start the runs once the checks pass.
"""

import os

import pyqtgraph as pg
from PySide6.QtCore import QLocale, QRegularExpression, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QRegularExpressionValidator
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog,
                               QFormLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QVBoxLayout, QWidget)

import amorph_stats

from amorph_gui import config
from amorph_gui import strings as S
from amorph_gui.widgets import COLORS, Banner, Screen, bold

# Colours of the plot
DATA_PEN = (55, 71, 79)
RANGE_COLOR = (25, 118, 210)
CP_COLOR = (183, 28, 28)
BAND_COLOR = (239, 108, 0)


class NumberBox(QDoubleSpinBox):
    """
    A number with up to six decimals, shown without trailing zeros, with a
    decimal point whatever the language of the system, as in config.yaml.
    """

    def __init__(self, low, high, step, parent=None):
        super().__init__(parent)
        self.setLocale(QLocale.c())
        self.setDecimals(6)
        self.setRange(low, high)
        self.setSingleStep(step)
        self.setKeyboardTracking(False)

    def textFromValue(self, value):
        text = "{0:.6f}".format(value).rstrip("0").rstrip(".")
        return "0" if text in ("", "-0") else text


def _count_box(low, high):
    box = QSpinBox()
    box.setRange(low, high)
    box.setKeyboardTracking(False)
    return box


def _pair_row(first, second):
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(first, 1)
    layout.addWidget(QLabel(S.TO))
    layout.addWidget(second, 1)
    return row


class DataScreen(Screen):
    """
    runRequested(settings, data path, x, y, text of the options file) asks
    the main window to start the runs.
    """

    runRequested = Signal(object, str, object, object, str)

    def __init__(self, parent=None):
        super().__init__(S.SCREEN_DATA, parent)
        self.data_path = None
        self.x = None
        self.y = None
        self.data_file = config.Settings().data_file
        self.templates = config.options_templates()
        self.problems = []
        self._syncing = False
        self.last_dir = None

        self.add_button(S.OPEN_DATA, self.open_data_dialog)
        self.add_button(S.LOAD_CONFIG, self.load_config_dialog)
        self.add_button(S.SAVE_CONFIG_BUTTON, self.save_config_dialog)

        splitter = QSplitter(Qt.Horizontal)
        self.body.addWidget(splitter, 1)
        splitter.addWidget(self._make_plot())
        splitter.addWidget(self._make_form())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([740, 500])

        self.set_settings(config.default_settings())

    # ------------------------------------------------------------ layout

    def _make_plot(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        self.banner = Banner()
        layout.addWidget(self.banner)
        self.info = QLabel(S.NO_DATA)
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        self.plot = pg.PlotWidget(background="w")
        item = self.plot.getPlotItem()
        item.setLabel("bottom", S.AXIS_X)
        item.setLabel("left", S.AXIS_Y)
        item.showGrid(x=True, y=True, alpha=0.15)
        self.curve = item.plot([], [], pen=pg.mkPen(DATA_PEN, width=1))

        self.band = pg.LinearRegionItem(
            values=(0.0, 1.0), movable=False,
            brush=QBrush(QColor(*BAND_COLOR, 110), Qt.BDiagPattern),
            pen=pg.mkPen(BAND_COLOR, width=1, style=Qt.DashLine))
        self.band.setZValue(-5)
        self.region = pg.LinearRegionItem(
            values=(0.0, 1.0), brush=pg.mkBrush(RANGE_COLOR + (28,)),
            hoverBrush=pg.mkBrush(RANGE_COLOR + (45,)),
            pen=pg.mkPen(RANGE_COLOR, width=2))
        self.region.setZValue(-10)
        self.cp_lines = []
        for label in (S.LABEL_CP1, S.LABEL_CP2):
            line = pg.InfiniteLine(
                pos=0.0, angle=90, movable=True,
                pen=pg.mkPen(CP_COLOR, width=2, style=Qt.DashLine),
                hoverPen=pg.mkPen(CP_COLOR, width=4), label=label,
                labelOpts={"position": 0.92, "color": CP_COLOR,
                           "fill": (255, 255, 255, 200)})
            self.cp_lines.append(line)
        for thing in [self.band, self.region] + self.cp_lines:
            thing.setVisible(False)
            item.addItem(thing)
        self.region.sigRegionChanged.connect(self._region_moved)
        for line in self.cp_lines:
            line.sigPositionChanged.connect(self._cp_moved)
        layout.addWidget(self.plot, 1)

        def swatch(color, mark, text):
            return '<span style="color: rgb({0},{1},{2})"><b>{3}</b></span> ' \
                '{4}'.format(color[0], color[1], color[2], mark, text)
        legend = QLabel("&nbsp;&nbsp;&nbsp;&nbsp;".join([
            swatch(DATA_PEN, "━", S.LEGEND_DATA),
            swatch(RANGE_COLOR, "▮", S.LEGEND_RANGE),
            swatch(CP_COLOR, "┆", S.LEGEND_CP),
            swatch(BAND_COLOR, "▨", S.LEGEND_BAND)]))
        legend.setTextFormat(Qt.RichText)
        layout.addWidget(legend)
        return panel

    def _make_form(self):
        form_panel = QWidget()
        outer = QVBoxLayout(form_panel)
        outer.setContentsMargins(8, 0, 0, 0)

        self.range_lo = NumberBox(-1E9, 1E9, 0.5)
        self.range_hi = NumberBox(-1E9, 1E9, 0.5)
        self.cp1 = NumberBox(-1E9, 1E9, 0.5)
        self.cp2 = NumberBox(-1E9, 1E9, 0.5)
        self.left_edge = NumberBox(0.0, 1.0, 0.05)
        self.right_edge = NumberBox(0.0, 1.0, 0.05)
        self.narrow = _count_box(1, 1000000)
        self.wide = _count_box(1, 1000000)
        self.nu_lo = NumberBox(config.NU_LIMITS[0], config.NU_LIMITS[1], 0.1)
        self.nu_hi = NumberBox(config.NU_LIMITS[0], config.NU_LIMITS[1], 1.0)
        self.threads = _count_box(1, 4096)
        self.options = QComboBox()
        self.max_saves = _count_box(0, 2000000000)
        self.max_saves.setSpecialValueText(S.UNLIMITED)
        self.seed = QLineEdit()
        self.seed.setPlaceholderText(S.SEED_PLACEHOLDER)
        self.seed.setValidator(QRegularExpressionValidator(
            QRegularExpression("[0-9]{0,10}"), self.seed))
        self.num_seeds = _count_box(1, 1000)

        def group(title, rows):
            box = QGroupBox(title)
            layout = QFormLayout(box)
            layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
            for label, key, field, tip in rows:
                # The key of config.yaml under the label
                text = QLabel(label if key is None else
                              '{0}<br><span style="color: #607d8b">{1}'
                              '</span>'.format(label, key))
                text.setTextFormat(Qt.RichText)
                if tip:
                    text.setToolTip(tip)
                    field.setToolTip(tip)
                layout.addRow(text, field)
            return box

        scroll_body = QWidget()
        groups = QVBoxLayout(scroll_body)
        groups.setContentsMargins(0, 0, 4, 0)
        groups.addWidget(group(S.GROUP_RANGE, [
            (S.FIELD_RANGE, None, _pair_row(self.range_lo, self.range_hi),
             S.FIELD_RANGE_TIP),
            (S.FIELD_CONTROL_POINTS, "control_points",
             _pair_row(self.cp1, self.cp2), S.FIELD_CONTROL_POINTS_TIP),
            (S.FIELD_EDGES, "left_edge, right_edge",
             _pair_row(self.left_edge, self.right_edge), S.FIELD_EDGES_TIP)]))
        groups.addWidget(group(S.GROUP_PEAKS, [
            (S.FIELD_NARROW, "max_num_narrow_peaks", self.narrow,
             S.FIELD_NARROW_TIP),
            (S.FIELD_WIDE, "max_num_wide_peaks", self.wide, None),
            (S.FIELD_NU, "narrow_peak_nu", _pair_row(self.nu_lo, self.nu_hi),
             S.FIELD_NU_TIP)]))
        groups.addWidget(group(S.GROUP_SAMPLER, [
            (S.FIELD_THREADS, "num_threads", self.threads, None),
            (S.FIELD_OPTIONS, "dnest4_options_file", self.options,
             S.FIELD_OPTIONS_TIP),
            (S.FIELD_MAX_SAVES, S.FIELD_MAX_SAVES_KEY, self.max_saves,
             S.FIELD_MAX_SAVES_TIP),
            (S.FIELD_SEED, "seed", self.seed, S.FIELD_SEED_TIP),
            (S.FIELD_NUM_SEEDS, None, self.num_seeds,
             S.FIELD_NUM_SEEDS_TIP)]))
        groups.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(scroll_body)
        form_panel.setMinimumWidth(scroll_body.minimumSizeHint().width() + 24)
        outer.addWidget(scroll, 1)

        outer.addWidget(bold(QLabel(S.CHECKS)))
        self.checks = QLabel()
        self.checks.setWordWrap(True)
        self.checks.setTextFormat(Qt.RichText)
        outer.addWidget(self.checks)
        self.run_button = QPushButton(S.RUN)
        self.run_button.setMinimumHeight(36)
        bold(self.run_button)
        self.run_button.clicked.connect(self.request_run)
        outer.addWidget(self.run_button)

        for box in (self.range_lo, self.range_hi, self.cp1, self.cp2,
                    self.left_edge, self.right_edge, self.nu_lo, self.nu_hi):
            box.valueChanged.connect(self._form_changed)
        for box in (self.narrow, self.wide, self.threads, self.max_saves,
                    self.num_seeds):
            box.valueChanged.connect(self._form_changed)
        self.seed.textChanged.connect(self._form_changed)
        self.options.currentTextChanged.connect(self._options_changed)
        self._fill_options()
        return form_panel

    def add_options(self, name, text):
        """
        Offer another DNest4 options file, or replace the text of one.
        """
        self.templates[name] = text
        self._fill_options()

    def _fill_options(self):
        current = self.options.currentText()
        self._syncing = True
        self.options.clear()
        names = [n for n in config.OPTIONS_FILES if n in self.templates]
        names += sorted(n for n in self.templates if n not in names)
        self.options.addItems(names)
        if current in names:
            self.options.setCurrentText(current)
        self._syncing = False

    # ---------------------------------------------------------- settings

    def settings(self):
        """
        The settings in the form.
        """
        seed = self.seed.text().strip()
        x_range = None
        if self.x is not None:
            lo, hi = self.range_lo.value(), self.range_hi.value()
            if lo > self.x[0] or hi < self.x[-1]:
                x_range = (lo, hi)
        return config.Settings(
            num_threads=self.threads.value(), data_file=self.data_file,
            dnest4_options_file=self.options.currentText(),
            seed=int(seed) if seed else None,
            control_points=(self.cp1.value(), self.cp2.value()),
            max_num_narrow_peaks=self.narrow.value(),
            max_num_wide_peaks=self.wide.value(),
            left_edge=self.left_edge.value(),
            right_edge=self.right_edge.value(),
            narrow_peak_nu=(self.nu_lo.value(), self.nu_hi.value()),
            max_saves=self.max_saves.value(),
            num_seeds=self.num_seeds.value(), x_range=x_range)

    def set_settings(self, s):
        """
        Put the settings into the form. The range of x is that of the data
        unless s.x_range gives one.
        """
        self._syncing = True
        try:
            self.data_file = s.data_file
            self.threads.setValue(s.num_threads)
            # An options file the form has no text of is never chosen:
            # load_config adds the one next to config.yaml first
            if s.dnest4_options_file in self.templates:
                self.options.setCurrentText(s.dnest4_options_file)
            self.max_saves.setValue(s.max_saves)
            self.seed.setText("" if s.seed is None else str(s.seed))
            self.num_seeds.setValue(s.num_seeds)
            self.cp1.setValue(s.control_points[0])
            self.cp2.setValue(s.control_points[1])
            self.narrow.setValue(s.max_num_narrow_peaks)
            self.wide.setValue(s.max_num_wide_peaks)
            self.left_edge.setValue(s.left_edge)
            self.right_edge.setValue(s.right_edge)
            self.nu_lo.setValue(s.narrow_peak_nu[0])
            self.nu_hi.setValue(s.narrow_peak_nu[1])
            if self.x is not None:
                lo, hi = s.x_range if s.x_range is not None \
                    else (self.x[0], self.x[-1])
                self.range_lo.setValue(float(lo))
                self.range_hi.setValue(float(hi))
        finally:
            self._syncing = False
        self._update()

    def _options_changed(self, name):
        if self._syncing or name not in self.templates:
            return
        try:
            self.max_saves.setValue(config.options_max_saves(
                self.templates[name]))
        except (IndexError, ValueError):
            pass
        self._update()

    # -------------------------------------------------------------- data

    def open_data_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, S.CHOOSE_DATA,
                                              self.last_dir or "",
                                              S.FILTER_DATA)
        if path:
            self.open_data(path)

    def open_data(self, path):
        """
        Read a data file with the rules of the sampler and show it; on an
        error show the message of amorph_stats.load_data, with the file and
        the line. Returns whether it worked.
        """
        try:
            x, y = amorph_stats.load_data(path)
        except (OSError, ValueError) as e:
            self.banner.show_message(S.CANNOT_READ_DATA + ":\n" + str(e))
            return False
        self.banner.hide()
        self.data_path = os.path.abspath(path)
        self.last_dir = os.path.dirname(self.data_path)
        self.data_file = os.path.basename(path)
        self.x, self.y = x, y
        self.curve.setData(x, y)
        lo, hi = float(x[0]), float(x[-1])
        self._syncing = True
        try:
            self.range_lo.setRange(lo, hi)
            self.range_hi.setRange(lo, hi)
            self.range_lo.setValue(lo)
            self.range_hi.setValue(hi)
            self.region.setBounds((lo, hi))
        finally:
            self._syncing = False
        for thing in [self.band, self.region] + self.cp_lines:
            thing.setVisible(True)
        self._update()
        self._show_all()
        return True

    def _show_all(self):
        # The data and the control points, which may lie outside them
        lo = min(self.x[0], self.cp1.value())
        hi = max(self.x[-1], self.cp2.value())
        self.plot.getPlotItem().setXRange(lo, hi, padding=0.03)
        self.plot.getPlotItem().enableAutoRange(axis="y")

    # ---------------------------------------------------- config.yaml

    def load_config_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, S.CHOOSE_CONFIG,
                                              self.last_dir or "",
                                              S.FILTER_CONFIG)
        if path:
            self.load_config(path)

    def load_config(self, path):
        """
        Put the settings of a config.yaml into the form, and open its data
        file if it is next to it. Returns whether it worked.
        """
        try:
            settings, options = config.read_config(path)
        except (OSError, config.ConfigError) as e:
            self.banner.show_message(S.CANNOT_READ_CONFIG + ":\n" + str(e))
            return False
        name = settings.dnest4_options_file
        if options is not None:
            self.add_options(name, options)
        elif name not in self.templates:
            self.banner.show_message(S.CANNOT_READ_CONFIG + ":\n"
                                     + S.CONFIG_OPTIONS.format(
                                         os.path.basename(path), name,
                                         ", ".join(sorted(self.templates))))
            return False
        else:
            settings.max_saves = config.options_max_saves(
                self.templates[name])
        self.banner.hide()
        folder = os.path.dirname(os.path.abspath(path))
        self.last_dir = folder
        data = os.path.join(folder, settings.data_file)
        if os.path.isfile(data):
            self.open_data(data)
        self.set_settings(settings)
        if self.x is not None:
            self._show_all()
        return True

    def save_config_dialog(self):
        path, _ = QFileDialog.getSaveFileName(
            self, S.SAVE_CONFIG,
            os.path.join(self.last_dir or "", "config.yaml"), S.FILTER_CONFIG)
        if path:
            try:
                self.save_config(path)
            except OSError as e:
                self.report_error(S.ERROR, S.CANNOT_SAVE.format(path) + "\n"
                                  + str(e))

    def save_config(self, path):
        config.write_config(self.settings(), path)

    # ----------------------------------------------- plot <-> form

    def _region_moved(self):
        if self._syncing:
            return
        lo, hi = self.region.getRegion()
        self._syncing = True
        try:
            self.range_lo.setValue(lo)
            self.range_hi.setValue(hi)
        finally:
            self._syncing = False
        self._update(move_items=False)

    def _cp_moved(self):
        if self._syncing:
            return
        a, b = (line.value() for line in self.cp_lines)
        self._syncing = True
        try:
            self.cp1.setValue(a)
            self.cp2.setValue(b)
        finally:
            self._syncing = False
        self._update(move_items=False)

    def _form_changed(self, *args):
        if not self._syncing:
            self._update()

    def _update(self, move_items=True):
        """
        Move the plot to the form, and check the settings.
        """
        s = self.settings()
        if self.x is not None:
            keep = config.selected(self.x, s.x_range)
            self._syncing = True
            try:
                if move_items:
                    self.region.setRegion((self.range_lo.value(),
                                           self.range_hi.value()))
                    self.cp_lines[0].setValue(s.control_points[0])
                    self.cp_lines[1].setValue(s.control_points[1])
                if keep.sum() >= 2 and s.left_edge < s.right_edge:
                    self.band.setRegion(config.wide_band(
                        self.x[keep], s.left_edge, s.right_edge))
            finally:
                self._syncing = False
            self.info.setText(S.DATA_INFO.format(
                name=self.data_file, n=self.x.size, lo=self.x[0],
                hi=self.x[-1], m=int(keep.sum())))
        self.problems = config.check(s, self.x)
        self._show_checks()

    def _show_checks(self):
        errors = [t for level, t in self.problems if level == config.ERROR]
        if not self.problems:
            fg, bg = COLORS["ok"]
            html = '<p style="color:{0}">✔ {1}</p>'.format(fg, S.CHECKS_OK)
        else:
            parts = []
            for level, text in self.problems:
                fg, _ = COLORS[level]
                mark = "✖" if level == config.ERROR else "▲"
                parts.append('<p style="color:{0}; margin: 2px 0">{1} {2}'
                             '</p>'.format(fg, mark, text))
            html = "".join(parts)
        self.checks.setText(html)
        self.run_button.setEnabled(not errors)
        self.run_button.setToolTip(S.RUN_BLOCKED_TIP if errors else S.RUN_TIP)

    def errors(self):
        return [t for level, t in self.problems if level == config.ERROR]

    def warnings(self):
        return [t for level, t in self.problems if level == config.WARNING]

    # --------------------------------------------------------------- run

    def request_run(self):
        self._update(move_items=False)
        if self.errors():
            return
        s = self.settings()
        self.runRequested.emit(s, self.data_path, self.x, self.y,
                               self.templates[s.dnest4_options_file])
