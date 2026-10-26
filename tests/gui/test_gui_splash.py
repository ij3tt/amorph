"""
The splash screen that shows while the GUI loads (amorph_gui.splash), and
the start of the GUI with it (python -m amorph_gui).
"""

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

import amorph_gui.app

from amorph_gui import __main__ as start
from amorph_gui import splash as SP
from amorph_gui import strings as S
from amorph_gui import theme
from amorph_gui.main_window import MainWindow


def has_color(image, ratio, xs, ys, color, tolerance=40):
    """
    Whether a pixel of image within the points xs by ys is near color:
    antialiased text has few pixels of exactly its colour.
    """
    want = QColor(color)
    for x in xs:
        for y in ys:
            c = image.pixelColor(int(x * ratio), int(y * ratio))
            if abs(c.red() - want.red()) + abs(c.green() - want.green()) \
                    + abs(c.blue() - want.blue()) <= tolerance:
                return True
    return False


def test_the_splash_shows_its_steps_and_goes(qtbot, window):
    shown = SP.show_splash()
    qtbot.addWidget(shown)
    assert shown.isVisible()
    assert shown.step == S.SPLASH_STARTING
    shown.set_step(S.SPLASH_SCREENS)
    assert shown.step == S.SPLASH_SCREENS
    # The step is drawn in the accent colour
    image = shown.grab().toImage()
    ratio = image.devicePixelRatio()
    assert has_color(image, ratio, range(28, 300), range(120, 156),
                     theme.ACCENT)
    shown.finish(window)
    qtbot.waitUntil(lambda: not shown.isVisible(), timeout=5000)


def test_the_picture_of_the_splash():
    amorph_gui.app.application()
    for ratio in (1.0, 2.0):
        pixmap = SP.splash_pixmap(ratio)
        assert pixmap.width() == int(SP.SIZE.width() * ratio)
        assert pixmap.height() == int(SP.SIZE.height() * ratio)
        image = pixmap.toImage()
        # The mark of AMORPH, in ink, on white
        assert has_color(image, ratio, range(28, 76), range(28, 76),
                         theme.INK)
        assert has_color(image, ratio, range(28, 76), range(28, 76),
                         theme.SURFACE, tolerance=0)


def test_the_gui_starts_with_the_splash(qtbot, tmp_path, monkeypatch):
    # What is on the screen when the event loop would start: the window of
    # main() is gone once main() returns. The loop would wait for the
    # window to close, so close it here.
    seen = {}

    def event_loop(self):
        top = QApplication.topLevelWidgets()
        seen["windows"] = [w for w in top if isinstance(w, MainWindow)
                           and w.isVisible()]
        seen["splashes"] = [w for w in top if isinstance(w, SP.Splash)
                            and w.isVisible()]
        for w in seen["windows"]:
            w.close()
        return 0

    monkeypatch.setattr(QApplication, "exec", event_loop)
    assert start.main(["--runs", str(tmp_path / "runs")]) == 0
    assert len(seen["windows"]) == 1
    # finish() closed the splash once the window was shown
    assert seen["splashes"] == []
