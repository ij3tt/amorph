"""
The entry point of the packaged GUI of AMORPH (packaging/amorph_gui.spec):
what `python -m amorph_gui` runs from src/.

A program built without a console (Windows) has no standard output: print
would fail. Its output then goes to the file AMORPH_GUI_LOG names, or to
amorph_gui.log in the temporary folder.
"""

import os
import sys
import tempfile

if sys.stdout is None or sys.stderr is None:
    log = open(os.environ.get("AMORPH_GUI_LOG")
               or os.path.join(tempfile.gettempdir(), "amorph_gui.log"),
               "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or log
    sys.stderr = sys.stderr or log

from amorph_gui.__main__ import main  # noqa: E402

sys.exit(main())
