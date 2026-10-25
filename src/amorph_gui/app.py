"""
The Qt application of the GUI, in the look of theme.py.
"""

import matplotlib

# The figures are drawn on canvases of their own: pyplot, which
# dnest_functions imports, must never open windows
matplotlib.use("Agg")

import pyqtgraph as pg  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from amorph_gui import strings as S  # noqa: E402
from amorph_gui import theme  # noqa: E402


def application(argv=None):
    """
    The QApplication, made if there is none yet.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv else ["amorph_gui"])
    app.setApplicationName(S.APP_NAME)
    app.setOrganizationName("AMORPH")
    # Fusion draws the same on every system, under the style sheet
    app.setStyle("Fusion")
    app.setFont(theme.sans())
    app.setStyleSheet(theme.STYLE_SHEET)
    pg.setConfigOptions(antialias=True, background=theme.SURFACE,
                        foreground=theme.MUTED)
    return app
