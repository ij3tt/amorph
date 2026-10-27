"""
The screen «Результаты»: the results of one run, from its folder after the
post-processing or from an archive. The tabs show the fraction with its
intervals, the diagnostic cards, the decomposition of the scan and the
distribution of the fraction; the figures of amorph_results.FIGURES; and
the whole report. The header exports the figures, the archive, the
posterior samples, the tables of PGFPlots (export_pgf.py) and the report
for LaTeX (report.py).
"""

import os
import shutil

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QLabel,
                               QPlainTextEdit, QScrollArea, QTabWidget,
                               QVBoxLayout, QWidget)

import amorph_archive
import amorph_results
import amorph_seeds
import amorph_tex

from amorph_gui import digest, helptext, report
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.widgets import (Banner, Card, FigureView, HelpButton,
                                IntervalBar, Screen, card, language_menu,
                                styled_label, tooltip)

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


def _page():
    page = QWidget()
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 16, 4, 8)
    layout.setSpacing(16)
    return page, layout


def _note(text, level="info"):
    banner = Banner()
    banner.show_message(text, level)
    return banner


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
        self.set_header("", S.NO_RESULTS)

        self.export_buttons = [
            self.add_button(S.SAVE_ARCHIVE, self.save_archive,
                            S.SAVE_ARCHIVE_TIP),
            self.add_button(S.SAVE_POSTERIOR, self.save_posterior,
                            S.SAVE_POSTERIOR_TIP),
            self.add_button(S.SAVE_FIGURES, self.save_figures,
                            S.SAVE_FIGURES_TIP),
            self.add_button(S.EXPORT_DATA, self.save_pgf_data,
                            S.EXPORT_DATA_ONE_TIP),
            self.add_button(S.EXPORT_REPORT, None, S.EXPORT_REPORT_TIP,
                            menu=language_menu(self, self.save_report))]
        for button in self.export_buttons:
            button.setEnabled(False)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
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
        self.set_header(results.info.get("data_file", S.UNKNOWN),
                        "seed {0} · {1}".format(
                            S.NO_SEED if seed is None else seed, source))
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
            self.tabs.setTabToolTip(index, tooltip(S.TAB_TIPS[index]))
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

    # -------------------------------------------------------------- Итог

    def _summary(self):
        r = self.results
        d = r.diagnosis
        cards = digest.diagnostic_cards(r, self.stopped)
        page, layout = _page()

        top = QHBoxLayout()
        top.setSpacing(16)
        badge = None
        if any(level == digest.RED for level, _, _ in cards):
            badge = styled_label(S.UNRELIABLE, "badge", wrap=False)
        fraction_card, column = card(S.FRACTION_TITLE, badge, help="fraction")
        if d is None:
            column.addWidget(_note(S.NO_DIAGNOSIS, "warning"))
        else:
            f = d["fraction"]
            value = QLabel("{0:.3f}".format(f["q50"]))
            value.setObjectName("fraction")
            value.setToolTip(tooltip(S.FRACTION_TIP))
            column.addWidget(value)
            row = QHBoxLayout()
            row.setSpacing(6)
            intervals = QLabel(S.FRACTION_INTERVALS.format(
                f["q25"], f["q75"], f["q05"], f["q95"]))
            intervals.setObjectName("mono")
            intervals.setWordWrap(True)
            intervals.setToolTip(tooltip(S.INTERVALS_TIP))
            row.addWidget(intervals, 1)
            row.addWidget(HelpButton("intervals"), 0, Qt.AlignTop)
            column.addLayout(row)
            bar = IntervalBar([f["q05"], f["q25"], f["q50"], f["q75"],
                               f["q95"]])
            bar.setToolTip(tooltip(helptext.short("intervals")))
            column.addWidget(bar)
            p = d.get("fraction_in_range")
            if p and p.get("range"):
                column.addWidget(styled_label(S.FRACTION_IN_RANGE.format(
                    p["range"][0], p["range"][1], p["q50"], p["q25"],
                    p["q75"]), "mono"))
        column.addWidget(styled_label(S.NOTE_FRACTION, "muted"))
        column.addStretch(1)
        top.addWidget(fraction_card, 2)

        diagnosis_card, column = card(S.DIAGNOSIS_TITLE, spacing=8,
                                      help="diagnosis")
        for level, title, text in cards:
            column.addWidget(Card(level, title, text))
        if d is not None:
            posterior = len(r.posterior) if r.posterior is not None else 0
            ess = styled_label(S.ESS.format(d["effective_sample_size"],
                                            d["saves"], posterior), "muted")
            ess.setToolTip(tooltip(helptext.short("ess")))
            column.addWidget(ess)
        column.addWidget(styled_label(S.NOTE_SEEDS, "muted"))
        column.addStretch(1)
        top.addWidget(diagnosis_card, 3)
        layout.addLayout(top)

        plots = QHBoxLayout()
        plots.setSpacing(16)
        decomposition = self._decomposition()
        if decomposition is not None:
            plots.addWidget(decomposition, 3)
        histogram = self._histogram()
        if histogram is not None:
            plots.addWidget(histogram, 2)
        if decomposition is not None or histogram is not None:
            layout.addLayout(plots)

        layout.addWidget(self._settings_label())
        layout.addStretch(1)
        return _scroll(page)

    def _decomposition(self):
        """
        The scan, the background, and the amorphous and crystalline parts on
        top of it: the posterior means of the curves.
        """
        c = self.results.curves or {}
        if not all(k in c for k in ("bg_mean", "wide_mean", "narrow_mean")):
            return None
        x = np.asarray(self.results.x, dtype=float)
        bg = np.asarray(c["bg_mean"], dtype=float)
        wide = bg + np.asarray(c["wide_mean"], dtype=float)
        top = wide + np.asarray(c["narrow_mean"], dtype=float)
        legend = QLabel(theme.swatches([
            ("line", theme.DATA, S.LEGEND_DATA),
            ("dash", theme.BACKGROUND, S.LEGEND_BACKGROUND),
            ("box", theme.WIDE_FILL, S.LEGEND_WIDE_PART),
            ("box", theme.NARROW_FILL, S.LEGEND_NARROW_PART)]))
        legend.setTextFormat(Qt.RichText)
        legend.setObjectName("muted")
        frame, layout = card(S.DECOMPOSITION_TITLE, help="decomposition")
        layout.addWidget(legend)
        plot = pg.PlotWidget()
        item = theme.style_plot(plot, S.AXIS_X, S.AXIS_Y)
        base = item.plot(x, bg, pen=pg.mkPen(theme.BACKGROUND, width=1.5,
                                             style=Qt.DashLine))
        wide_line = item.plot(x, wide, pen=pg.mkPen(theme.WIDE, width=2))
        top_line = item.plot(x, top, pen=pg.mkPen(None))
        item.addItem(pg.FillBetweenItem(base, wide_line, brush=pg.mkBrush(
            theme.qcolor(theme.WIDE_FILL, 150))))
        item.addItem(pg.FillBetweenItem(wide_line, top_line, brush=pg.mkBrush(
            theme.qcolor(theme.NARROW_FILL, 170))))
        item.plot(x, self.results.y, pen=pg.mkPen(theme.DATA, width=1))
        item.setXRange(float(x[0]), float(x[-1]), padding=0.01)
        plot.setMinimumHeight(280)
        layout.addWidget(plot, 1)
        return frame

    def _histogram(self):
        """
        The distribution of the fraction over the saved particles, weighted
        (the histogram of the diagnosis); the weight below 0.2 in orange.
        """
        d = self.results.diagnosis
        if d is None or "histogram" not in d:
            return None
        edges = np.asarray(d["histogram"]["edges"], dtype=float)
        weights = np.asarray(d["histogram"]["weights"], dtype=float)
        if weights.size == 0 or weights.max() <= 0.0:
            return None
        frame, layout = card(S.HISTOGRAM_TITLE, help="histogram")
        plot = pg.PlotWidget()
        item = theme.style_plot(plot, S.FRACTION_TITLE)
        width = np.diff(edges)
        low = edges[:-1] < 0.2
        for mask, color in ((low, theme.NARROW), (~low, theme.WIDE)):
            if mask.any():
                item.addItem(pg.BarGraphItem(
                    x0=edges[:-1][mask] + 0.05 * width[mask],
                    width=0.9 * width[mask], height=weights[mask],
                    brush=pg.mkBrush(color), pen=pg.mkPen(None)))
        item.setXRange(0.0, 1.0, padding=0.02)
        item.getAxis("left").setStyle(showValues=False)
        plot.setMinimumHeight(280)
        layout.addWidget(plot, 1)
        layout.addWidget(styled_label(S.HISTOGRAM_NOTE, "muted"))
        return frame

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
        return styled_label(S.SETTINGS_SUMMARY + ": " + S.SETTINGS_LINE.format(
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
            options=c.get("dnest4_options_file", S.UNKNOWN)), "muted")

    # ------------------------------------------------------ the other tabs

    def _figures(self, names, columns=1, size=(9.0, 4.6), before=None):
        r = self.results
        available = {name: (title, draw) for name, title, draw
                     in amorph_results.available_figures(r)}
        page, layout = _page()
        if before is not None:
            layout.addWidget(before)
        grid = QGridLayout()
        grid.setSpacing(16)
        shown = 0
        for name in names:
            if name not in available:
                continue
            title, draw = available[name]
            view = FigureView(r, name, S.FIGURE_TITLES.get(name, title), draw,
                              size, self.report_error,
                              help=helptext.FIGURE_TOPICS.get(name))
            self.figure_views[name] = view
            grid.addWidget(view, shown // columns, shown % columns)
            shown += 1
        layout.addLayout(grid)
        if shown == 0:
            layout.addWidget(styled_label(S.NO_FIGURES, "muted"))
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
            numbers, layout = card()
            row = QHBoxLayout()
            row.setSpacing(8)
            label = QLabel(S.SAMPLER_NUMBERS.format(
                s["log_z"], s["information"], s["effective_sample_size"]))
            label.setObjectName("sampler_numbers")
            label.setFont(theme.mono(10.5))
            label.setWordWrap(True)
            row.addWidget(label, 1)
            row.addWidget(HelpButton("log_z"), 0, Qt.AlignVCenter)
            row.addWidget(HelpButton("ess"), 0, Qt.AlignVCenter)
            layout.addLayout(row)
        return self._figures(SAMPLER_FIGURES, before=numbers)

    def _report(self):
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setLineWrapMode(QPlainTextEdit.NoWrap)
        text.setFont(theme.mono(9.5))
        text.setPlainText("\n".join(amorph_results.report_lines(self.results)))
        text.setObjectName("report")
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.addWidget(text)
        return page

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

    def save_pgf_data(self):
        if self.results is None:
            return
        folder = QFileDialog.getExistingDirectory(self, S.CHOOSE_DATA_FOLDER)
        if folder:
            self.write_pgf_data(folder)

    def write_pgf_data(self, folder):
        """
        The tables of PGFPlots of the run, as export_pgf.py writes them for
        doc/figures/xrd_fit.tex, into folder.
        """
        results = self.results
        title = results.info.get("data_file", "amorph")

        def job():
            amorph_tex.write_tables(amorph_seeds.pool([results]), folder,
                                    title)
            return folder

        self._export(job)

    def save_report(self, language):
        if self.results is None:
            return
        folder = QFileDialog.getExistingDirectory(self,
                                                  S.CHOOSE_REPORT_FOLDER)
        if folder:
            self.write_report(folder, language)

    def write_report(self, folder, language="ru"):
        """
        The report of the run for LaTeX (report.write_report) in folder,
        in language ("ru" or "en"): report.tex with the figures and their
        tables, to build with pdflatex.
        """
        rows = report.results_rows(self.results, self.archive)
        title = str(self.results.info.get("data_file", "amorph"))
        self._export(lambda: report.write_report(rows, folder, title,
                                                 language=language))

    def _export(self, job, done_text=S.SAVED):
        self.tasks.run(job, lambda path: self.message.emit(
            done_text.format(path)),
            lambda error: self.report_error(S.ERROR, error))
