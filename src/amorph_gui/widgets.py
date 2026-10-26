"""
Widgets that the screens share, in the look of theme.py: the white header
of a screen with its description and buttons and «Открыть архив…», a
card, the «?» that explains what it stands next to, an inline message, a
diagnostic card with the icon of its level, the point-and-interval bar of
the amorphous fraction, and a matplotlib figure of amorph_results.FIGURES
in a card with a button that saves it as PNG.
"""

import html
import os

import matplotlib
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSizePolicy,
                               QToolButton, QVBoxLayout, QWidget)

import amorph_archive

from amorph_gui import helptext
from amorph_gui import strings as S
from amorph_gui import theme

# The colours of the levels of the checks and the cards: text, background
COLORS = {level: (fg, bg) for level, (fg, bg, _, _) in theme.LEVELS.items()}

# The colour of the interval bars
ACCENT = QColor(theme.ACCENT)

# The height of the header bar of a screen, and of the brand above the
# navigation, which continue each other
HEADER_HEIGHT = 58

# The width of the explanation that a «?» opens, in pixels
HELP_WIDTH = 440


def tooltip(*lines):
    """
    A tooltip of lines of plain text that wraps: Qt wraps the text of a
    tooltip only if it is rich text, and shows plain text in one line
    however long.
    """
    return "<p>{0}</p>".format("<br>".join(
        html.escape(line, quote=False) for line in lines if line))


class ElidedLabel(QLabel):
    """
    A label of one line that shortens its text in the middle, with "…",
    when it is too narrow for it (a long path in a header), instead of
    pushing the widgets beside it away. With word wrap it is a plain label.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(40)

    def paintEvent(self, event):
        if self.wordWrap():
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        text = self.fontMetrics().elidedText(self.text(), Qt.ElideMiddle,
                                             self.width())
        painter.drawText(self.rect(), self.alignment() | Qt.AlignVCenter,
                         text)
        painter.end()


class Screen(QWidget):
    """
    A screen of the main window: a white header with the description of
    what the screen shows (set_header), the buttons of the screen and
    «Открыть архив…», above the body (self.body) on the grey ground.
    """

    openArchiveRequested = Signal()
    # The screen asks to open run folders (main_window.open_runs_dialog)
    openRunsRequested = Signal()
    # An error to show: title, text (the main window shows it)
    errorReported = Signal(str, str)

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QWidget()
        bar.setObjectName("topbar")
        bar.setAttribute(Qt.WA_StyledBackground, True)
        bar.setFixedHeight(HEADER_HEIGHT)
        self.header = QHBoxLayout(bar)
        self.header.setContentsMargins(20, 8, 20, 8)
        self.header.setSpacing(8)
        self.header_name = QLabel()
        self.header_name.setObjectName("headerName")
        self.header_name.hide()
        self.header_text = ElidedLabel(title)
        self.header_text.setObjectName("headerText")
        self.header_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.header.addWidget(self.header_name)
        self.header.addSpacing(4)
        self.header.addWidget(self.header_text, 1)
        self.archive_button = QPushButton(S.OPEN_ARCHIVE)
        self.archive_button.setToolTip(tooltip(S.OPEN_ARCHIVE_TIP))
        self.archive_button.clicked.connect(self.openArchiveRequested)
        self.header.addWidget(self.archive_button)
        layout.addWidget(bar)

        ground = QWidget()
        ground.setObjectName("ground")
        ground.setAttribute(Qt.WA_StyledBackground, True)
        self.body = QVBoxLayout(ground)
        self.body.setContentsMargins(20, 16, 20, 16)
        self.body.setSpacing(16)
        layout.addWidget(ground, 1)

    def set_header(self, name, text):
        """
        The description in the header: a file name in the monospaced font,
        then the rest.
        """
        self.header_name.setText(name or "")
        self.header_name.setVisible(bool(name))
        self.header_text.setText(text or "")
        self.header_text.setToolTip(text or "")

    def add_button(self, text, slot, tip=None, kind=None):
        """
        A button of the screen in the header, before «Открыть архив…».
        kind "primary" or "danger" gives it the look of the design.
        """
        button = QPushButton(text)
        if kind:
            button.setObjectName(kind)
        if tip:
            button.setToolTip(tooltip(tip))
        button.clicked.connect(slot)
        self.header.insertWidget(self.header.count() - 1, button)
        return button

    def save_file_name(self, title, name, filter_text):
        path, _ = QFileDialog.getSaveFileName(self, title, name, filter_text)
        return path

    def report_error(self, title, text):
        self.errorReported.emit(title, text)


class HelpPopup(QFrame):
    """
    The explanation of a topic of helptext under its «?», until a click
    elsewhere; its link opens the topic on «Справка».
    """

    def __init__(self, topic, button):
        super().__init__(button, Qt.Popup)
        self.topic = topic
        self.setObjectName("helpPopup")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        title, _, body = helptext.TOPICS[topic]
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        self.text = QLabel(body)
        self.text.setObjectName("helpText")
        self.text.setTextFormat(Qt.RichText)
        self.text.setWordWrap(True)
        layout.addWidget(self.text)
        more = QLabel('<a href="help">{0}</a>'.format(S.HELP_MORE))
        more.setTextFormat(Qt.RichText)
        more.linkActivated.connect(self.open_help)
        layout.addWidget(more, 0, Qt.AlignRight)
        self.setFixedWidth(HELP_WIDTH)

    def open_help(self, link=None):
        window = self.parentWidget().window()
        self.close()
        if hasattr(window, "show_help"):
            window.show_help(self.topic)

    def show_under(self, widget):
        """
        Show the popup under widget, or above it where there is no room
        below, within the screen.
        """
        self.adjustSize()
        area = widget.screen().availableGeometry()
        below = widget.mapToGlobal(QPoint(0, widget.height() + 4))
        x = min(max(below.x() - 24, area.left() + 8),
                area.right() - self.width() - 8)
        y = below.y()
        if y + self.height() > area.bottom() - 8:
            y = widget.mapToGlobal(QPoint(0, 0)).y() - self.height() - 4
        self.move(x, max(y, area.top() + 8))
        self.show()


class HelpButton(QToolButton):
    """
    A small «?» that explains a topic of helptext: briefly as its tooltip,
    in full in a popup on a click.
    """

    def __init__(self, topic, parent=None):
        super().__init__(parent)
        self.topic = topic
        self.setText("?")
        self.setObjectName("help")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(QSize(20, 20))
        self.setToolTip(tooltip(helptext.short(topic) + " " + S.HELP_CLICK))
        self.popup = None
        self.clicked.connect(self.show_popup)

    def show_popup(self):
        self.popup = HelpPopup(self.topic, self)
        self.popup.show_under(self)
        return self.popup


def title_row(title, help=None):
    """
    The title of a card, with the «?» of its topic of helptext if given,
    in a row to which the caller adds what goes on the right.
    """
    row = QHBoxLayout()
    row.setSpacing(12)
    heading = QHBoxLayout()
    heading.setSpacing(6)
    label = QLabel(title)
    label.setObjectName("cardTitle")
    heading.addWidget(label)
    if help is not None:
        heading.addWidget(HelpButton(help), 0, Qt.AlignVCenter)
    row.addLayout(heading)
    return row


def card(title=None, right=None, margins=16, spacing=10, help=None):
    """
    A white card with a title, the «?» of a topic of helptext next to it,
    and a widget on the right of the title (a legend, a button). Returns
    the card and the layout of its content.
    """
    frame = QFrame()
    frame.setObjectName("card")
    frame.setAttribute(Qt.WA_StyledBackground, True)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(margins, margins - 2, margins, margins)
    layout.setSpacing(spacing)
    if title is not None or right is not None:
        if title is not None:
            row = title_row(title, help)
        else:
            row = QHBoxLayout()
            row.setSpacing(12)
        row.addStretch(1)
        if right is not None:
            row.addWidget(right)
        layout.addLayout(row)
    return frame, layout


def styled_label(text, name, wrap=True):
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


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
        fg, bg, line, _ = theme.LEVELS[level]
        self.setStyleSheet("QLabel {{ color: {0}; background: {1}; "
                           "border: 1px solid {2}; border-radius: 6px; "
                           "padding: 8px 10px; }}".format(fg, bg, line))
        self.setText(text)
        self.show()


class LevelIcon(QWidget):
    """
    The icon of a level: a circle with "!" (red), a triangle with "!"
    (amber), a tick (ok) or a circle with "i" (info).
    """

    def __init__(self, level, size=18, parent=None):
        super().__init__(parent)
        self.level = level
        self.setFixedSize(QSize(size, size))

    def paintEvent(self, event):
        color = QColor(theme.LEVELS[self.level][3])
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = float(self.width())
        pen = QPen(color, 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        if self.level == "ok":
            path = QPainterPath(QPointF(0.2 * s, 0.52 * s))
            path.lineTo(0.42 * s, 0.74 * s)
            path.lineTo(0.82 * s, 0.28 * s)
            p.drawPath(path)
        elif self.level in ("warning", "amber"):
            path = QPainterPath(QPointF(0.5 * s, 0.1 * s))
            path.lineTo(0.94 * s, 0.88 * s)
            path.lineTo(0.06 * s, 0.88 * s)
            path.closeSubpath()
            p.drawPath(path)
            p.drawLine(QPointF(0.5 * s, 0.4 * s), QPointF(0.5 * s, 0.6 * s))
            p.drawPoint(QPointF(0.5 * s, 0.74 * s))
        else:
            p.drawEllipse(QRectF(0.08 * s, 0.08 * s, 0.84 * s, 0.84 * s))
            if self.level == "info":
                p.drawPoint(QPointF(0.5 * s, 0.32 * s))
                p.drawLine(QPointF(0.5 * s, 0.48 * s),
                           QPointF(0.5 * s, 0.7 * s))
            else:
                p.drawLine(QPointF(0.5 * s, 0.28 * s),
                           QPointF(0.5 * s, 0.54 * s))
                p.drawPoint(QPointF(0.5 * s, 0.7 * s))
        p.end()


class Card(QFrame):
    """
    A diagnostic card: the icon of its level, a title and a text, on the
    background of its level (none for "ok").
    """

    def __init__(self, level, title, text, parent=None):
        super().__init__(parent)
        fg, bg, line, _ = theme.LEVELS[level]
        self.level = level
        self.setObjectName("diag")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            "QFrame#diag {{ background: {1}; border: 1px solid {2}; "
            "border-radius: 6px; }} QFrame#diag QLabel {{ color: {0}; "
            "background: transparent; }}".format(fg, bg, line))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)
        icon = LevelIcon(level)
        layout.addWidget(icon, 0, Qt.AlignTop)
        column = QVBoxLayout()
        column.setSpacing(2)
        self.title = QLabel(title)
        font = self.title.font()
        font.setWeight(QFont.Weight.DemiBold)
        self.title.setFont(font)
        self.title.setWordWrap(True)
        self.text = QLabel(text)
        self.text.setWordWrap(True)
        column.addWidget(self.title)
        column.addWidget(self.text)
        layout.addLayout(column, 1)
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
    soft = QColor(color)
    soft.setAlpha(110)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(theme.GRID), 1))
    painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
    painter.setPen(QPen(soft, 2))
    painter.drawLine(QPointF(at(q05), y), QPointF(at(q95), y))
    thickness = min(6.0, rect.height() * 0.4)
    left = at(q25)
    painter.setPen(Qt.NoPen)
    painter.setBrush(soft)
    painter.drawRoundedRect(QRectF(left, y - thickness / 2,
                                   max(at(q75) - left, 2.0), thickness),
                            thickness / 2, thickness / 2)
    radius = min(7.0, rect.height() * 0.35)
    painter.setPen(QPen(QColor("white"), 2))
    painter.setBrush(color)
    painter.drawEllipse(QPointF(at(q50), y), radius, radius)
    painter.restore()


class IntervalBar(QWidget):
    """
    The point-and-interval bar of the fraction on a scale from 0 to 1, with
    tick labels.
    """

    TICKS = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)

    def __init__(self, quantiles, parent=None):
        super().__init__(parent)
        self.quantiles = quantiles
        self.setMinimumHeight(48)
        self.setMinimumWidth(240)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setFont(theme.mono(8.5))
        margin = 12.0
        bar = QRectF(margin, 2.0, self.width() - 2 * margin, 24.0)
        painter.setPen(QPen(QColor(theme.MUTED), 1))
        for t in self.TICKS:
            x = bar.left() + t * bar.width()
            box = QRectF(x - 20, bar.bottom() + 4, 40, 16)
            painter.drawText(box, Qt.AlignHCenter | Qt.AlignTop,
                             "{0:g}".format(t))
        paint_interval(painter, bar, self.quantiles, (0.0, 1.0))
        painter.end()


class FigureView(QFrame):
    """
    One figure of amorph_results.FIGURES, drawn on a matplotlib canvas in
    the look of the screens, in a card with its title and a button that
    saves it as PNG (amorph_archive.figure_png, in the look of the
    archives).
    """

    def __init__(self, results, name, title, draw, size=(9.0, 5.0),
                 report_error=None, help=None, parent=None):
        super().__init__(parent)
        self.report_error = report_error
        self.results = results
        self.name = name
        self.draw = draw
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        row = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("cardTitle")
        label.setWordWrap(True)
        row.addWidget(label)
        self.help_button = None
        if help is not None:
            self.help_button = HelpButton(help)
            row.addWidget(self.help_button, 0, Qt.AlignVCenter)
        row.addStretch(1)
        button = QPushButton(S.SAVE_PNG)
        button.setObjectName("small")
        button.setToolTip(S.SAVE_PNG_TIP)
        button.clicked.connect(self.save_png)
        row.addWidget(button)
        layout.addLayout(row)

        # The constrained layout keeps the labels in the canvas whatever its
        # size
        with matplotlib.rc_context(theme.matplotlib_style()):
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
