"""
The screen «Сравнение»: a table of several run archives, such as the seeds
of one sample or the run.amorph files of the experiment and validate
workflows, with the fraction, its 50% interval as a bar on a common scale,
and the posterior weight below 0.2 and at the cap; exported as CSV or
Markdown.
"""

import bisect
import itertools
import os

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QHeaderView,
                               QLabel, QStyle, QStyledItemDelegate,
                               QTableView)

import amorph_archive

from amorph_gui import digest
from amorph_gui import strings as S
from amorph_gui.widgets import Screen, paint_interval

COLUMNS = [S.COLUMN_ARCHIVE, S.COLUMN_DATA, S.COLUMN_SETTINGS, S.COLUMN_SEED,
           S.COLUMN_FRACTION, None, S.COLUMN_LOW, S.COLUMN_CAP]
INTERVAL_COLUMN = 5

# The role of the quantiles q05, q25, q50, q75 and q95 of a row
QUANTILES_ROLE = Qt.UserRole + 1


class ComparisonModel(QAbstractTableModel):
    """
    The rows of digest.comparison_row, one per archive.
    """

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
        if role == Qt.ToolTipRole and section == INTERVAL_COLUMN:
            return S.COLUMN_INTERVAL_TIP
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        column = index.column()
        if role == QUANTILES_ROLE:
            if row["q50"] is None:
                return None
            return [row[q] for q in ("q05", "q25", "q50", "q75", "q95")]
        if role == Qt.ToolTipRole:
            if column == 0:
                return row["archive"]
            if column == INTERVAL_COLUMN and row["q50"] is not None:
                return S.FRACTION_INTERVALS.format(row["q25"], row["q75"],
                                                   row["q05"], row["q95"])
            return None
        if role == Qt.TextAlignmentRole and column in (3, 4, 6, 7):
            return int(Qt.AlignRight | Qt.AlignVCenter)
        if role != Qt.DisplayRole:
            return None
        return [digest.archive_text(row), row["data_file"],
                row["settings"], digest.seed_text(row),
                digest.fraction_text(row), None,
                digest.weight_text(row["below_0.2"]),
                digest.weight_text(row["at_cap"])][column]

    def add(self, row, order=None):
        if order is None:
            order = self.orders[-1] + 1 if self.orders else 0
        i = bisect.bisect(self.orders, order)
        self.beginInsertRows(QModelIndex(), i, i)
        self.rows.insert(i, row)
        self.orders.insert(i, order)
        self.endInsertRows()
        self.headerDataChanged.emit(Qt.Horizontal, INTERVAL_COLUMN,
                                    INTERVAL_COLUMN)

    def remove(self, numbers):
        for i in sorted(numbers, reverse=True):
            self.beginRemoveRows(QModelIndex(), i, i)
            del self.rows[i]
            del self.orders[i]
            self.endRemoveRows()
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

    def __init__(self, tasks, parent=None):
        super().__init__(S.SCREEN_COMPARE, parent)
        self.tasks = tasks
        self.pending = 0
        self.last_dir = None
        self._order = itertools.count()
        self.add_button(S.ADD_ARCHIVES, self.add_archives_dialog)
        self.add_button(S.REMOVE_ROWS, self.remove_selected)
        self.add_button(S.CLEAR_ROWS, self.clear)
        self.add_button(S.EXPORT_CSV, self.export_csv_dialog)
        self.add_button(S.EXPORT_MARKDOWN, self.export_markdown_dialog)

        hint = QLabel(S.COMPARE_HINT)
        hint.setWordWrap(True)
        self.body.addWidget(hint)
        self.model = ComparisonModel(self)
        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setItemDelegateForColumn(INTERVAL_COLUMN,
                                           IntervalDelegate(self.view))
        self.view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.verticalHeader().setVisible(False)
        self.view.setWordWrap(False)
        header = self.view.horizontalHeader()
        for i in range(len(COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(INTERVAL_COLUMN, QHeaderView.Fixed)
        header.resizeSection(INTERVAL_COLUMN, 220)
        self.view.doubleClicked.connect(self._double_clicked)
        self.body.addWidget(self.view, 1)
        self.errors = QLabel()
        self.errors.setStyleSheet("color: #b71c1c")
        self.errors.setWordWrap(True)
        self.errors.hide()
        self.body.addWidget(self.errors)

    def add_archives_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, S.CHOOSE_ARCHIVES,
                                                self.last_dir or "",
                                                S.FILTER_ARCHIVE)
        if paths:
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

    def _loaded(self, result):
        self.pending -= 1
        order, row = result
        self.model.add(row, order)
        self.view.resizeColumnsToContents()
        self.view.horizontalHeader().resizeSection(INTERVAL_COLUMN, 220)

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
