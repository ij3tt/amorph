"""
The settings of a run as the screen «Данные и модель» edits them, and the
files that the sampler reads: config.yaml and the DNest4 options file.

read_config() applies the limits that Config.cpp enforces, and check()
looks at the settings together with the data before a run, so that the
sampler does not reject a run that the GUI starts. Neither needs Qt.
"""

import json
import math
import os
import re
from dataclasses import dataclass

import numpy as np
import yaml

import amorph_stats

from amorph_gui import SRC_DIR
from amorph_gui import strings as S

# The DNest4 options files that come with AMORPH, in src/
OPTIONS_FILES = ("OPTIONS_AGGRESSIVE", "OPTIONS")

# The largest seed: DNest4 takes an unsigned int (Config.cpp)
MAX_SEED = 4294967295

# The range of nu of the table of peak shapes (Lookup.cpp), which is also
# the default of the sampler, and the range that README recommends
NU_LIMITS = (0.1, 100.0)
RECOMMENDED_NU = (1.0, 100.0)

# Which value of the DNest4 options file is the maximum number of saves
# (counting from 0; Options.cpp)
MAX_SAVES_VALUE = 7

ERROR = "error"
WARNING = "warning"


@dataclass
class Settings:
    """
    Every key of config.yaml, and what a run needs besides: the maximum
    number of saves (a line of the options file), the number of seeds and
    the range of x to analyse (None for all the data). seed None means
    "use the time".
    """
    num_threads: int = 8
    data_file: str = "easy_data.txt"
    dnest4_options_file: str = OPTIONS_FILES[0]
    seed: object = None
    control_points: tuple = (10.0, 40.0)
    max_num_narrow_peaks: int = 500
    max_num_wide_peaks: int = 100
    left_edge: float = 0.3
    right_edge: float = 0.7
    narrow_peak_nu: tuple = RECOMMENDED_NU
    max_saves: int = 10000
    num_seeds: int = 1
    x_range: object = None


class ConfigError(ValueError):
    pass


# ------------------------------------------------------------- config.yaml

def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _number(filename, value, key):
    # yaml-cpp reads "1e-5" as a number, PyYAML as text
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            pass
    if not _is_number(value) or not math.isfinite(value):
        raise ConfigError(S.CONFIG_NUMBER.format(filename, key, value))
    return float(value)


def _count(filename, group, key, path):
    if key not in group:
        raise ConfigError(S.CONFIG_MISSING.format(filename, path))
    value = group[key]
    if isinstance(value, str) and re.fullmatch(r"\s*[+-]?[0-9]+\s*", value):
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(S.CONFIG_COUNT.format(filename, path, value))
    return value


def _pair(filename, group, key, path):
    value = group[key]
    if not isinstance(value, list) or len(value) != 2:
        raise ConfigError(S.CONFIG_PAIR.format(filename, path, value))
    a = _number(filename, value[0], path)
    b = _number(filename, value[1], path)
    if not a < b:
        raise ConfigError(S.CONFIG_INCREASING.format(filename, path, a, b))
    return a, b


def _file_name(filename, config, key):
    if key not in config:
        raise ConfigError(S.CONFIG_MISSING.format(filename, key))
    value = config[key]
    if value is None or isinstance(value, (list, dict, bool)):
        raise ConfigError(S.CONFIG_FILE_NAME.format(filename, key, value))
    return str(value)


def settings_from_config(config, filename="config.yaml"):
    """
    The settings of a config.yaml that yaml.safe_load has read, with the
    rules of Config.cpp. Raises ConfigError, naming the file and the key.
    The keys that are not in config.yaml keep their defaults.
    """
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ConfigError(S.CONFIG_NOT_SETTINGS.format(filename))
    s = Settings()
    s.num_threads = _count(filename, config, "num_threads", "num_threads")
    s.data_file = _file_name(filename, config, "data_file")
    s.dnest4_options_file = _file_name(filename, config,
                                       "dnest4_options_file")

    ia = "inference_assumptions"
    if ia not in config:
        raise ConfigError(S.CONFIG_MISSING.format(filename, ia))
    group = config[ia]
    if not isinstance(group, dict):
        raise ConfigError(S.CONFIG_GROUP.format(filename, ia))

    def path(key):
        return ia + "." + key

    for key in ("control_points", "left_edge", "right_edge"):
        if key not in group:
            raise ConfigError(S.CONFIG_MISSING.format(filename, path(key)))
    s.control_points = _pair(filename, group, "control_points",
                             path("control_points"))
    s.max_num_narrow_peaks = _count(filename, group, "max_num_narrow_peaks",
                                    path("max_num_narrow_peaks"))
    s.max_num_wide_peaks = _count(filename, group, "max_num_wide_peaks",
                                  path("max_num_wide_peaks"))
    s.left_edge = _number(filename, group["left_edge"], path("left_edge"))
    s.right_edge = _number(filename, group["right_edge"], path("right_edge"))
    if not 0.0 <= s.left_edge < s.right_edge <= 1.0:
        raise ConfigError(S.CONFIG_EDGES.format(filename, s.left_edge,
                                                s.right_edge))

    # Optional, 0.1 to 100 by default as in the sampler
    s.narrow_peak_nu = NU_LIMITS
    if "narrow_peak_nu" in group:
        s.narrow_peak_nu = _pair(filename, group, "narrow_peak_nu",
                                 path("narrow_peak_nu"))
        if s.narrow_peak_nu[0] < NU_LIMITS[0] or \
                s.narrow_peak_nu[1] > NU_LIMITS[1]:
            raise ConfigError(S.CONFIG_NU_RANGE.format(
                filename, path("narrow_peak_nu"), *s.narrow_peak_nu))

    # Optional: without a seed the sampler uses the time
    if "seed" in config:
        seed = config["seed"]
        if isinstance(seed, bool) or not isinstance(seed, int) \
                or not 0 <= seed <= MAX_SEED:
            raise ConfigError(S.CONFIG_SEED.format(filename, seed))
        s.seed = seed
    return s


def read_config(filename):
    """
    The settings of the config.yaml filename. When the options file that
    it names is next to it, its maximum number of saves too; returns the
    settings and the text of that options file (None if it is not there).
    """
    name = os.path.basename(filename)
    with open(filename, encoding="utf-8-sig") as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(S.CONFIG_SYNTAX.format(name, e))
    settings = settings_from_config(config, name)
    options = None
    path = os.path.join(os.path.dirname(os.path.abspath(filename)),
                        settings.dnest4_options_file)
    if os.path.isfile(path):
        with open(path) as f:
            options = f.read()
        settings.max_saves = options_max_saves(options)
    return settings, options


def default_settings():
    """
    The settings of the bundled config.yaml, with the range of nu that
    README recommends, and the maximum number of saves of its options file.
    """
    try:
        settings, _ = read_config(os.path.join(SRC_DIR, "config.yaml"))
    except (OSError, ConfigError):
        settings = Settings()
    settings.narrow_peak_nu = RECOMMENDED_NU
    template = options_templates().get(settings.dnest4_options_file)
    if template is not None:
        settings.max_saves = options_max_saves(template)
    return settings


def _yaml_number(value):
    # Text that both PyYAML and yaml-cpp read as this float: PyYAML wants a
    # decimal point
    text = repr(float(value))
    if "e" in text and "." not in text:
        mantissa, exponent = text.split("e")
        text = mantissa + ".0e" + exponent
    return text


def _yaml_pair(pair):
    return "[{0}, {1}]".format(_yaml_number(pair[0]), _yaml_number(pair[1]))


def _yaml_string(text):
    # A double-quoted YAML string is a JSON string
    return json.dumps(text, ensure_ascii=False)


def config_text(settings):
    """
    The config.yaml of the settings, laid out as the bundled one.
    """
    s = settings
    if s.seed is None:
        seed = ("# Seed of the random number generator, a whole number. "
                "Without it the time\n# is used.\n# seed: 42\n")
    else:
        seed = ("# Seed of the random number generator, a whole number. "
                "Without it the time\n# is used.\nseed: {0}\n".format(
                    int(s.seed)))
    return """# Set up everything for an AMORPH run (written by the AMORPH GUI)
---

# Number of threads to use
num_threads: {threads}

# Data file for the run
data_file: {data}

# Which file of DNest4 options to use
dnest4_options_file: {options}

{seed}
# Section for things that affect the inference
inference_assumptions:

    # Control points of the background, which is a straight line between
    # them: put them where the amorphous halo ends
    control_points: {cp}

    # Maximum number of peaks
    max_num_narrow_peaks: {narrow}
    max_num_wide_peaks: {wide}

    # What subset of the domain should the amorphous peaks be allowed to
    # appear in? In these units, the domain goes from 0 to 1.
    left_edge: {left}
    right_edge: {right}

    # Bounds of the shape parameter nu of the narrow (crystalline) peaks
    narrow_peak_nu: {nu}
""".format(threads=int(s.num_threads), data=_yaml_string(s.data_file),
           options=_yaml_string(s.dnest4_options_file), seed=seed,
           cp=_yaml_pair(s.control_points), narrow=int(s.max_num_narrow_peaks),
           wide=int(s.max_num_wide_peaks), left=_yaml_number(s.left_edge),
           right=_yaml_number(s.right_edge), nu=_yaml_pair(s.narrow_peak_nu))


def write_config(settings, filename):
    with open(filename, "w", encoding="utf-8") as f:
        f.write(config_text(settings))


# --------------------------------------------------------- DNest4 options

def options_templates():
    """
    The text of each options file of OPTIONS_FILES that is in src/, by
    name.
    """
    templates = {}
    for name in OPTIONS_FILES:
        path = os.path.join(SRC_DIR, name)
        if os.path.isfile(path):
            with open(path) as f:
                templates[name] = f.read()
    return templates


def _value_lines(lines):
    # Comments come at the top only, then one value per line (Options.cpp)
    i = 0
    while i < len(lines) and lines[i].startswith("#"):
        i += 1
    return [j for j in range(i, len(lines)) if lines[j].strip()]


def options_max_saves(text):
    """
    The maximum number of saves of a DNest4 options file (0: no limit).
    """
    lines = text.splitlines()
    return int(lines[_value_lines(lines)[MAX_SAVES_VALUE]].split()[0])


def options_with_max_saves(text, max_saves):
    """
    The text of a DNest4 options file with another maximum number of saves.
    """
    lines = text.splitlines(keepends=True)
    i = _value_lines(lines)[MAX_SAVES_VALUE]
    lines[i] = re.sub(r"^(\s*)\S+", lambda m: m.group(1) + str(int(max_saves)),
                      lines[i], count=1)
    return "".join(lines)


# ---------------------------------------------------- checks before a run

def selected(x, x_range):
    """
    Which points of x lie in the range of x to analyse.
    """
    if x_range is None:
        return np.ones(np.shape(x), dtype=bool)
    return (x >= x_range[0]) & (x <= x_range[1])


def wide_band(x, left_edge, right_edge):
    """
    Where the centres of the wide peaks may be, from the analysed points x,
    as MyConditionalPrior.cpp puts them.
    """
    x_min, x_max = float(np.min(x)), float(np.max(x))
    return (x_min + left_edge * (x_max - x_min),
            x_min + right_edge * (x_max - x_min))


def background_preview(x, y, x_range, control_points):
    """
    Where the straight background between the control points roughly lies,
    for the plot of «Данные и модель»: a low quantile (30%) of the data
    near each knot, which are the edges of the analysed range and the
    control points (moved into the range). The sampler fits the background;
    this only shows the choice of the knots. Returns the x and y of the
    knots, or None with fewer than 10 points.
    """
    keep = selected(x, x_range)
    xs, ys = np.asarray(x)[keep], np.asarray(y)[keep]
    if xs.size < 10:
        return None
    lo, hi = float(xs[0]), float(xs[-1])
    knots = [lo] + sorted(min(max(float(c), lo), hi)
                          for c in control_points) + [hi]
    half = 0.015 * (hi - lo)
    values = []
    for k in knots:
        near = np.nonzero(np.abs(xs - k) <= half)[0]
        if near.size < 5:
            near = np.argsort(np.abs(xs - k))[:5]
        values.append(float(np.percentile(ys[near], 30.0)))
    return np.array(knots), np.array(values)


def check(settings, x):
    """
    What is wrong with a run of these settings on the data x (None: no
    data), as a list of (ERROR or WARNING, text). A run with an error is
    not started.
    """
    s = settings
    problems = []

    def error(text):
        problems.append((ERROR, text))

    def warning(text):
        problems.append((WARNING, text))

    if s.control_points[0] >= s.control_points[1]:
        error(S.CHECK_CP_ORDER.format(*s.control_points))
    if not 0.0 <= s.left_edge < s.right_edge <= 1.0:
        error(S.CHECK_EDGES.format(s.left_edge, s.right_edge))
    nu = s.narrow_peak_nu
    if nu[0] >= nu[1]:
        error(S.CHECK_NU_ORDER.format(*nu))
    elif nu[0] < NU_LIMITS[0] or nu[1] > NU_LIMITS[1]:
        error(S.CHECK_NU_TABLE.format(*nu))
    if nu[0] < 1.0:
        warning(S.CHECK_NU_BELOW_1.format(nu[0]))
    if s.seed is not None:
        if not 0 <= s.seed <= MAX_SEED:
            error(S.CHECK_SEED.format(MAX_SEED))
        elif s.seed + s.num_seeds - 1 > MAX_SEED:
            error(S.CHECK_SEEDS_RANGE.format(s.seed, s.num_seeds, MAX_SEED))
    if s.max_saves == 0:
        warning(S.CHECK_NO_LIMIT)

    if x is None:
        error(S.CHECK_NO_DATA)
        return problems
    if s.x_range is not None and not s.x_range[0] < s.x_range[1]:
        error(S.CHECK_RANGE_ORDER)
        return problems
    cut = x[selected(x, s.x_range)]
    if cut.size < amorph_stats.MIN_NUM_POINTS:
        error(S.CHECK_FEW_POINTS.format(cut.size,
                                        amorph_stats.MIN_NUM_POINTS))
        return problems

    # The background is a straight line under the halo: its control points
    # belong where the halo ends, with data beyond them on both sides
    cp1, cp2 = s.control_points
    lo, hi = float(cut[0]), float(cut[-1])
    if cp1 < lo or cp2 > hi:
        error(S.CHECK_CP_OUTSIDE.format(cp1, cp2, lo, hi))
    else:
        if not lo < cp1:
            warning(S.CHECK_CP_NOTHING_LEFT.format(cp1))
        if not cp2 < hi:
            warning(S.CHECK_CP_NOTHING_RIGHT.format(cp2))
    return problems


def run_seeds(settings, now):
    """
    The seeds of the runs: seed, seed + 1, ..., or from the time now (in
    seconds) if the settings have no seed.
    """
    n = settings.num_seeds
    if settings.seed is not None:
        base = int(settings.seed)
    else:
        base = min(int(now) % (MAX_SEED + 1), MAX_SEED - n + 1)
    return [base + i for i in range(n)]
