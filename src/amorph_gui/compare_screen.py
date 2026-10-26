"""
The screen «Сравнение»: a table of several run archives, such as the seeds
of one sample or the run.amorph files of the experiment and validate
workflows, with the sampler of each run, its effective sample size, its
log(Z) against the best run of the same data and settings, the fraction,
its 50% interval as a bar on a common scale, the posterior weight below 0.2
and at the cap, and the checks of the run; exported as CSV or Markdown.

The ticked runs (all but those that failed a red check, unless the user
ticks otherwise) make the joint report: the fraction of all of them
together, how far apart the seeds are, and a figure, in the style of
doc/figures/xrd_fit.tex or with two panels, previewed here and exported as
the tables of PGFPlots, a folder for LaTeX, PDF, SVG or PNG (amorph_tex).
"""

import bisect
import glob
import itertools
import os
import shutil
import tempfile

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QRectF, Qt,
                            QTimer, Signal)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup,
                               QFileDialog, QGridLayout, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QStyle, QStyledItemDelegate,
                               QTableView, QVBoxLayout, QWidget)

import amorph_archive
import amorph_tex

from amorph_gui import digest, figures
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.widgets import Banner, HelpButton, Screen, card, \
    paint_interval, styled_label, title_row, tooltip

COLUMNS = [S.COLUMN_ARCHIVE, S.COLUMN_DATA, S.COLUMN_SETTINGS, S.COLUMN_SEED,
           S.COLUMN_SAMPLER, S.COLUMN_ESS, S.COLUMN_LOG_Z, S.COLUMN_FRACTION,
           None, S.COLUMN_LOW, S.COLUMN_CAP, S.COLUMN_CHECK]
LOG_Z_COLUMN = 6
INTERVAL_COLUMN = 8
CHECK_COLUMN = 11
RIGHT_ALIGNED = (3, 5, 6, 7, 9, 10)

# The role of the quantiles q05, q25, q50, q75 and q95 of a row
QUANTILES_ROLE = Qt.UserRole + 1

# The colours of the checks
CHECK_COLORS = {digest.RED: theme.RED, digest.AMBER: theme.AMBER,
                digest.OK: theme.GREEN}

# The figure styles, as amorph_tex.FIGURES names them
STYLES = [("fit", S.STYLE_FIT), ("seeds", S.STYLE_SEEDS)]
STYLE_NOTES = {"fit": S.FIGURE_FIT_NOTE, "seeds": S.FIGURE_SEEDS_NOTE}

# The size of the figures saved as PNG, in inches, and their resolution
PNG_SIZE = {"fit": (8.0, 5.3), "seeds": (11.0, 4.4)}
PNG_DPI = 200


class ComparisonModel(QAbstractTableModel):
    """
    The rows of digest.comparison_row, one per archive.
    chosenChanged(): the user ticked or unticked a run.
    """

    chosenChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        # When each row was asked for: the archives are read in parallel,
        # and the rows keep the order in which they were added
        self.orders = []

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLUMNS)

    def scale(self):
        """
        The common scale of the interval bars: the 90% intervals of all the
        rows, with a margin, within 0 to 1.
        """
        values = [v for row in self.rows if row["q05"] is not None
                  for v in (row["q05"], row["q95"])]
        if not values:
            return 0.0, 1.0
        lo, hi = min(values), max(values)
        margin = max(0.1 * (hi - lo), 0.02)
        lo, hi = max(0.0, lo - margin), min(1.0, hi + margin)
        if hi - lo < 0.05:
            middle = 0.5 * (lo + hi)
            lo, hi = max(0.0, middle - 0.025), min(1.0, middle + 0.025)
        return lo, hi

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation != Qt.Horizontal:
            return None
        if role == Qt.DisplayRole:
            if section == INTERVAL_COLUMN:
                return S.COLUMN_INTERVAL.format(*self.scale())
            return COLUMNS[section]
        if role == Qt.ToolTipRole:
            if section == INTERVAL_COLUMN:
                return tooltip(S.COLUMN_INTERVAL_TIP)
            return tooltip(S.COLUMN_TIPS[section])
        return None

    def flags(self, index):
        flags = super().flags(index)
        if index.isValid() and index.column() == 0:
            flags |= Qt.ItemIsUserCheckable
        return flags

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        column = index.column()
        if role == QUANTILES_ROLE:
            if row["q50"] is None:
                return None
            return [row[q] for q in ("q05", "q25", "q50", "q75", "q95")]
        if role == Qt.CheckStateRole and column == 0:
            return Qt.Checked if row["chosen"] else Qt.Unchecked
        if role == Qt.ToolTipRole:
            if column == 0:
                return row["archive"]
            if column == INTERVAL_COLUMN and row["q50"] is not None:
                return S.FRACTION_INTERVALS.format(row["q25"], row["q75"],
                                                   row["q05"], row["q95"])
            if column == LOG_Z_COLUMN and row["log_z"] is not None:
                return S.LOG_Z_TIP.format(row["log_z"],
                                          row["log_z"] - row["dlog_z"])
            if column == CHECK_COLUMN:
                return digest.check_text(row)
            return None
        if role == Qt.ForegroundRole:
            if column == CHECK_COLUMN:
                return QColor(CHECK_COLORS[digest.check_level(row)])
            if column == LOG_Z_COLUMN and row["dlog_z"] is not None \
                    and row["dlog_z"] <= -digest.LOG_Z_GAP:
                return QColor(theme.RED)
            return None
        if role == Qt.TextAlignmentRole and column in RIGHT_ALIGNED:
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role != Qt.DisplayRole:
            return None
        return [digest.archive_text(row), row["data_file"],
                row["settings"], digest.seed_text(row),
                digest.sampler_text(row), digest.ess_text(row),
                digest.dlog_z_text(row), digest.fraction_text(row), None,
                digest.weight_text(row["below_0.2"]),
                digest.weight_text(row["at_cap"]),
                digest.check_text(row)][column]

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or index.column() != 0 \
                or role != Qt.CheckStateRole:
            return False
        self.choose(index.row(), Qt.CheckState(value) == Qt.Checked)
        return True

    def choose(self, i, chosen):
        """
        Tick (chosen) or untick the run of row i, as the user.
        """
        row = self.rows[i]
        row["chosen"] = bool(chosen)
        row["chosen_by_user"] = True
        self.dataChanged.emit(self.index(i, 0),
                              self.index(i, len(COLUMNS) - 1))
        self.chosenChanged.emit()

    def _remark(self):
        # log(Z) of every row against the best of its group, which may
        # change with the rows
        digest.mark_log_z(self.rows)
        if self.rows:
            self.dataChanged.emit(self.index(0, 0),
                                  self.index(len(self.rows) - 1,
                                             len(COLUMNS) - 1))

    def add(self, row, order=None):
        if order is None:
            order = self.orders[-1] + 1 if self.orders else 0
        i = bisect.bisect(self.orders, order)
        self.beginInsertRows(QModelIndex(), i, i)
        self.rows.insert(i, row)
        self.orders.insert(i, order)
        digest.mark_log_z(self.rows)
        self.endInsertRows()
        self._remark()
        self.headerDataChanged.emit(Qt.Horizontal, INTERVAL_COLUMN,
                                    INTERVAL_COLUMN)

    def remove(self, numbers):
        for i in sorted(numbers, reverse=True):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self.rows[i]
            del self.orders[i]
            self.endRemoveRows()
        self._remark()
        self.headerDataChanged.emit(Qt.Horizontal, INTERVAL_COLUMN,
                                    INTERVAL_COLUMN)

    def clear(self):
        self.beginResetModel()
        self.rows = []
        self.orders = []
        self.endResetModel()


class IntervalDelegate(QStyledItemDelegate):
    """
    Draws the median and the 50% and 90% intervals of the fraction of a
    row, on the common scale of the model.
    """

    def paint(self, painter, option, index):
        self.initStyleOption(option, index)
        style = option.widget.style() if option.widget else None
        if style is not None:
            style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter,
                                option.widget)
        quantiles = index.data(QUANTILES_ROLE)
        if quantiles is None:
            return
        rect = QRectF(option.rect).adjusted(8, 2, -8, -2)
        paint_interval(painter, rect, quantiles, index.model().scale())


class CompareScreen(Screen):
    """
    showArchive(path) asks for an archive on «Результаты».
    """

    showArchive = Signal(str)
    message = Signal(str)
    # A folder to open: its runs and its archives (main_window.open_paths)
    folderChosen = Signal(str)

    def __init__(self, tasks, parent=None):
        super().__init__(S.SCREEN_COMPARE, parent)
        self.tasks = tasks
        self.pending = 0
        self.last_dir = None
        self._order = itertools.count()
        self.pooled = None
        self.figure_style = "fit"
        self.latex = amorph_tex.find_latex()
        self.add_button(S.ADD_ARCHIVES, self.add_archives_dialog)
        self.add_button(S.ADD_FOLDER, self.add_folder_dialog,
                        S.ADD_FOLDER_TIP)
        self.add_button(S.REMOVE_ROWS, self.remove_selected)
        self.add_button(S.CLEAR_ROWS, self.clear)
        self.add_button(S.EXPORT_CSV, self.export_csv_dialog)
        self.add_button(S.EXPORT_MARKDOWN, self.export_markdown_dialog)

        self.set_header("", S.COMPARE_HINT)

        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(0, 0, 4, 0)
        column.setSpacing(16)
        column.addWidget(self._make_table())

        # What the table shows: the spread of the seeds against that of the
        # settings
        summary_card, summary_layout = card(S.SUMMARY_TITLE,
                                            help="compare_summary")
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("summary")
        summary_layout.addWidget(self.summary)
        column.addWidget(summary_card)

        row = QHBoxLayout()
        row.setSpacing(16)
        row.addWidget(self._make_joint(), 2)
        row.addWidget(self._make_figure(), 3)
        column.addLayout(row)
        column.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(page)
        self.body.addWidget(scroll, 1)

        # The joint report follows the ticks, a moment after the last one
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(150)
        self.refresh_timer.timeout.connect(self.refresh_joint)
        for signal in (self.model.rowsInserted, self.model.rowsRemoved,
                       self.model.modelReset, self.model.chosenChanged):
            signal.connect(self._summarise)
            signal.connect(self.refresh_timer.start)
        self._summarise()
        self.refresh_joint()

    # -------------------------------------------------------------- layout

    def _make_table(self):
        table_card, table_layout = card(S.TABLE_TITLE, help="compare_table")
        self.model = ComparisonModel(self)
        self.view = QTableView()
        self.view.setShowGrid(False)
        self.view.verticalHeader().setDefaultSectionSize(40)
        self.view.setModel(self.model)
        self.view.setItemDelegateForColumn(INTERVAL_COLUMN,
                                           IntervalDelegate(self.view))
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.verticalHeader().setVisible(False)
        self.view.setWordWrap(False)
        self.view.setMinimumHeight(220)
        header = self.view.horizontalHeader()
        # Wide enough for the names of the columns that stretch, also in an
        # empty table
        header.setMinimumSectionSize(84)
        for i in range(len(COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        self.view.setTextElideMode(Qt.ElideMiddle)
        header.setSectionResizeMode(INTERVAL_COLUMN, QHeaderView.Fixed)
        header.resizeSection(INTERVAL_COLUMN, 180)
        self.view.doubleClicked.connect(self._double_clicked)
        table_layout.addWidget(self.view, 1)
        self.errors = QLabel()
        self.errors.setStyleSheet("color: {0}".format(theme.RED))
        self.errors.setWordWrap(True)
        self.errors.hide()
        table_layout.addWidget(self.errors)
        return table_card

    def _make_joint(self):
        joint_card, layout = card(S.JOINT_TITLE, help="joint")
        layout.addWidget(styled_label(S.JOINT_CAPTION, "muted"))
        self.joint_value = QLabel("—")
        self.joint_value.setObjectName("liveFraction")
        self.joint_value.setToolTip(tooltip(S.FRACTION_TIP))
        layout.addWidget(self.joint_value)
        self.joint_intervals = QLabel()
        self.joint_intervals.setObjectName("mono")
        self.joint_intervals.setWordWrap(True)
        self.joint_intervals.setToolTip(tooltip(S.INTERVALS_TIP))
        layout.addWidget(self.joint_intervals)
        stats = QGridLayout()
        stats.setHorizontalSpacing(16)
        self.joint_stats = []
        for i, caption in enumerate((S.JOINT_COUNT, S.JOINT_SPREAD,
                                     S.JOINT_ESS)):
            value = QLabel("—")
            value.setObjectName("stat")
            value.setToolTip(tooltip(S.JOINT_TIPS[i]))
            text = styled_label(caption, "muted")
            text.setToolTip(tooltip(S.JOINT_TIPS[i]))
            stats.addWidget(value, 0, i)
            stats.addWidget(text, 1, i)
            stats.setColumnStretch(i, 1)
            self.joint_stats.append(value)
        layout.addLayout(stats)
        self.notes = QVBoxLayout()
        self.notes.setSpacing(8)
        layout.addLayout(self.notes)

        paper_title = QHBoxLayout()
        paper_title.setSpacing(6)
        paper_title.addWidget(styled_label(S.PAPER_TITLE, "muted",
                                           wrap=False))
        paper_title.addWidget(HelpButton("paper"), 0, Qt.AlignVCenter)
        paper_title.addStretch(1)
        layout.addLayout(paper_title)
        paper_row = QHBoxLayout()
        self.paper = QLabel()
        self.paper.setObjectName("mono")
        self.paper.setWordWrap(True)
        self.paper.setTextInteractionFlags(Qt.TextSelectableByMouse)
        paper_row.addWidget(self.paper, 1)
        self.copy_button = QPushButton(S.COPY)
        self.copy_button.setObjectName("small")
        self.copy_button.clicked.connect(self.copy_paper_line)
        paper_row.addWidget(self.copy_button, 0, Qt.AlignTop)
        layout.addLayout(paper_row)
        layout.addWidget(styled_label(S.JOINT_HOW, "muted"))
        layout.addStretch(1)
        return joint_card

    def _make_figure(self):
        figure_card, layout = card()
        top = title_row(S.FIGURE_TITLE, "figure")
        top.addStretch(1)
        top.addWidget(styled_label(S.FIGURE_STYLE, "muted", wrap=False))
        group = QButtonGroup(self)
        group.setExclusive(True)
        segments = QHBoxLayout()
        segments.setSpacing(0)
        self.style_buttons = {}
        for key, label in STYLES:
            button = QPushButton(label)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setChecked(key == self.figure_style)
            button.clicked.connect(lambda checked, k=key: self.set_style(k))
            group.addButton(button)
            segments.addWidget(button)
            self.style_buttons[key] = button
        top.addLayout(segments)
        layout.addLayout(top)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText(S.FIGURE_TITLE_PLACEHOLDER)
        self.title_edit.editingFinished.connect(self._redraw)
        layout.addWidget(self.title_edit)

        with matplotlib.rc_context(theme.matplotlib_style()):
            self.figure = Figure(figsize=(8.0, 4.6), dpi=100,
                                 layout="constrained")
            self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(380)
        layout.addWidget(self.canvas, 1)
        self.style_note = styled_label(STYLE_NOTES[self.figure_style], "muted")
        layout.addWidget(self.style_note)
        layout.addWidget(styled_label(S.FIGURE_PREVIEW_NOTE, "muted"))

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.export_buttons = {}
        for key, text, tip, slot, kind in (
                ("data", S.EXPORT_DATA, S.EXPORT_DATA_TIP,
                 self.export_data_dialog, "primary"),
                ("tex", S.EXPORT_TEX, S.EXPORT_TEX_TIP,
                 self.export_tex_dialog, None),
                ("pdf", S.EXPORT_PDF, None,
                 lambda: self.export_file_dialog("pdf"), None),
                ("svg", S.EXPORT_SVG, None,
                 lambda: self.export_file_dialog("svg"), None),
                ("png", S.EXPORT_PNG, S.EXPORT_PNG_TIP,
                 lambda: self.export_file_dialog("png"), None)):
            button = QPushButton(text)
            if kind:
                button.setObjectName(kind)
            if tip:
                button.setToolTip(tooltip(tip))
            button.clicked.connect(slot)
            buttons.addWidget(button)
            self.export_buttons[key] = button
        buttons.addStretch(1)
        layout.addLayout(buttons)
        missing = [t for t in amorph_tex.TOOLS if t not in self.latex]
        self.latex_label = styled_label(
            S.LATEX_MISSING.format(", ".join(missing)) if missing
            else S.LATEX_FOUND.format(", ".join(amorph_tex.TOOLS)), "muted")
        layout.addWidget(self.latex_label)
        return figure_card

    # ---------------------------------------------------------------- rows

    def _summarise(self, *args):
        self.summary.setText("\n".join(digest.comparison_summary(
            self.model.rows)))

    def add_archives_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, S.CHOOSE_ARCHIVES,
                                                self.last_dir or "",
                                                S.FILTER_ARCHIVE)
        if paths:
            self.add_archives(paths)

    def choose_folder(self, title):
        return QFileDialog.getExistingDirectory(self, title,
                                                self.last_dir or "")

    def add_folder_dialog(self):
        folder = self.choose_folder(S.CHOOSE_FOLDER)
        if folder:
            self.folderChosen.emit(folder)

    def add_folder(self, folder):
        """
        Add every run archive in folder and its subfolders.
        """
        paths = sorted(glob.glob(os.path.join(folder, "**", "*.amorph"),
                                 recursive=True))
        if not paths:
            self.errors.setText(S.NO_ARCHIVES_IN.format(folder))
            self.errors.show()
            return
        self.add_archives(paths)

    def add_archives(self, paths):
        """
        Read archives in worker threads and add a row for each.
        """
        self.errors.hide()
        for path in paths:
            path = os.path.abspath(path)
            self.last_dir = os.path.dirname(path)
            self.pending += 1
            order = next(self._order)

            def job(path=path, order=order):
                return order, digest.comparison_row(amorph_archive.read(path),
                                                    path)

            def failed(error, path=path):
                self.pending -= 1
                self.errors.setText(S.CANNOT_READ_ARCHIVE.format(path)
                                    + ": " + error)
                self.errors.show()

            self.tasks.run(job, self._loaded, failed)

    def add_results(self, results, path):
        """
        A row for results already read, such as those of a run opened from
        its folder; path is its archive.
        """
        self.model.add(digest.comparison_row(results, path),
                       next(self._order))
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().resizeSection(INTERVAL_COLUMN, 180)

    def _loaded(self, result):
        self.pending -= 1
        order, row = result
        self.model.add(row, order)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().resizeSection(INTERVAL_COLUMN, 180)

    def remove_selected(self):
        rows = {i.row() for i in self.view.selectionModel().selectedRows()}
        self.model.remove(rows)

    def clear(self):
        self.model.clear()

    def _double_clicked(self, index):
        self.showArchive.emit(self.model.rows[index.row()]["archive"])

    def export_csv_dialog(self):
        path = self.save_file_name(S.EXPORT_CSV, "comparison.csv",
                                   S.FILTER_CSV)
        if path:
            self._write(path, digest.rows_csv(self.model.rows))

    def export_markdown_dialog(self):
        path = self.save_file_name(S.EXPORT_MARKDOWN, "comparison.md",
                                   S.FILTER_MARKDOWN)
        if path:
            self._write(path, digest.rows_markdown(self.model.rows))

    def _write(self, path, text):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except OSError as e:
            self.report_error(S.ERROR, S.CANNOT_SAVE.format(path) + "\n"
                              + str(e))
            return
        self.message.emit(S.SAVED.format(path))

    # ------------------------------------------------------ the joint report

    def refresh_joint(self):
        """
        The joint report and the figure of the ticked runs.
        """
        pooled, notes, paper = digest.joint_report(self.model.rows)
        self.pooled = pooled
        while self.notes.count():
            widget = self.notes.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        for level, text in notes:
            banner = Banner()
            banner.show_message(text, {digest.OK: "good"}.get(level, level))
            self.notes.addWidget(banner)
        if pooled is None:
            self.joint_value.setText("—")
            self.joint_intervals.setText("")
            for value in self.joint_stats:
                value.setText("—")
        else:
            q = pooled["quantiles"]
            self.joint_value.setText("{0:.3f}".format(q[2]))
            self.joint_intervals.setText(S.JOINT_INTERVALS.format(
                q[1], q[3], q[0], q[4]))
            count = len(pooled["seeds"])
            self.joint_stats[0].setText("{0} / {1}".format(
                count, len(self.model.rows)))
            self.joint_stats[1].setText(
                "—" if pooled["spread"] is None
                else "{0:.3f}".format(pooled["spread"]))
            self.joint_stats[2].setText("{0:.0f}".format(pooled["ess"]))
            chosen = [r for r in self.model.rows if r["chosen"]]
            default = str(chosen[0]["data_file"]) if chosen else ""
            if not self.title_edit.text() or \
                    self.title_edit.text() == self._default_title:
                self.title_edit.setText(default)
            self._default_title = default
        self.paper.setText(paper)
        self.copy_button.setEnabled(bool(paper))
        has = pooled is not None
        for key, button in self.export_buttons.items():
            needs = {"pdf": ["pdflatex"], "svg": ["latex", "dvisvgm"]}.get(
                key, [])
            button.setEnabled(has and all(t in self.latex for t in needs))
        self._redraw()

    _default_title = ""

    def figure_title(self):
        return self.title_edit.text().strip() or self._default_title

    def set_style(self, style):
        self.figure_style = style
        self.style_buttons[style].setChecked(True)
        self.style_note.setText(STYLE_NOTES[style])
        self._redraw()

    def _redraw(self):
        self.figure.clear()
        if self.pooled is not None:
            with matplotlib.rc_context(theme.matplotlib_style()):
                figures.DRAW[self.figure_style](self.figure, self.pooled,
                                                self.figure_title())
        # Now rather than at idle time, when the window may be gone
        self.canvas.draw()

    def copy_paper_line(self):
        QApplication.clipboard().setText(self.paper.text())
        self.message.emit(S.COPIED)

    # ------------------------------------------------------------- export

    def export_data_dialog(self):
        folder = self.choose_folder(S.CHOOSE_DATA_FOLDER)
        if folder:
            self.export_data(folder)

    def export_data(self, folder):
        """
        The tables of PGFPlots of the joint report into folder, as
        export_pgf.py writes them, with those of the two-panel figure.
        """
        pooled, title = self.pooled, self.figure_title()
        self._export(lambda: amorph_tex.write_tables(pooled, folder, title))

    def export_tex_dialog(self):
        folder = self.choose_folder(S.CHOOSE_TEX_FOLDER)
        if folder:
            self.export_tex(folder)

    def export_tex(self, folder):
        """
        The folder of the figure in the chosen style, ready for LaTeX.
        """
        pooled, style = self.pooled, self.figure_style
        title = self.figure_title()

        def job():
            amorph_tex.write_figure(pooled, folder, style, title)
            return folder

        self._export(job)

    def export_file_dialog(self, kind):
        stem = os.path.splitext(amorph_tex.FIGURES[self.figure_style][0])[0]
        filters = {"pdf": S.FILTER_PDF, "svg": S.FILTER_SVG,
                   "png": S.FILTER_PNG}
        path = self.save_file_name(S.FIGURE_TITLE, stem + "." + kind,
                                   filters[kind])
        if path:
            self.export_file(kind, path)

    def export_file(self, kind, path):
        """
        The figure as PDF or SVG, built by LaTeX in a temporary folder, or
        its preview as PNG.
        """
        pooled, style = self.pooled, self.figure_style
        title = self.figure_title()
        tools = self.latex
        if pooled is None:
            return
        if kind == "png":
            # Here rather than in a worker: matplotlib's settings are global
            try:
                with matplotlib.rc_context(theme.matplotlib_style()):
                    fig = Figure(figsize=PNG_SIZE[style], layout="constrained")
                    figures.DRAW[style](fig, pooled, title)
                    fig.savefig(path, dpi=PNG_DPI)
            except OSError as e:
                self.report_error(S.CANNOT_EXPORT, S.CANNOT_SAVE.format(path)
                                  + "\n" + str(e))
                return
            self.message.emit(S.SAVED.format(path))
            return

        def job():
            folder = tempfile.mkdtemp(prefix="amorph_tex_")
            try:
                amorph_tex.write_figure(pooled, folder, style, title)
                built = amorph_tex.build(folder, style, kind, tools)
                shutil.copyfile(built, path)
            finally:
                shutil.rmtree(folder, ignore_errors=True)
            return path

        self.message.emit(S.BUILDING.format(os.path.basename(path)))
        self._export(job)

    def _export(self, job):
        if self.pooled is None:
            return
        self.tasks.run(job, lambda path: self.message.emit(
            S.SAVED.format(path)),
            lambda error: self.report_error(S.CANNOT_EXPORT, error))
