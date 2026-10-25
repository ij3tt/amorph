"""
The form of «Данные и модель» and config.yaml: what the form writes reads
back unchanged, and reading a config.yaml applies the limits of
Config.cpp.
"""

import os

import pytest
import yaml

from amorph_gui import config

from gui_helpers import SRC


def read_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


def test_form_writes_the_bundled_config_back_unchanged(window, tmp_path):
    form = window.data_screen
    assert form.load_config(os.path.join(SRC, "config.yaml"))
    # Its data file is next to it, and opened with it
    assert form.data_path == os.path.join(SRC, "easy_data.txt")
    out = str(tmp_path / "config.yaml")
    form.save_config(out)
    assert read_yaml(out) == read_yaml(os.path.join(SRC, "config.yaml"))
    # It has nu from 0.1: a warning, not an error
    assert any("ν" in w for w in form.warnings())
    assert not form.errors()


def test_form_reads_back_what_it_wrote(window, tmp_path):
    form = window.data_screen
    s = config.Settings(num_threads=3, data_file="my data.txt",
                        dnest4_options_file="OPTIONS", seed=4294967290,
                        control_points=(12.5, 37.25),
                        max_num_narrow_peaks=123, max_num_wide_peaks=45,
                        left_edge=0.25, right_edge=0.75,
                        narrow_peak_nu=(1.5, 80.0), max_saves=5000)
    form.set_settings(s)
    first = str(tmp_path / "first.yaml")
    form.save_config(first)
    assert config.read_config(first)[0] == config.Settings(
        **dict(vars(s), max_saves=config.Settings().max_saves))

    # Into the form and out again: the same file
    form.set_settings(config.default_settings())
    assert form.load_config(first)
    second = str(tmp_path / "second.yaml")
    form.save_config(second)
    with open(first) as f, open(second) as g:
        assert f.read() == g.read()
    got = form.settings()
    for key in ("num_threads", "data_file", "dnest4_options_file", "seed",
                "control_points", "max_num_narrow_peaks",
                "max_num_wide_peaks", "left_edge", "right_edge",
                "narrow_peak_nu"):
        assert getattr(got, key) == getattr(s, key), key


def test_without_a_seed_the_key_is_left_out(tmp_path):
    path = str(tmp_path / "config.yaml")
    config.write_config(config.Settings(seed=None), path)
    assert "seed" not in read_yaml(path)
    config.write_config(config.Settings(seed=0), path)
    assert read_yaml(path)["seed"] == 0


def test_numbers_are_written_so_that_yaml_reads_them_back(tmp_path):
    path = str(tmp_path / "config.yaml")
    s = config.Settings(control_points=(1E-5, 3E20), left_edge=0.1,
                        right_edge=1.0)
    config.write_config(s, path)
    back = config.read_config(path)[0]
    assert back.control_points == s.control_points
    assert back.left_edge == 0.1 and back.right_edge == 1.0


BUNDLED = read_yaml(os.path.join(SRC, "config.yaml"))


def changed(path, value):
    c = yaml.safe_load(yaml.safe_dump(BUNDLED))
    *groups, key = path.split(".")
    target = c
    for g in groups:
        target = target[g]
    if value is None:
        del target[key]
    else:
        target[key] = value
    return c


@pytest.mark.parametrize("path, value, key", [
    ("num_threads", 0, "'num_threads'"),
    ("num_threads", 2.5, "'num_threads'"),
    ("data_file", None, "'data_file'"),
    ("inference_assumptions", None, "'inference_assumptions'"),
    ("inference_assumptions.control_points", [40.0, 10.0],
     "'inference_assumptions.control_points'"),
    ("inference_assumptions.control_points", [10.0],
     "'inference_assumptions.control_points'"),
    ("inference_assumptions.max_num_narrow_peaks", 0,
     "'inference_assumptions.max_num_narrow_peaks'"),
    ("inference_assumptions.left_edge", -0.1, "left_edge"),
    ("inference_assumptions.right_edge", 1.5, "right_edge"),
    ("inference_assumptions.right_edge", 0.2, "right_edge"),
    ("inference_assumptions.narrow_peak_nu", [0.05, 100.0],
     "'inference_assumptions.narrow_peak_nu'"),
    ("inference_assumptions.narrow_peak_nu", [10.0, 1.0],
     "'inference_assumptions.narrow_peak_nu'"),
    ("seed", -1, "'seed'"),
    ("seed", 4294967296, "'seed'"),
    ("seed", True, "'seed'"),
])
def test_reading_applies_the_limits_of_config_cpp(path, value, key):
    with pytest.raises(config.ConfigError) as e:
        config.settings_from_config(changed(path, value), "config.yaml")
    assert str(e.value).startswith("config.yaml: ")
    assert key in str(e.value)


def test_optional_keys_take_the_defaults_of_the_sampler():
    s = config.settings_from_config(
        changed("inference_assumptions.narrow_peak_nu", None))
    assert s.narrow_peak_nu == (0.1, 100.0)
    assert s.seed is None


def test_form_shows_an_invalid_config(window, tmp_path):
    path = str(tmp_path / "config.yaml")
    with open(path, "w") as f:
        yaml.safe_dump(changed("num_threads", 0), f)
    before = window.data_screen.settings()
    assert not window.data_screen.load_config(path)
    assert window.data_screen.banner.isVisible()
    assert "'num_threads'" in window.data_screen.banner.text()
    assert window.data_screen.settings() == before


def test_options_file_keeps_everything_but_the_maximum_of_saves():
    for name, text in config.options_templates().items():
        assert config.options_max_saves(text) == 10000
        changed_text = config.options_with_max_saves(text, 250)
        assert config.options_max_saves(changed_text) == 250
        old, new = text.splitlines(), changed_text.splitlines()
        assert len(old) == len(new)
        assert sum(a != b for a, b in zip(old, new)) == 1
        assert new[9] == "250\t# Maximum number of saves (0 = infinite)"


def test_choosing_an_options_file_takes_its_maximum_of_saves(window):
    form = window.data_screen
    form.add_options("OPTIONS_TINY", config.options_with_max_saves(
        form.templates["OPTIONS"], 77))
    form.options.setCurrentText("OPTIONS_TINY")
    assert form.max_saves.value() == 77
    assert form.settings().max_saves == 77
