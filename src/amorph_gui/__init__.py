"""
The graphical interface of AMORPH: open a data file, choose the range and
the settings, run the sampler for one or more seeds, and look at the
results and compare runs. Start it from src/ with

    python -m amorph_gui

It needs PySide6, pyqtgraph and matplotlib besides what the post-processing
needs. The numbers and figures come from amorph_stats, amorph_results,
amorph_archive and dnest_functions; this package only shows them. All the
text of the interface is in strings.py.
"""

import os

# The folder of the GUI: src/, with the bundled data, config.yaml and the
# DNest4 options files
SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
