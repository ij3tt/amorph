"""
The splash screen of the GUI. It shows as soon as Qt is up, before the
rest of the program loads: numpy, pandas, matplotlib, pyqtgraph and the
screens. That takes a few seconds, and the first start of a newly unpacked
package can take a minute while the system (Microsoft Defender on Windows,
Gatekeeper on macOS) checks every file of it: without a window, the
program looked as if it had not started, and was started again.

This module imports Qt only, so that the splash comes first:

    splash = show_splash(sys.argv)
    splash.set_step(S.SPLASH_LIBRARIES)
    ... import the rest, make the window ...
    splash.finish(window)
"""

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from amorph_gui import strings as S
from amorph_gui import theme

# The size of the splash, in points
SIZE = QSize(520, 250)


def splash_pixmap(ratio=1.0):
    """
    The picture of the splash, for a screen of device pixel ratio ratio: the
    mark and the name of AMORPH, what it is, and the note on the first
    start. The step under way is drawn over it (Splash.drawContents).
    """
    pixmap = QPixmap(int(SIZE.width() * ratio), int(SIZE.height() * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QColor(theme.SURFACE))
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setPen(QPen(QColor(theme.LINE), 1))
    p.drawRect(QRectF(0.5, 0.5, SIZE.width() - 1, SIZE.height() - 1))

    p.save()
    p.translate(28, 28)
    theme.paint_logo(p, 2.0)
    p.restore()

    p.setPen(QColor(theme.INK))
    p.setFont(theme.sans(20.0, QFont.Weight.DemiBold))
    p.drawText(QRectF(92, 26, 400, 34), Qt.AlignLeft | Qt.AlignVCenter,
               S.APP_NAME)
    p.setPen(QColor(theme.MUTED))
    p.setFont(theme.sans(10.0))
    p.drawText(QRectF(92, 60, 400, 22), Qt.AlignLeft | Qt.AlignVCenter,
               S.SPLASH_SUBTITLE)

    p.setPen(QPen(QColor(theme.LINE), 1))
    p.drawLine(28, 104, SIZE.width() - 28, 104)

    p.setPen(QColor(theme.MUTED))
    p.setFont(theme.sans(9.0))
    p.drawText(QRectF(28, 170, SIZE.width() - 56, 60),
               Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, S.SPLASH_NOTE)
    p.end()
    return pixmap


class Splash(QSplashScreen):
    """
    The splash: its picture, with the step under way in the accent colour.
    """

    def __init__(self, pixmap):
        super().__init__(pixmap, Qt.WindowStaysOnTopHint)
        self.step = S.SPLASH_STARTING

    def set_step(self, text):
        """
        Show text as the step under way, and draw it at once: the program
        is busy loading, not in its event loop.
        """
        self.step = text
        self.repaint()
        QApplication.processEvents()

    def drawContents(self, painter):
        painter.setPen(QColor(theme.ACCENT))
        painter.setFont(theme.sans(11.0, QFont.Weight.DemiBold))
        painter.drawText(QRectF(28, 118, SIZE.width() - 56, 40),
                         Qt.AlignLeft | Qt.AlignVCenter, self.step)


def show_splash(argv=None):
    """
    Make the QApplication, if there is none yet, as amorph_gui.app does,
    and show the splash on it. Returns the splash.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(list(argv) if argv else ["amorph_gui"])
    screen = app.primaryScreen()
    ratio = screen.devicePixelRatio() if screen is not None else 1.0
    splash = Splash(splash_pixmap(ratio))
    splash.show()
    splash.set_step(S.SPLASH_STARTING)
    return splash
