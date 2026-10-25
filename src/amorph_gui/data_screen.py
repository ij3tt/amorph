"""
The screen «Данные и модель»: open a data file, choose the range to
analyse and the background control points on the plot, fill in the
settings of config.yaml, and start the runs once the checks pass.
"""

import os

import pyqtgraph as pg
from PySide6.QtCore import QLocale, QRegularExpression, Qt, Signal
from PySide6.QtGui import QBrush, QRegularExpressionValidator
from PySide6.QtWidgets import (QComboBox, QDoubleSpinBox, QFileDialog,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QSpinBox, QSplitter,
                               QVBoxLayout, QWidget)

import amorph_stats

from amorph_gui import config
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.widgets import Banner, Screen, card, styled_label


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
        self.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)

    def textFromValue(self, value):
        text = "{0:.6f}".format(value).rstrip("0").rstrip(".")
        return "0" if text in ("", "-0") else text


def _count_box(low, high):
    box = QSpinBox()
    box.setRange(low, high)
    box.setKeyboardTracking(False)
    box.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
    return box


def _fieldset(legend, cells, note=None):
    """
    A group of fields as the design draws them: a small legend in capitals,
    then the fields in two columns, each under its label. cells holds
    (label, field, tip, key of config.yaml, columns it spans).
    """
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(styled_label(legend, "legend", wrap=False))
    grid = QGridLayout()
    grid.setHorizontalSpacing(10)
    grid.setVerticalSpacing(8)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    row = column = 0
    for label, field, tip, key, span in cells:
        cell = QWidget()
        cell_layout = QVBoxLayout(cell)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        cell_layout.setSpacing(3)
        text = styled_label(label, "fieldLabel", wrap=False)
        cell_layout.addWidget(text)
        cell_layout.addWidget(field)
        parts = [t for t in (tip, S.CONFIG_KEY.format(key) if key else None)
                 if t]
        if parts:
            text.setToolTip("\n".join(parts))
            field.setToolTip("\n".join(parts))
        if column + span > 2:
            row, column = row + 1, 0
        grid.addWidget(cell, row, column, 1, span)
        column += span
        if column >= 2:
            row, column = row + 1, 0
    layout.addLayout(grid)
    if note:
        layout.addWidget(styled_label(note, "muted"))
    return box


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
        self.set_header("", S.NO_DATA)

        self.add_button(S.OPEN_DATA, self.open_data_dialog)
        self.add_button(S.LOAD_CONFIG, self.load_config_dialog)
        self.add_button(S.SAVE_CONFIG_BUTTON, self.save_config_dialog)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(16)
        self.body.addWidget(splitter, 1)
        splitter.addWidget(self._make_plot())
        splitter.addWidget(self._make_form())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([820, 380])

        self.set_settings(config.default_settings())

    # ------------------------------------------------------------ layout

    def _make_plot(self):
        column = QWidget()
        outer = QVBoxLayout(column)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(16)

        legend = QLabel(theme.swatches([
            ("line", theme.DATA, S.LEGEND_DATA),
            ("dash", theme.AMBER, S.LEGEND_BACKGROUND_PREVIEW),
            ("line", theme.ACCENT, S.LEGEND_RANGE),
            ("box", theme.BAND_LINE, S.LEGEND_BAND)]))
        legend.setTextFormat(Qt.RichText)
        legend.setObjectName("muted")
        plot_card, layout = card(S.PLOT_TITLE)
        layout.addWidget(legend)
        self.banner = Banner()
        layout.addWidget(self.banner)

        self.plot = pg.PlotWidget()
        item = theme.style_plot(self.plot, S.AXIS_X, S.AXIS_Y)
        self.curve = item.plot([], [], pen=pg.mkPen(theme.DATA, width=1.1))
        self.background = item.plot([], [], pen=pg.mkPen(
            theme.AMBER, width=2, style=Qt.DashLine))

        # The parts of the data left out of the analysis, shaded grey
        self.outside = [pg.LinearRegionItem(
            values=(0.0, 1.0), movable=False,
            brush=pg.mkBrush(theme.qcolor(theme.OUTSIDE, 70)),
            pen=pg.mkPen(None)) for _ in range(2)]
        # Where the wide peaks may be: a band along the bottom
        self.band = pg.LinearRegionItem(
            values=(0.0, 1.0), movable=False, span=(0.0, 0.07),
            brush=pg.mkBrush(theme.BAND),
            pen=pg.mkPen(theme.BAND_LINE, width=1))
        self.band.setZValue(-5)
        self.region = pg.LinearRegionItem(
            values=(0.0, 1.0), brush=QBrush(Qt.NoBrush),
            hoverBrush=pg.mkBrush(theme.qcolor(theme.ACCENT, 18)),
            pen=pg.mkPen(theme.ACCENT, width=2.5),
            hoverPen=pg.mkPen(theme.ACCENT, width=4))
        self.region.setZValue(-10)
        self.cp_lines = []
        for label in (S.LABEL_CP1, S.LABEL_CP2):
            line = pg.InfiniteLine(
                pos=0.0, angle=90, movable=True,
                pen=pg.mkPen(theme.AMBER, width=2),
                hoverPen=pg.mkPen(theme.AMBER, width=4), label=label,
                labelOpts={"position": 0.9, "color": theme.AMBER_TEXT,
                           "fill": pg.mkBrush(theme.SURFACE),
                           "border": pg.mkPen(theme.AMBER)})
            self.cp_lines.append(line)
        self.plot_items = self.outside + [self.band, self.region] \
            + self.cp_lines
        for thing in self.plot_items:
            thing.setVisible(False)
            item.addItem(thing)
        self.region.sigRegionChanged.connect(self._region_moved)
        for line in self.cp_lines:
            line.sigPositionChanged.connect(self._cp_moved)
        self.plot.setMinimumHeight(320)
        layout.addWidget(self.plot, 1)
        layout.addWidget(styled_label(S.PLOT_HINT, "muted"))
        outer.addWidget(plot_card, 1)

        checks_card, layout = card(S.CHECKS_TITLE)
        self.checks = QLabel()
        self.checks.setWordWrap(True)
        self.checks.setTextFormat(Qt.RichText)
        layout.addWidget(self.checks)
        outer.addWidget(checks_card)
        return column

    def _make_form(self):
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

        settings_card, layout = card(S.SETTINGS_TITLE, spacing=18)
        layout.addWidget(_fieldset(S.LEGEND_RANGE_GROUP, [
            (S.F_RANGE_LO, self.range_lo, S.FIELD_RANGE_TIP, None, 1),
            (S.F_RANGE_HI, self.range_hi, S.FIELD_RANGE_TIP, None, 1),
            (S.F_CP1, self.cp1, S.FIELD_CONTROL_POINTS_TIP, "control_points",
             1),
            (S.F_CP2, self.cp2, S.FIELD_CONTROL_POINTS_TIP, "control_points",
             1),
            (S.F_EDGE_LO, self.left_edge, S.FIELD_EDGES_TIP, "left_edge", 1),
            (S.F_EDGE_HI, self.right_edge, S.FIELD_EDGES_TIP, "right_edge",
             1)]))
        layout.addWidget(_fieldset(S.LEGEND_PEAKS_GROUP, [
            (S.F_NU_LO, self.nu_lo, S.FIELD_NU_TIP, "narrow_peak_nu", 1),
            (S.F_NU_HI, self.nu_hi, S.FIELD_NU_TIP, "narrow_peak_nu", 1),
            (S.F_NARROW, self.narrow, S.FIELD_NARROW_TIP,
             "max_num_narrow_peaks", 1),
            (S.F_WIDE, self.wide, None, "max_num_wide_peaks", 1)],
            note=S.NU_NOTE))
        layout.addWidget(_fieldset(S.LEGEND_SAMPLER_GROUP, [
            (S.F_OPTIONS, self.options, S.FIELD_OPTIONS_TIP,
             "dnest4_options_file", 2),
            (S.F_SAVES, self.max_saves, S.FIELD_MAX_SAVES_TIP, None, 1),
            (S.F_THREADS, self.threads, None, "num_threads", 1),
            (S.F_SEED, self.seed, S.FIELD_SEED_TIP, "seed", 1),
            (S.F_NUM_SEEDS, self.num_seeds, S.FIELD_NUM_SEEDS_TIP, None, 1)],
            note=S.SEEDS_NOTE))
        layout.addStretch(1)

        self.run_button = QPushButton(S.RUN)
        self.run_button.setObjectName("primary")
        self.run_button.clicked.connect(self.request_run)
        layout.addWidget(self.run_button)
        save_button = QPushButton(S.SAVE_CONFIG_BUTTON)
        save_button.clicked.connect(self.save_config_dialog)
        layout.addWidget(save_button)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(settings_card)
        scroll.setMinimumWidth(settings_card.minimumSizeHint().width() + 8)

        for box in (self.range_lo, self.range_hi, self.cp1, self.cp2,
                    self.left_edge, self.right_edge, self.nu_lo, self.nu_hi):
            box.valueChanged.connect(self._form_changed)
        for box in (self.narrow, self.wide, self.threads, self.max_saves,
                    self.num_seeds):
            box.valueChanged.connect(self._form_changed)
        self.seed.textChanged.connect(self._form_changed)
        self.options.currentTextChanged.connect(self._options_changed)
        self._fill_options()
        return scroll

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
        for thing in self.plot_items:
            thing.setVisible(True)
        self._update()
        self._show_all()
        return True

    def _show_all(self):
        # The data and the control points, which may lie outside them
        lo = min(self.x[0], self.cp1.value())
        hi = max(self.x[-1], self.cp2.value())
        item = self.plot.getPlotItem()
        item.setXRange(lo, hi, padding=0.03)
        # Room above the data for the labels of the control points
        item.setYRange(min(0.0, float(self.y.min())), float(self.y.max())
                       * 1.12, padding=0.0)

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
            lo, hi = self.range_lo.value(), self.range_hi.value()
            self._syncing = True
            try:
                if move_items:
                    self.region.setRegion((lo, hi))
                    self.cp_lines[0].setValue(s.control_points[0])
                    self.cp_lines[1].setValue(s.control_points[1])
                if keep.sum() >= 2 and s.left_edge < s.right_edge:
                    self.band.setRegion(config.wide_band(
                        self.x[keep], s.left_edge, s.right_edge))
            finally:
                self._syncing = False
            x0, x1 = float(self.x[0]), float(self.x[-1])
            for shade, (a, b) in zip(self.outside, ((x0, lo), (hi, x1))):
                shade.setRegion((a, b))
                shade.setVisible(b > a)
            preview = config.background_preview(self.x, self.y, s.x_range,
                                                s.control_points)
            if preview is None:
                self.background.setData([], [])
            else:
                self.background.setData(*preview)
            self.set_header(self.data_file, S.DATA_DETAILS.format(
                n=self.x.size, lo=self.x[0], hi=self.x[-1],
                m=int(keep.sum())))
        self.run_button.setText(S.run_button_text(s.num_seeds))
        self.problems = config.check(s, self.x)
        self._show_checks()

    def _show_checks(self):
        errors = [t for level, t in self.problems if level == config.ERROR]
        if not self.problems:
            html = ('<p style="color: {0}"><span style="font-weight: 600">'
                    '✔</span>&nbsp; {1}</p>'.format(theme.GREEN,
                                                     S.CHECKS_OK))
        else:
            parts = []
            for level, text in self.problems:
                fg, bg, _, icon = theme.LEVELS[level]
                mark = "✖" if level == config.ERROR else "▲"
                parts.append(
                    '<table width="100%" cellpadding="8" cellspacing="0" '
                    'style="background-color: {0}; margin-bottom: 6px">'
                    '<tr><td width="18" valign="top" style="color: {1}; '
                    'font-weight: 600">{2}</td><td style="color: {3}">{4}'
                    '</td></tr></table>'.format(bg, icon, mark, fg, text))
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
