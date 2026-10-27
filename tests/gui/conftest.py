"""
Fixtures of the tests of the graphical interface (src/amorph_gui). They
need PySide6, pyqtgraph and pytest-qt, and run without a screen:

    QT_QPA_PLATFORM=offscreen python -m pytest tests/gui

Without PySide6, pyqtgraph or pytest-qt they are skipped, so that
`python -m pytest tests` works with the packages of the post-processing
alone.
"""

import os
import shutil
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")
for path in (SRC, os.path.join(ROOT, "tests"),
             os.path.join(ROOT, "tests", "gui")):
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    import PySide6.QtWidgets  # noqa: F401
    import pyqtgraph  # noqa: F401
    import pytestqt  # noqa: F401
except ImportError:
    collect_ignore_glob = ["test_*.py"]
else:
    import gc

    import pytest
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings

    # Before anything imports pyplot
    import amorph_gui.app

    import amorph_archive
    import amorph_results
    from gui_helpers import write_archive
    from test_results import make_full_run

    from amorph_gui.main_window import MainWindow
    from amorph_gui.preferences import Preferences

    @pytest.fixture
    def prefs(tmp_path):
        store = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
        return Preferences(store, runs=str(tmp_path / "runs"))

    @pytest.fixture
    def window(qtbot, prefs):
        amorph_gui.app.application()
        w = MainWindow(prefs, headless=True)
        qtbot.addWidget(w)
        w.resize(1360, 860)
        w.show()
        yield w
        w.close()
        # Delete the window here, in the GUI thread. Its screens hold
        # lambdas that refer to them, so left to the garbage collector it
        # could be deleted in whatever thread collects next: a worker that
        # reads an archive in a later test, which crashes Qt.
        w.tasks.wait()
        w.queue.post_tasks.wait()
        w.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        gc.collect()

    @pytest.fixture(scope="module")
    def fake_run(tmp_path_factory):
        """
        The fake run of tests/test_results.py: (folder, column names, rows
        of sample.txt).
        """
        folder = str(tmp_path_factory.mktemp("fake_run"))
        names, rows = make_full_run(folder)
        return folder, names, rows

    @pytest.fixture(scope="module")
    def archives(fake_run, tmp_path_factory):
        """
        Two archives of the fake run, with seeds 5 and 6 and different
        ranges of nu, and the archive that from_run writes with the
        config.yaml of the fake run as it is.
        """
        out = tmp_path_factory.mktemp("archives")
        folder = str(out / "run")
        shutil.copytree(fake_run[0], folder)
        plain = amorph_archive.write(amorph_results.from_run(folder),
                                     str(out / "plain.amorph"))
        first = write_archive(folder, str(out / "seed5.amorph"), 5)
        second = write_archive(folder, str(out / "seed6.amorph"), 6,
                               nu=(0.1, 100.0))
        return {"plain": plain, "seed5": first, "seed6": second}
