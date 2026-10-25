"""
The screen «Результаты»: the results of one run, from its folder after the
post-processing or from an archive. The tabs show the fraction with its
intervals and the diagnostic cards, the figures of amorph_results.FIGURES
and the whole report; the header exports the figures, the archive and the
posterior samples.
"""

import os
import shutil

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QLabel,
                               QPlainTextEdit, QScrollArea, QTabWidget,
                               QVBoxLayout, QWidget)

import amorph_archive
import amorph_results

from amorph_gui import digest
from amorph_gui import strings as S
from amorph_gui.widgets import (COLORS, Card, FigureView, IntervalBar, Screen,
                                bold)

# The figures of each tab, by their names in amorph_results.FIGURES
MODEL_FIGURES = ["model", "residuals"]
DISTRIBUTION_FIGURES = ["narrow_peaks", "fraction", "center", "halfwidth",
                        "skewness", "nongaussianity"]
SAMPLER_FIGURES = ["levels", "compression", "likelihood"]


def _scroll(widget):
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QScrollArea.NoFrame)
    scroll.setWidget(widget)
    return scroll


def _note(text, level="info"):
    fg, bg = COLORS[level]
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet("QLabel {{ color: {0}; background: {1}; "
                        "border-radius: 4px; padding: 8px; }}".format(fg, bg))
    return label


class ResultsScreen(Screen):
    """
    message(text) reports what an export did, for the status bar.
    """

    message = Signal(str)

    def __init__(self, tasks, parent=None):
        super().__init__(S.SCREEN_RESULTS, parent)
        self.tasks = tasks
        self.results = None
        self.archive = None
        self.stopped = False
        self.figure_views = {}
        self._builders = {}

        self.export_buttons = [
            self.add_button(S.SAVE_ARCHIVE, self.save_archive,
                            S.SAVE_ARCHIVE_TIP),
            self.add_button(S.SAVE_POSTERIOR, self.save_posterior,
                            S.SAVE_POSTERIOR_TIP),
            self.add_button(S.SAVE_FIGURES, self.save_figures,
                            S.SAVE_FIGURES_TIP)]
        for button in self.export_buttons:
            button.setEnabled(False)

        self.subtitle = QLabel(S.NO_RESULTS)
        self.subtitle.setWordWrap(True)
        self.subtitle.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.body.addWidget(self.subtitle)
        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._build_tab)
        self.tabs.hide()
        self.body.addWidget(self.tabs, 1)

    def show_results(self, results, source, archive=None, stopped=False):
        """
        Show the results of a run. source says where they come from;
        archive is the run archive they are in, if there is one; stopped
        says that the GUI stopped the run.
        """
        self.results = results
        self.archive = archive
        self.stopped = stopped
        self.figure_views = {}
        seed = digest.run_config(results).get("seed")
        self.subtitle.setText(S.RESULTS_TITLE.format(
            data=results.info.get("data_file", S.UNKNOWN),
            seed=S.NO_SEED if seed is None else seed, source=source))
        for button in self.export_buttons:
            button.setEnabled(True)

        self.tabs.blockSignals(True)
        while self.tabs.count():
            page = self.tabs.widget(0)
            self.tabs.removeTab(0)
            page.deleteLater()
        self._builders = {}
        for title, build in ((S.TAB_SUMMARY, self._summary),
                             (S.TAB_MODEL, self._model),
                             (S.TAB_DISTRIBUTIONS, self._distributions),
                             (S.TAB_SAMPLER, self._sampler),
                             (S.TAB_REPORT, self._report)):
            page = QWidget()
            QVBoxLayout(page).setContentsMargins(0, 0, 0, 0)
            index = self.tabs.addTab(page, title)
            self._builders[index] = build
        self.tabs.setCurrentIndex(0)
        self.tabs.blockSignals(False)
        self.tabs.show()
        self._build_tab(0)

    def _build_tab(self, index):
        # The figures of a tab are drawn when it is first shown
        build = self._builders.pop(index, None)
        if build is not None:
            self.tabs.widget(index).layout().addWidget(build())

    # ----------------------------------------------------------------- tabs

    def _summary(self):
        r = self.results
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 12, 8)
        d = r.diagnosis
        if d is None:
            layout.addWidget(_note(S.NO_DIAGNOSIS, "warning"))
        else:
            f = d["fraction"]
            layout.addWidget(bold(QLabel(S.FRACTION_TITLE)))
            value = bold(QLabel("{0:.3f}".format(f["q50"])), 2.6)
            value.setObjectName("fraction")
            layout.addWidget(value)
            layout.addWidget(QLabel(S.FRACTION_INTERVALS.format(
                f["q25"], f["q75"], f["q05"], f["q95"])))
            bar = IntervalBar([f["q05"], f["q25"], f["q50"], f["q75"],
                               f["q95"]])
            bar.setMaximumWidth(560)
            layout.addWidget(bar)
            p = d.get("fraction_in_range")
            if p and p.get("range"):
                layout.addWidget(QLabel(S.FRACTION_IN_RANGE.format(
                    p["range"][0], p["range"][1], p["q50"], p["q25"],
                    p["q75"])))

        cards = digest.diagnostic_cards(r, self.stopped)
        if cards:
            grid = QGridLayout()
            grid.setSpacing(8)
            for i, (level, title, text) in enumerate(cards):
                grid.addWidget(Card(level, title, text), i // 2, i % 2)
            layout.addSpacing(8)
            layout.addLayout(grid)

        if d is not None:
            posterior = len(r.posterior) if r.posterior is not None else 0
            layout.addWidget(QLabel(S.ESS.format(
                d["effective_sample_size"], d["saves"], posterior)))
        layout.addWidget(self._settings_label())
        layout.addSpacing(8)
        layout.addWidget(_note(S.NOTE_FRACTION))
        layout.addWidget(_note(S.NOTE_SEEDS))
        layout.addStretch(1)
        return _scroll(page)

    def _settings_label(self):
        r = self.results
        c = digest.run_config(r)
        a = digest.assumptions(r)

        def pair(key, default=None):
            value = a.get(key, default)
            if isinstance(value, list) and len(value) == 2:
                return "[{0:g}, {1:g}]".format(value[0], value[1])
            return S.UNKNOWN

        info = r.info
        label = QLabel(S.SETTINGS_SUMMARY + ": " + S.SETTINGS_LINE.format(
            data=info.get("data_file", S.UNKNOWN),
            n=info.get("num_points", S.UNKNOWN),
            lo=info.get("x_min", float("nan")),
            hi=info.get("x_max", float("nan")),
            cp=pair("control_points"),
            edges="{0}–{1}".format(a.get("left_edge", S.UNKNOWN),
                                   a.get("right_edge", S.UNKNOWN)),
            caps="{0}/{1}".format(a.get("max_num_narrow_peaks", S.UNKNOWN),
                                  a.get("max_num_wide_peaks", S.UNKNOWN)),
            nu=pair("narrow_peak_nu", [0.1, 100.0]),
            options=c.get("dnest4_options_file", S.UNKNOWN)))
        label.setWordWrap(True)
        label.setStyleSheet("color: #455a64")
        return label

    def _figures(self, names, columns=1, size=(9.0, 4.6), before=None):
        r = self.results
        available = {name: (title, draw) for name, title, draw
                     in amorph_results.available_figures(r)}
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 8, 12, 8)
        if before is not None:
            layout.addWidget(before)
        grid = QGridLayout()
        grid.setSpacing(10)
        shown = 0
        for name in names:
            if name not in available:
                continue
            title, draw = available[name]
            view = FigureView(r, name, S.FIGURE_TITLES.get(name, title), draw,
                              size, self.report_error)
            self.figure_views[name] = view
            grid.addWidget(view, shown // columns, shown % columns)
            shown += 1
        layout.addLayout(grid)
        if shown == 0:
            layout.addWidget(QLabel(S.NO_FIGURES))
        layout.addStretch(1)
        return _scroll(page)

    def _model(self):
        return self._figures(MODEL_FIGURES)

    def _distributions(self):
        return self._figures(DISTRIBUTION_FIGURES, columns=2, size=(6.0, 3.8))

    def _sampler(self):
        s = self.results.sampler
        if s is None:
            numbers = _note(S.NO_SAMPLER, "warning")
        else:
            numbers = bold(QLabel(S.SAMPLER_NUMBERS.format(
                s["log_z"], s["information"], s["effective_sample_size"])))
            numbers.setObjectName("sampler_numbers")
        return self._figures(SAMPLER_FIGURES, before=numbers)

    def _report(self):
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setLineWrapMode(QPlainTextEdit.NoWrap)
        text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        text.setPlainText("\n".join(amorph_results.report_lines(self.results)))
        text.setObjectName("report")
        return text

    # --------------------------------------------------------------- export

    def _stem(self):
        return os.path.splitext(self.results.info.get("data_file",
                                                      "amorph"))[0]

    def save_archive(self):
        if self.results is None:
            return
        name = os.path.basename(self.archive) if self.archive \
            else os.path.basename(amorph_archive.default_name(self.results))
        path = self.save_file_name(S.SAVE_ARCHIVE_TIP, name, S.FILTER_ARCHIVE)
        if path:
            self.write_archive(path)

    def write_archive(self, path):
        results, source = self.results, self.archive

        def job():
            if source and os.path.isfile(source):
                if os.path.abspath(source) != os.path.abspath(path):
                    shutil.copyfile(source, path)
            else:
                amorph_archive.write(results, path)
            return path

        self._export(job)

    def save_posterior(self):
        if self.results is None:
            return
        if self.results.posterior is None:
            self.report_error(S.ERROR, S.NO_POSTERIOR)
            return
        path = self.save_file_name(S.SAVE_POSTERIOR_TIP,
                                   self._stem() + "_posterior.csv",
                                   S.FILTER_CSV)
        if path:
            self.write_posterior(path)

    def write_posterior(self, path):
        posterior = self.results.posterior

        def job():
            posterior.to_csv(path, index=False)
            return path

        self._export(job)

    def save_figures(self):
        if self.results is None:
            return
        folder = QFileDialog.getExistingDirectory(self, S.SAVE_FIGURES_TIP)
        if folder:
            self.write_figures(folder)

    def write_figures(self, folder):
        results, stem = self.results, self._stem()

        def job():
            for name, _, draw in amorph_results.available_figures(results):
                with open(os.path.join(folder, "{0}_{1}.png".format(
                        stem, name)), "wb") as f:
                    f.write(amorph_archive.figure_png(results, draw))
            return folder

        self._export(job, S.FIGURES_SAVED)

    def _export(self, job, done_text=S.SAVED):
        self.tasks.run(job, lambda path: self.message.emit(
            done_text.format(path)),
            lambda error: self.report_error(S.ERROR, error))
