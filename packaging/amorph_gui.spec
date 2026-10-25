# -*- mode: python -*-
#
# PyInstaller spec of the GUI of AMORPH: one folder, AMORPH-GUI, with the
# program, Python, Qt, the packages of the post-processing, the sampler and
# the files the GUI reads next to it (config.yaml, the DNest4 options and
# easy_data.txt); on macOS also the app AMORPH-GUI.app. Build it from the
# root of the repository with the sampler of the same system:
#
#     AMORPH_BIN=path/to/AMORPH pyinstaller packaging/amorph_gui.spec
#
# scripts/ci/gui_package.sh does this in CI. The GUI looks for the sampler
# next to itself (amorph_gui.preferences.search_folders), so it runs the one
# packed with it.

import os
import sys

from PyInstaller.utils.hooks import collect_submodules, copy_metadata

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

sampler = os.environ.get("AMORPH_BIN")
if not sampler or not os.path.isfile(sampler):
    raise SystemExit("amorph_gui.spec: set AMORPH_BIN to the AMORPH "
                     "executable to pack, not {0!r}".format(sampler))

# What the GUI reads from its folder (amorph_gui.SRC_DIR)
datas = [(os.path.join(SRC, name), ".")
         for name in ("config.yaml", "OPTIONS", "OPTIONS_AGGRESSIVE",
                      "easy_data.txt")]
# The licences of the bundled packages are in their metadata
for package in ("PySide6_Essentials", "shiboken6", "pyqtgraph", "numpy",
                "matplotlib", "pandas", "PyYAML"):
    try:
        datas += copy_metadata(package)
    except Exception:
        print("amorph_gui.spec: no metadata of " + package)

a = Analysis(
    [os.path.join(SPECPATH, "amorph_gui_app.py")],
    pathex=[SRC],
    binaries=[(sampler, ".")],
    datas=datas,
    hiddenimports=collect_submodules("amorph_gui")
    + ["amorph_stats", "amorph_results", "amorph_archive", "dnest_functions"],
    excludes=["tkinter", "IPython", "PyQt5", "PyQt6", "PySide2", "pytest"],
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AMORPH-GUI",
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="AMORPH-GUI")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="AMORPH-GUI.app",
        bundle_identifier="io.github.ij3tt.amorph-gui",
        info_plist={"CFBundleName": "AMORPH", "CFBundleDisplayName": "AMORPH",
                    "NSHighResolutionCapable": True},
    )
