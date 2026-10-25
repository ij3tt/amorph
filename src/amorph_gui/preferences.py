"""
The settings of the program itself, kept by QSettings: which AMORPH
executable to run and the folder of the runs. Without a path in the
settings, the sampler is looked for next to the GUI, in a CMake build of
the repository and on PATH.
"""

import os
import shutil
import sys

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QWidget)

from amorph_gui import SRC_DIR
from amorph_gui import strings as S


def executable_names():
    return ("AMORPH.exe", "AMORPH") if os.name == "nt" else ("AMORPH",)


def search_folders():
    """
    Where the sampler is looked for: next to the GUI (src/, or the folder of
    a packaged program) and in build/ of the repository.
    """
    folders = [SRC_DIR]
    if getattr(sys, "frozen", False):
        folders.insert(0, os.path.dirname(sys.executable))
    folders.append(os.path.join(os.path.dirname(SRC_DIR), "build"))
    return folders


def _runnable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


def find_amorph(configured=""):
    """
    The AMORPH executable: the one in the settings if any (None if it does
    not exist), otherwise the first found next to the GUI or on PATH.
    """
    if configured:
        return os.path.abspath(configured) if _runnable(configured) else None
    for folder in search_folders():
        for name in executable_names():
            path = os.path.join(folder, name)
            if _runnable(path):
                return path
    for name in executable_names():
        path = shutil.which(name)
        if path:
            return path
    return None


class Preferences(object):
    """
    The settings of the program. amorph and runs given here (from the
    command line) take the place of the stored ones, without storing them.
    """

    def __init__(self, store=None, amorph=None, runs=None):
        self.store = store if store is not None \
            else QSettings("AMORPH", "AMORPH GUI")
        self._amorph = amorph
        self._runs = runs

    @property
    def amorph(self):
        if self._amorph is not None:
            return self._amorph
        return str(self.store.value("amorph_executable", "") or "")

    @amorph.setter
    def amorph(self, path):
        self._amorph = None
        self.store.setValue("amorph_executable", path)

    @property
    def runs_folder(self):
        if self._runs is not None:
            return self._runs
        return str(self.store.value("runs_folder", "") or "") \
            or os.path.join(os.getcwd(), "runs")

    @runs_folder.setter
    def runs_folder(self, path):
        self._runs = None
        self.store.setValue("runs_folder", path)


class PreferencesDialog(QDialog):

    def __init__(self, preferences, parent=None):
        super().__init__(parent)
        self.preferences = preferences
        self.setWindowTitle(S.PREFERENCES_TITLE)
        self.setMinimumWidth(620)
        layout = QFormLayout(self)

        self.amorph = QLineEdit(preferences.amorph)
        self.amorph.setPlaceholderText(", ".join(search_folders()))
        self.amorph.setToolTip(S.PREF_AMORPH_TIP.format(
            ", ".join(search_folders())))
        self.amorph.textChanged.connect(self._update)
        layout.addRow(S.PREF_AMORPH, self._with_browse(self.amorph,
                                                       self._browse_amorph))
        self.found = QLabel()
        self.found.setWordWrap(True)
        layout.addRow("", self.found)

        self.runs = QLineEdit(preferences.runs_folder)
        self.runs.setToolTip(S.PREF_RUNS_TIP)
        layout.addRow(S.PREF_RUNS, self._with_browse(self.runs,
                                                     self._browse_runs))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok
                                   | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self._update()

    def _with_browse(self, edit, slot):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(edit, 1)
        button = QPushButton(S.BROWSE)
        button.clicked.connect(slot)
        layout.addWidget(button)
        return row

    def _browse_amorph(self):
        path, _ = QFileDialog.getOpenFileName(self, S.PREF_AMORPH)
        if path:
            self.amorph.setText(path)

    def _browse_runs(self):
        path = QFileDialog.getExistingDirectory(self, S.PREF_RUNS,
                                                self.runs.text())
        if path:
            self.runs.setText(path)

    def _update(self):
        path = find_amorph(self.amorph.text().strip())
        self.found.setText(S.PREF_AMORPH_FOUND.format(path) if path
                           else S.PREF_AMORPH_MISSING)

    def accept(self):
        self.preferences.amorph = self.amorph.text().strip()
        self.preferences.runs_folder = self.runs.text().strip()
        super().accept()
