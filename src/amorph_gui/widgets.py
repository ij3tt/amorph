"""
Widgets that the screens share: the header of a screen with its buttons
and «Открыть архив…», an inline message, a diagnostic card, the
point-and-interval bar of the amorphous fraction, and a matplotlib figure
of amorph_results.FIGURES with a button that saves it as PNG.
"""

import os

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSizePolicy,
                               QVBoxLayout, QWidget)

import amorph_archive

from amorph_gui import strings as S

# The colours of the levels of the checks and the cards: text, background
COLORS = {"error": ("#b71c1c", "#fdecea"), "red": ("#b71c1c", "#fdecea"),
          "warning": ("#8a5300", "#fff4e0"), "amber": ("#8a5300", "#fff4e0"),
          "ok": ("#1b5e20", "#e8f5e9"), "info": ("#0d47a1", "#e3f2fd")}

# The colour of the interval bars
ACCENT = QColor("#1565c0")


class Screen(QWidget):
    """
    A screen of the main window: a header with the title, the buttons of
    the screen and «Открыть архив…», above the body (self.body).
    """

    openArchiveRequested = Signal()
    # An error to show: title, text (the main window shows it)
    errorReported = Signal(str, str)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        self.header = QHBoxLayout()
        label = QLabel(title)
        font = label.font()
        font.setPointSizeF(font.pointSizeF() * 1.5)
        font.setBold(True)
        label.setFont(font)
        self.header.addWidget(label)
        self.header.addStretch(1)
        layout.addLayout(self.header)
        self.archive_button = QPushButton(S.OPEN_ARCHIVE)
        self.archive_button.setToolTip(S.OPEN_ARCHIVE_TIP)
        self.archive_button.clicked.connect(self.openArchiveRequested)
        self.header.addWidget(self.archive_button)
        self.body = QVBoxLayout()
        layout.addLayout(self.body, 1)

    def add_button(self, text, slot, tip=None):
        """
        A button of the screen in the header, before «Открыть архив…».
        """
        button = QPushButton(text)
        if tip:
            button.setToolTip(tip)
        button.clicked.connect(slot)
        self.header.insertWidget(self.header.count() - 1, button)
        return button

    def save_file_name(self, title, name, filter_text):
        path, _ = QFileDialog.getSaveFileName(self, title, name, filter_text)
        return path

    def report_error(self, title, text):
        self.errorReported.emit(title, text)


class Banner(QLabel):
    """
    A message in the colours of its level, hidden until there is one.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hide()

    def show_message(self, text, level="error"):
        fg, bg = COLORS[level]
        self.setStyleSheet("QLabel {{ color: {0}; background: {1}; "
                           "border-radius: 4px; padding: 8px; }}".format(fg,
                                                                         bg))
        self.setText(text)
        self.show()


class Card(QFrame):
    """
    A diagnostic card: a coloured frame with a title and a text.
    """

    def __init__(self, level, title, text, parent=None):
        super().__init__(parent)
        fg, bg = COLORS[level]
        self.level = level
        self.setObjectName("card")
        self.setStyleSheet(
            "QFrame#card {{ background: {1}; border-left: 5px solid {0}; "
            "border-radius: 4px; }} QLabel {{ color: {0}; }}".format(fg, bg))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.title = QLabel(title)
        font = self.title.font()
        font.setBold(True)
        self.title.setFont(font)
        self.text = QLabel(text)
        self.text.setWordWrap(True)
        layout.addWidget(self.title)
        layout.addWidget(self.text)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)


def paint_interval(painter, rect, quantiles, scale, color=ACCENT):
    """
    Draw the 90% interval (q05 to q95) as a thin line, the 50% interval
    (q25 to q75) as a thick bar and the median as a dot, on a scale from
    scale[0] to scale[1] across rect.
    """
    q05, q25, q50, q75, q95 = quantiles
    lo, hi = scale
    width = max(rect.width(), 1.0)

    def at(value):
        value = min(max(value, lo), hi)
        return rect.left() + (value - lo) / (hi - lo) * width

    y = rect.center().y()
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#b0bec5"), 1))
    painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
    painter.setPen(QPen(color, 2))
    painter.drawLine(QPointF(at(q05), y), QPointF(at(q95), y))
    thickness = min(10.0, rect.height() * 0.5)
    left = at(q25)
    painter.fillRect(QRectF(left, y - thickness / 2,
                            max(at(q75) - left, 2.0), thickness), color)
    radius = thickness * 0.55
    painter.setPen(QPen(QColor("#0d2b52"), 1.5))
    painter.setBrush(QColor("white"))
    painter.drawEllipse(QPointF(at(q50), y), radius, radius)
    painter.restore()


class IntervalBar(QWidget):
    """
    The point-and-interval bar of the fraction on a scale from 0 to 1, with
    tick labels.
    """

    TICKS = (0.0, 0.25, 0.5, 0.75, 1.0)

    def __init__(self, quantiles, parent=None):
        super().__init__(parent)
        self.quantiles = quantiles
        self.setMinimumHeight(54)
        self.setMinimumWidth(240)

    def paintEvent(self, event):
        painter = QPainter(self)
        margin = 14.0
        bar = QRectF(margin, 4.0, self.width() - 2 * margin, 26.0)
        painter.setPen(QPen(QColor("#78909c"), 1))
        for t in self.TICKS:
            x = bar.left() + t * bar.width()
            painter.drawLine(QPointF(x, bar.bottom() - 2),
                             QPointF(x, bar.bottom() + 3))
            text = "{0:g}".format(t)
            box = QRectF(x - 20, bar.bottom() + 4, 40, 16)
            painter.drawText(box, Qt.AlignHCenter | Qt.AlignTop, text)
        paint_interval(painter, bar, self.quantiles, (0.0, 1.0))
        painter.end()


class FigureView(QFrame):
    """
    One figure of amorph_results.FIGURES, drawn on a matplotlib canvas,
    with its title and a button that saves it as PNG
    (amorph_archive.figure_png).
    """

    def __init__(self, results, name, title, draw, size=(9.0, 5.0),
                 report_error=None, parent=None):
        super().__init__(parent)
        self.report_error = report_error
        self.results = results
        self.name = name
        self.draw = draw
        self.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        row = QHBoxLayout()
        label = QLabel(title)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        row.addWidget(label)
        row.addStretch(1)
        button = QPushButton(S.SAVE_PNG)
        button.setToolTip(S.SAVE_PNG_TIP)
        button.clicked.connect(self.save_png)
        row.addWidget(button)
        layout.addLayout(row)

        # The constrained layout keeps the labels in the canvas whatever its
        # size
        self.figure = Figure(figsize=size, dpi=100, layout="constrained")
        draw(self.figure, results)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumHeight(int(size[1] * 90))
        self.canvas.draw()
        layout.addWidget(self.canvas, 1)

    def default_name(self):
        data_file = self.results.info.get("data_file", "amorph")
        stem = os.path.splitext(data_file)[0]
        return "{0}_{1}.png".format(stem, self.name)

    def save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, S.SAVE_PNG_TIP,
                                              self.default_name(),
                                              S.FILTER_PNG)
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(amorph_archive.figure_png(self.results, self.draw))
        except OSError as e:
            text = S.CANNOT_SAVE.format(path) + "\n" + str(e)
            if self.report_error is not None:
                self.report_error(S.ERROR, text)
            else:
                QMessageBox.warning(self, S.ERROR, text)


def bold(label, scale=1.0):
    font = QFont(label.font())
    font.setBold(True)
    if scale != 1.0:
        font.setPointSizeF(font.pointSizeF() * scale)
    label.setFont(font)
    return label
