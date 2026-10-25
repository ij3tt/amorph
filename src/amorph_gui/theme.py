"""
The look of the GUI, as the design shows it: a light interface with white
cards on a grey ground, a blue accent, amber for the background of the
model and for warnings, red and green for the diagnostic levels, blue for
the amorphous and orange for the crystalline part. The colours, the fonts
and the style sheet of every screen are here, and the styling of the
pyqtgraph and matplotlib plots.
"""

from PySide6.QtGui import QColor, QFont

# ------------------------------------------------------------------ colours

INK = "#1B2430"
MUTED = "#5B6573"
GROUND = "#F4F6F8"
SURFACE = "#FFFFFF"
LINE = "#DDE2E8"
FIELD_LINE = "#C9D0D9"
GRID = "#E3E7ED"
HOVER = "#F1F5F9"

ACCENT = "#1D4ED8"
ACCENT_DARK = "#1E3A8A"
ACCENT_SOFT = "#EEF2FF"

# The background of the model, the control points and the warnings
AMBER = "#B45309"
AMBER_TEXT = "#7C2D12"
AMBER_SOFT = "#FFF7ED"
AMBER_LINE = "#FED7AA"

RED = "#991B1B"
RED_TEXT = "#7F1D1D"
RED_SOFT = "#FEF2F2"
RED_LINE = "#FECACA"

GREEN = "#166534"
GREEN_SOFT = "#F0FDF4"
GREEN_LINE = "#BBF7D0"

INFO = "#1E3A8A"
INFO_SOFT = "#EFF6FF"
INFO_LINE = "#BFDBFE"

# The curves: the data, the amorphous (wide) and crystalline (narrow) parts
DATA = "#4B5563"
DATA_LIGHT = "#9AA3AF"
WIDE = "#1D4ED8"
WIDE_FILL = "#BFD3FA"
NARROW = "#EA580C"
NARROW_FILL = "#F4A06C"
BACKGROUND = "#6B7280"
OUTSIDE = "#94A3B8"
BAND = "#DBEAFE"
BAND_LINE = "#93C5FD"

LOG_GROUND = "#0F172A"
LOG_INK = "#E2E8F0"

# The levels of the checks and of the diagnostic cards: text, background,
# border, icon colour
LEVELS = {
    "error": (RED_TEXT, RED_SOFT, RED_LINE, RED),
    "red": (RED_TEXT, RED_SOFT, RED_LINE, RED),
    "warning": (AMBER_TEXT, AMBER_SOFT, AMBER_LINE, AMBER),
    "amber": (AMBER_TEXT, AMBER_SOFT, AMBER_LINE, AMBER),
    "ok": (INK, SURFACE, SURFACE, GREEN),
    "info": (INFO, INFO_SOFT, INFO_LINE, INFO),
}

# The status of a run on «Прогоны»
STATUS_COLORS = {"waiting": MUTED, "running": ACCENT, "stopping": AMBER,
                 "postprocessing": ACCENT, "done": GREEN,
                 "incomplete": AMBER, "failed": RED, "cancelled": MUTED}

# -------------------------------------------------------------------- fonts

# The design's fonts first, then those of each system
SANS = ["IBM Plex Sans", "Segoe UI", "Helvetica Neue", "Noto Sans",
        "DejaVu Sans", "Arial"]
MONO = ["IBM Plex Mono", "Cascadia Mono", "Consolas", "Menlo",
        "DejaVu Sans Mono", "Courier New"]


def _font(families, points, weight):
    font = QFont()
    font.setFamilies(families)
    font.setPointSizeF(points)
    font.setWeight(weight)
    return font


def sans(points=10.0, weight=QFont.Weight.Normal):
    return _font(SANS, points, weight)


def mono(points=10.0, weight=QFont.Weight.Normal):
    font = _font(MONO, points, weight)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


def css_families(families):
    return ", ".join("'{0}'".format(f) for f in families)


# -------------------------------------------------------------- style sheet

STYLE_SHEET = """
QWidget {{ color: {INK}; }}
QMainWindow, QWidget#ground, QStackedWidget {{ background: {GROUND}; }}
QToolTip {{ color: {INK}; background: {SURFACE}; border: 1px solid {LINE};
    padding: 6px; }}

/* The brand and the header of each screen: one white bar */
QWidget#brand, QWidget#topbar {{ background: {SURFACE};
    border: none; border-bottom: 1px solid {LINE}; }}
QLabel#brandName {{ font-weight: 600; font-size: 12pt; }}
QLabel#headerName {{ font-family: {MONO_CSS}; }}
QLabel#headerText {{ color: {MUTED}; }}

/* Navigation */
QWidget#side {{ background: {SURFACE}; border-right: 1px solid {LINE}; }}
QListWidget#nav {{ background: {SURFACE}; border: none; outline: 0;
    padding: 8px; }}
QListWidget#nav::item {{ padding: 10px 12px; margin: 2px 0;
    border-radius: 6px; color: {INK}; }}
QListWidget#nav::item:hover:!selected {{ background: {HOVER}; }}
QListWidget#nav::item:selected {{ background: {ACCENT_SOFT};
    color: {ACCENT}; font-weight: 600; }}
QPushButton#flat {{ border: none; background: transparent; color: {MUTED};
    text-align: left; padding: 8px 12px; }}
QPushButton#flat:hover {{ background: {HOVER}; color: {INK}; }}

/* Cards */
QFrame#card {{ background: {SURFACE}; border: 1px solid {LINE};
    border-radius: 8px; }}
QFrame#card QLabel {{ background: transparent; }}
QLabel#cardTitle {{ font-weight: 600; font-size: 11pt; }}
QLabel#legend {{ color: {MUTED}; font-weight: 600; font-size: 8pt; }}
QLabel#fieldLabel {{ color: {MUTED}; font-size: 9pt; }}
QLabel#muted {{ color: {MUTED}; font-size: 9pt; }}
QLabel#mono {{ font-family: {MONO_CSS}; }}
QLabel#fraction {{ font-family: {MONO_CSS}; font-size: 34pt;
    font-weight: 500; }}
QLabel#badge {{ color: {RED}; background: {RED_SOFT};
    border: 1px solid {RED_LINE}; border-radius: 10px; padding: 1px 10px;
    font-weight: 600; font-size: 9pt; }}

/* Fields */
QLineEdit, QAbstractSpinBox, QComboBox {{ background: {SURFACE};
    border: 1px solid {FIELD_LINE}; border-radius: 6px; padding: 6px 8px;
    font-family: {MONO_CSS}; selection-background-color: {ACCENT}; }}
QComboBox {{ font-family: {SANS_CSS}; }}
/* A number field has no padding of its own: its editor, laid out in the
   field, takes the padding, and the look of the field rather than that of
   a field of its own, which would push the text out of sight. Its buttons
   are hidden here, by a width of 0: with setButtonSymbols(NoButtons) under
   a style sheet, Qt gives the editor a width of 1 pixel. */
QAbstractSpinBox {{ padding: 0; min-height: 32px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{ width: 0;
    border: none; }}
QAbstractSpinBox QLineEdit, QComboBox QLineEdit,
QLineEdit#qt_spinbox_lineedit {{ border: none; padding: 0 8px; margin: 0;
    background: transparent; }}
QLineEdit:focus, QAbstractSpinBox:focus, QComboBox:focus {{
    border: 1px solid {ACCENT}; }}
QAbstractSpinBox QLineEdit:focus {{ border: none; }}
QLineEdit:disabled, QAbstractSpinBox:disabled {{ color: {MUTED};
    background: {GROUND}; }}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: {SURFACE}; border: 1px solid
    {LINE}; selection-background-color: {ACCENT_SOFT};
    selection-color: {INK}; }}

/* Buttons */
QPushButton {{ background: {SURFACE}; border: 1px solid {FIELD_LINE};
    border-radius: 6px; padding: 7px 14px; }}
QPushButton:hover {{ background: #F8FAFC; border-color: #AEB7C2; }}
QPushButton:pressed {{ background: {HOVER}; }}
QPushButton:disabled {{ color: #9AA3AF; background: {GROUND};
    border-color: {LINE}; }}
QPushButton#primary {{ background: {ACCENT}; color: white;
    border: 1px solid {ACCENT}; font-weight: 600; padding: 10px 14px; }}
QPushButton#primary:hover {{ background: {ACCENT_DARK};
    border-color: {ACCENT_DARK}; }}
QPushButton#primary:disabled {{ background: #9DB0E4; border-color: #9DB0E4;
    color: {ACCENT_SOFT}; }}
QPushButton#danger {{ color: {AMBER_TEXT}; border: 1px solid #C2410C;
    font-weight: 600; }}
QPushButton#danger:disabled {{ color: #9AA3AF; border-color: {LINE}; }}
QPushButton#small {{ padding: 4px 10px; font-size: 9pt; }}

/* Tabs */
QTabWidget::pane {{ border: none; border-top: 1px solid {LINE}; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{ background: transparent; border: none;
    border-bottom: 3px solid transparent; padding: 10px 14px;
    color: {INK}; }}
QTabBar::tab:hover {{ color: {ACCENT}; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 3px solid {ACCENT};
    font-weight: 600; }}

/* Tables */
QTableView, QTableWidget {{ background: {SURFACE}; border: none;
    gridline-color: {SURFACE}; selection-background-color: {ACCENT_SOFT};
    selection-color: {INK}; alternate-background-color: #FAFBFC; }}
QTableView::item, QTableWidget::item {{ padding: 6px 8px;
    border-bottom: 1px solid #EEF1F4; }}
QHeaderView {{ background: {SURFACE}; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED};
    font-weight: 600; font-size: 9pt; border: none;
    border-bottom: 1px solid {LINE}; padding: 8px; }}

/* Progress, logs, reports, scroll areas */
QProgressBar {{ background: #E5E9EF; border: none; border-radius: 4px;
    max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}
QPlainTextEdit#log {{ background: {LOG_GROUND}; color: {LOG_INK};
    border: none; border-radius: 6px; padding: 8px;
    font-family: {MONO_CSS}; }}
QPlainTextEdit#report {{ background: {SURFACE}; border: 1px solid {LINE};
    border-radius: 8px; padding: 10px; font-family: {MONO_CSS}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent;
    border: none; }}
QSplitter::handle {{ background: transparent; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {LINE};
    color: {MUTED}; }}
QDialog {{ background: {GROUND}; }}
""".format(MONO_CSS=css_families(MONO), SANS_CSS=css_families(SANS),
           **{k: v for k, v in globals().items() if k.isupper()
              and isinstance(v, str)})


# ------------------------------------------------------------------- plots

def style_plot(plot_widget, x_label=None, y_label=None):
    """
    The plots of the design: white, light grid, grey axes with their
    numbers in the monospaced font.
    """
    import pyqtgraph as pg
    plot_widget.setBackground(SURFACE)
    item = plot_widget.getPlotItem()
    item.showGrid(x=True, y=True, alpha=0.35)
    tick_font = mono(8.5)
    for name in ("bottom", "left"):
        axis = item.getAxis(name)
        axis.setPen(pg.mkPen(LINE))
        axis.setTextPen(pg.mkPen(MUTED))
        axis.setTickFont(tick_font)
        axis.setStyle(tickLength=-4)
    if x_label:
        item.setLabel("bottom", x_label, color=MUTED)
    if y_label:
        item.setLabel("left", y_label, color=MUTED)
    return item


def qcolor(value, alpha=255):
    color = QColor(value)
    color.setAlpha(alpha)
    return color


def swatches(items):
    """
    A legend in one line of rich text: (kind, colour, text), kind "line",
    "dash" or "box".
    """
    parts = []
    for kind, color, text in items:
        mark = {"line": "━━", "dash": "╍╍", "box": "■"}[kind]
        parts.append('<span style="color: {0}; font-weight: 600">{1}</span>'
                     '&nbsp;<span style="color: {2}">{3}</span>'.format(
                         color, mark, MUTED, text))
    return "&nbsp;&nbsp;&nbsp;&nbsp;".join(parts)


# The look of the matplotlib figures on the screens (matplotlib_style adds
# the fonts)
MATPLOTLIB = {
    "font.family": "sans-serif",
    "font.size": 9.0,
    "axes.edgecolor": FIELD_LINE,
    "axes.labelcolor": MUTED,
    "axes.titlecolor": INK,
    "axes.grid": True,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "legend.frameon": False,
}


def matplotlib_style():
    """
    MATPLOTLIB with the first fonts of SANS that matplotlib has: it warns
    about each family that it cannot find.
    """
    from matplotlib import font_manager
    have = {f.name for f in font_manager.fontManager.ttflist}
    style = dict(MATPLOTLIB)
    style["font.sans-serif"] = [f for f in SANS if f in have] + [
        "DejaVu Sans"]
    return style
