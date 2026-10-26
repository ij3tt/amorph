"""
Runs opened from their folders (src/amorph_gui/runfiles.py) and the
estimate of a run that has ended (live.replay), on the fake run of
test_results.py. They do not need Qt. Run with pytest from the repository
root:

    python -m pytest tests
"""

import os
import shutil
import sys
import time

import pytest
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import amorph_archive
import amorph_results
import amorph_stats
from amorph_gui import live, runfiles
from test_results import make_full_run

QUANTILES = ["q05", "q25", "q50", "q75", "q95"]

CONFIG = {"num_threads": 2, "data_file": "demo_data.txt",
          "dnest4_options_file": "OPTIONS", "seed": 7,
          "inference_assumptions": {
              "control_points": [34.0, 45.0], "max_num_narrow_peaks": 20,
              "max_num_wide_peaks": 10, "left_edge": 0.3,
              "right_edge": 0.7, "narrow_peak_nu": [1.0, 100.0]}}


@pytest.fixture(scope="module")
def finished(tmp_path_factory):
    """
    The fake run with the config.yaml and the options file of a run of the
    GUI, without its archive: (folder, rows of sample.txt).
    """
    folder = str(tmp_path_factory.mktemp("finished"))
    _, rows = make_full_run(folder)
    with open(os.path.join(folder, "config.yaml"), "w") as f:
        yaml.safe_dump(CONFIG, f)
    shutil.copyfile(os.path.join(ROOT, "src", "OPTIONS"),
                    os.path.join(folder, "OPTIONS"))
    return folder, rows


def copy_run(finished, to):
    shutil.copytree(finished[0], str(to))
    return str(to)


def test_run_folders_are_found(finished, tmp_path):
    top = tmp_path / "results"
    first = copy_run(finished, top / "2026-10-26_N3RAW_seed1")
    second = copy_run(finished, top / "deeper" / "2026-10-26_N3RAW_seed2")
    (top / "notes").mkdir()
    loose = top / "ci" / "run.amorph"
    loose.parent.mkdir()
    loose.write_bytes(b"")
    assert runfiles.is_run_folder(first)
    assert not runfiles.is_run_folder(str(top))
    assert runfiles.run_folders(first) == [os.path.abspath(first)]
    assert runfiles.run_folders(str(top)) == sorted(
        [os.path.abspath(first), os.path.abspath(second)])
    # Not deeper than asked
    assert runfiles.run_folders(str(top), depth=1) == [os.path.abspath(first)]
    assert runfiles.run_folders(str(top / "notes")) == []
    # Archives of a run folder belong to it; the others are loose
    (top / "2026-10-26_N3RAW_seed1" / "x.amorph").write_bytes(b"")
    assert runfiles.loose_archives(str(top)) == [str(loose)]


def test_a_run_is_opened_and_archived_once(finished, tmp_path):
    folder = copy_run(finished, tmp_path / "run")
    assert runfiles.current_archive(folder) is None
    info = runfiles.open_run(folder)
    assert info["seed"] == 7
    # The planned saves of the options file of the folder
    with open(os.path.join(folder, "OPTIONS")) as f:
        assert str(info["planned"]) in f.read()
    rows = finished[1]
    assert info["saves"] == len(rows) and info["levels"] == 4
    x, _ = amorph_stats.load_data(os.path.join(folder, "demo_data.txt"))
    assert (info["x"] == x).all()
    # Post-processed, with an archive that the next opening reads
    archive = info["archive"]
    assert os.path.isfile(archive) and os.path.dirname(archive) == folder
    assert os.path.isfile(os.path.join(folder, "posterior_sample.txt"))
    assert runfiles.current_archive(folder) == archive
    again = runfiles.open_run(folder)
    assert again["archive"] == archive
    assert again["results"].diagnosis["fraction"] == pytest.approx(
        info["results"].diagnosis["fraction"])
    # A save after the archive makes it out of date
    later = time.time() + 10
    os.utime(os.path.join(folder, "sample_info.txt"), (later, later))
    assert runfiles.current_archive(folder) is None


def test_the_estimate_of_a_run_that_has_ended(finished, tmp_path):
    folder = copy_run(finished, tmp_path / "run")
    x, _ = amorph_stats.load_data(os.path.join(folder, "demo_data.txt"))
    e = live.replay(folder, x, steps=4)
    rows = finished[1]
    assert e["saves"] == len(rows)
    assert len(e["trace"]) == 4
    assert [row[0] for row in e["trace"]] == [15, 30, 45, 60]
    d = amorph_results.from_run(folder).diagnosis["fraction"]
    assert e["quantiles"] == pytest.approx([d[q] for q in QUANTILES],
                                           abs=1E-12)
    assert "mean" in e and "band" in e
    # The file is closed again
    os.rename(os.path.join(folder, "sample.txt"),
              os.path.join(folder, "moved.txt"))


def test_an_archive_is_read_as_it_is(finished, tmp_path):
    folder = copy_run(finished, tmp_path / "run")
    results = amorph_results.from_run(folder)
    archive = amorph_archive.write(results,
                                   os.path.join(folder, "run.amorph"))
    before = os.path.getmtime(archive)
    info = runfiles.open_run(folder)
    # Read, not written again by a new post-processing
    assert info["archive"] == archive
    assert os.path.getmtime(archive) == before
    assert info["results"].diagnosis["fraction"] == pytest.approx(
        results.diagnosis["fraction"])
