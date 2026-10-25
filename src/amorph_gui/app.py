"""
The Qt application of the GUI.
"""

import matplotlib

# The figures are drawn on canvases of their own: pyplot, which
# dnest_functions imports, must never open windows
matplotlib.use("Agg")

import pyqtgraph as pg  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from amorph_gui import strings as S  # noqa: E402


def application(argv=None):
    """
    The QApplication, made if there is none yet.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv else ["amorph_gui"])
    app.setApplicationName(S.APP_NAME)
    app.setOrganizationName("AMORPH")
    pg.setConfigOptions(antialias=True, background="w", foreground="k")
    return app
