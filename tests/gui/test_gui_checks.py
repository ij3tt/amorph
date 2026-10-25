"""
The checks before a run, the plot of «Данные и модель», and the folder of
a run with the analysed part of the data.
"""

import datetime
import os

import numpy as np
import pytest

import amorph_stats

from amorph_gui import config, runfiles

from gui_helpers import SRC

EASY = os.path.join(SRC, "easy_data.txt")


def with_settings(form, **changes):
    s = form.settings()
    for key, value in changes.items():
        setattr(s, key, value)
    form.set_settings(s)
    return form


@pytest.fixture
def form(window):
    assert window.data_screen.open_data(EASY)
    return with_settings(window.data_screen, narrow_peak_nu=(1.0, 100.0))


def test_default_settings_pass(form):
    # easy_data.txt runs from 0 to 50, the control points are 10 and 40
    assert form.problems == []
    assert form.run_button.isEnabled()


def test_control_points_must_lie_in_the_analysed_range(form):
    with_settings(form, x_range=(12.0, 46.0), control_points=(10.0, 40.0))
    errors = form.errors()
    assert len(errors) == 1 and "(10, 40)" in errors[0]
    assert "12" in errors[0] and "46" in errors[0]
    assert not form.run_button.isEnabled()

    with_settings(form, control_points=(14.0, 40.0))
    assert not form.errors()
    assert form.run_button.isEnabled()


def test_data_must_reach_beyond_the_control_points(form):
    # On the edges of the analysed data: allowed, with a warning per side
    with_settings(form, x_range=(10.0, 40.0), control_points=(10.0, 40.0))
    assert not form.errors()
    warnings = form.warnings()
    assert len(warnings) == 2
    assert "10" in warnings[0] and "40" in warnings[1]
    assert form.run_button.isEnabled()

    with_settings(form, control_points=(10.0, 38.0))
    assert len(form.warnings()) == 1

    with_settings(form, control_points=(12.0, 38.0))
    assert not form.warnings()


def test_nu_below_1_gives_a_warning(form):
    with_settings(form, narrow_peak_nu=(0.1, 100.0))
    assert not form.errors()
    assert len(form.warnings()) == 1 and "0.1" in form.warnings()[0]
    assert "✖" not in form.checks.text() and "▲" in form.checks.text()

    with_settings(form, narrow_peak_nu=(1.0, 100.0))
    assert not form.warnings()
    assert "✔" in form.checks.text()


def test_other_checks():
    x = np.linspace(0.0, 50.0, 1001)
    s = config.Settings(narrow_peak_nu=(1.0, 100.0))
    assert config.check(s, x) == []

    def levels(**changes):
        t = config.Settings(**dict(vars(s), **changes))
        return [level for level, _ in config.check(t, x)]

    assert levels() == []
    assert levels(x_range=(20.0, 20.1)) == [config.ERROR]
    assert levels(x_range=(30.0, 20.0)) == [config.ERROR]
    assert levels(control_points=(40.0, 10.0))[0] == config.ERROR
    assert levels(left_edge=0.7, right_edge=0.3) == [config.ERROR]
    assert levels(seed=config.MAX_SEED, num_seeds=2) == [config.ERROR]
    assert levels(max_saves=0) == [config.WARNING]
    assert config.check(s, None) == [(config.ERROR, config.S.CHECK_NO_DATA)]


def test_the_plot_and_the_form_move_together(form):
    form.region.setRegion((5.0, 45.0))
    assert form.range_lo.value() == pytest.approx(5.0)
    assert form.range_hi.value() == pytest.approx(45.0)
    assert form.settings().x_range == pytest.approx((5.0, 45.0))

    form.cp_lines[0].setValue(12.0)
    assert form.cp1.value() == pytest.approx(12.0)
    form.cp2.setValue(38.0)
    assert form.cp_lines[1].value() == pytest.approx(38.0)

    # The band of the wide peaks: left_edge and right_edge of the analysed
    # points, as the sampler places it
    form.left_edge.setValue(0.25)
    x = form.x[(form.x >= 5.0) & (form.x <= 45.0)]
    assert form.band.getRegion() == pytest.approx(
        (x[0] + 0.25 * (x[-1] - x[0]), x[0] + 0.7 * (x[-1] - x[0])))

    # The whole data: no range to cut
    form.region.setRegion((form.x[0], form.x[-1]))
    assert form.settings().x_range is None


def test_errors_of_the_data_file_name_the_file_and_the_line(window,
                                                            tmp_path):
    path = tmp_path / "bad.txt"
    path.write_text("# comment\n10.0 1.0\n10.02 abc\n")
    assert not window.data_screen.open_data(str(path))
    text = window.data_screen.banner.text()
    assert window.data_screen.banner.isVisible()
    assert "bad.txt, line 3" in text and "10.02 abc" in text
    assert window.data_screen.x is None
    assert not window.data_screen.run_button.isEnabled()


def test_run_folder_has_the_analysed_data(tmp_path):
    x, y = amorph_stats.load_data(EASY)
    s = config.Settings(x_range=(5.0, 45.0), max_saves=250, seed=None)
    template = config.options_templates()["OPTIONS_AGGRESSIVE"]
    when = datetime.datetime(2026, 10, 25, 15, 30)
    folder = runfiles.prepare_run(str(tmp_path), s, "/data/Образец 1.txt",
                                  x, y, 7, template, when)
    assert os.path.basename(folder) == "2026-10-25_1530_Obrazets_1_seed7"
    again = runfiles.prepare_run(str(tmp_path), s, "/data/Образец 1.txt",
                                 x, y, 7, template, when)
    assert again == folder + "_2"

    settings, options = config.read_config(os.path.join(folder,
                                                        "config.yaml"))
    assert settings.seed == 7
    assert settings.data_file == "Obrazets_1.txt"
    assert settings.max_saves == 250
    assert options == config.options_with_max_saves(template, 250)
    cut_x, cut_y = amorph_stats.load_data(os.path.join(folder,
                                                       settings.data_file))
    keep = (x >= 5.0) & (x <= 45.0)
    np.testing.assert_array_equal(cut_x, x[keep])
    np.testing.assert_array_equal(cut_y, y[keep])


def test_seeds_of_the_runs():
    assert config.run_seeds(config.Settings(seed=4, num_seeds=3), 0) == \
        [4, 5, 6]
    seeds = config.run_seeds(config.Settings(seed=None, num_seeds=2),
                             config.MAX_SEED + 10)
    assert seeds == [9, 10]
    seeds = config.run_seeds(config.Settings(seed=None, num_seeds=2),
                             config.MAX_SEED)
    assert seeds == [config.MAX_SEED - 1, config.MAX_SEED]


def test_background_preview():
    # A flat background of 10 with a hump in the middle: the knots sit on
    # the background, not on the hump
    x = np.linspace(0.0, 50.0, 1001)
    y = 10.0 + 50.0 * np.exp(-0.5 * ((x - 25.0) / 4.0)**2)
    knots, values = config.background_preview(x, y, None, (10.0, 40.0))
    np.testing.assert_allclose(knots, [0.0, 10.0, 40.0, 50.0])
    np.testing.assert_allclose(values, 10.0, atol=0.5)
    # Control points outside the analysed range move to its edges
    knots, _ = config.background_preview(x, y, (5.0, 45.0), (0.0, 48.0))
    np.testing.assert_allclose(knots, [5.0, 5.0, 45.0, 45.0])
    assert config.background_preview(x[:5], y[:5], None, (1.0, 2.0)) is None


def test_run_button_text():
    from amorph_gui import strings as S
    assert S.run_button_text(1) == "Запустить 1 прогон"
    assert S.run_button_text(3) == "Запустить 3 прогона"
    assert S.run_button_text(5) == "Запустить 5 прогонов"
    assert S.run_button_text(11) == "Запустить 11 прогонов"
    assert S.run_button_text(21) == "Запустить 21 прогон"
    assert S.run_button_text(22) == "Запустить 22 прогона"


def test_number_fields_show_their_values(form):
    # The style sheet must leave the editor of a number field room for its
    # text: once it pushed the text out of sight
    form.show()
    for box, text in ((form.cp1, "10"), (form.cp2, "40"), (form.nu_lo, "1"),
                      (form.num_seeds, None)):
        editor = box.lineEdit()
        if text is not None:
            assert editor.text() == text
        assert editor.isVisible()
        assert editor.height() >= editor.fontMetrics().height(), \
            (editor.geometry(), box.geometry())
        assert editor.width() > editor.fontMetrics().horizontalAdvance("00")
