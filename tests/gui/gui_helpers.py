"""
Helpers of the tests of the GUI that do not need Qt.
"""

import os

import yaml

import amorph_archive
import amorph_results

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "src")


def full_config(seed, nu=(1.0, 100.0)):
    """
    A config.yaml of every key, for the data of the fake run of
    tests/test_results.py.
    """
    return {"num_threads": 2, "data_file": "demo_data.txt",
            "dnest4_options_file": "OPTIONS", "seed": seed,
            "inference_assumptions": {
                "control_points": [34.0, 45.0],
                "max_num_narrow_peaks": 20, "max_num_wide_peaks": 10,
                "left_edge": 0.3, "right_edge": 0.7,
                "narrow_peak_nu": list(nu)}}


def write_archive(folder, out, seed, nu=(1.0, 100.0)):
    """
    Give the run in folder a config.yaml of every key (full_config) and the
    options file it names, and write its archive to out.
    """
    with open(os.path.join(folder, "config.yaml"), "w") as f:
        yaml.safe_dump(full_config(seed, nu), f)
    with open(os.path.join(SRC, "OPTIONS")) as f, \
            open(os.path.join(folder, "OPTIONS"), "w") as g:
        g.write(f.read())
    return amorph_archive.write(amorph_results.from_run(folder), out)
