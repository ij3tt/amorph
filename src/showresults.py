# Uses actual DNest4 stuff if it's installed - otherwise
# uses dnest_functions.py as a fallback
try:
    import dnest4.classic as dn4
except ImportError:
    import dnest_functions as dn4

import numpy as np

import amorph_stats

# The post-processing resamples the saved particles at random: seed it, so
# that the same run always gives the same posterior samples
np.random.seed(amorph_stats.postprocessing_seed("config.yaml"))

# Writes posterior_sample.txt. Its figures and numbers are part of the
# report of display.py.
dn4.postprocess(plot=False, verbose=False)

import display
display.display()
