"""
What the screens «Результаты» and «Сравнение» show of the results of a
run (amorph_results.Results, from a run folder or an archive): the
diagnostic cards; one row of the comparison table with its checks and its
export to CSV and Markdown; and the joint report of the chosen runs
(amorph_seeds.pool). The numbers are those of results.diagnosis and
results.sampler; nothing here needs Qt.
"""

import io
import os

import pandas as pd

import amorph_results
import amorph_seeds

from amorph_gui import config
from amorph_gui import strings as S

RED = "red"
AMBER = "amber"
OK = "ok"

# A card warns when more posterior weight than this has a fraction below
# 0.2, or the cap of narrow peaks
WEIGHT_WARNING = 0.05

# The effective sample size below which the intervals are unreliable (red)
# or rough (amber)
ESS_BAD = 30
ESS_LOW = 100

# A run whose log(Z) is below the best of the runs of the same data and
# settings by more than this has not converged: between seeds that did,
# log(Z) differs by 2-3 nats (README, "Recommended settings")
LOG_Z_GAP = 5.0

# The seeds agree when the spread of their medians is at most this part of
# the width of the 50% interval of the pooled fraction
SPREAD_AGREES = 0.25


def run_config(results):
    c = results.info.get("config")
    return c if isinstance(c, dict) else {}


def assumptions(results):
    a = run_config(results).get("inference_assumptions")
    return a if isinstance(a, dict) else {}


def planned_saves(results):
    """
    The maximum number of saves of the options file of the run (0: no
    limit), or None if the results do not have the file.
    """
    name = run_config(results).get("dnest4_options_file")
    if not isinstance(name, str):
        return None
    text = results.attachments.get("input/" + os.path.basename(name))
    if text is None:
        return None
    try:
        return config.options_max_saves(text.decode("utf-8", "replace"))
    except (IndexError, ValueError):
        return None


def num_saves(results):
    if "num_saves" in results.info:
        return int(results.info["num_saves"])
    if results.diagnosis is not None:
        return int(results.diagnosis["saves"])
    return None


def diagnostic_cards(results, stopped=False):
    """
    The cards of the screen «Итог»: (RED, AMBER or OK, title, text). Red:
    over 5% of the posterior weight has a fraction below 0.2. Amber: over
    5% of the weight at the cap of narrow peaks; control points outside the
    data; a run stopped before its planned number of saves (stopped: the
    GUI stopped it). Last, the effective sample size: red below ESS_BAD,
    amber below ESS_LOW.
    """
    cards = []
    d = results.diagnosis
    if d is not None:
        w = d["weight_fraction_below_0.2"]
        cards.append((RED if w > WEIGHT_WARNING else OK,
                      S.CARD_LOW_TITLE.format(w),
                      S.CARD_LOW_BAD if w > WEIGHT_WARNING else S.CARD_LOW_OK))
        w = d["weight_narrow_at_cap"]
        cap = d["max_num_narrow_peaks"]
        cards.append((AMBER if w > WEIGHT_WARNING else OK,
                      S.CARD_CAP_TITLE.format(w),
                      S.CARD_CAP_BAD.format(amorph_results.AT_CAP * cap, cap)
                      if w > WEIGHT_WARNING else S.CARD_CAP_OK.format(cap)))

    cps = assumptions(results).get("control_points")
    info = results.info
    if isinstance(cps, list) and len(cps) == 2 and "x_min" in info:
        a, b = float(cps[0]), float(cps[1])
        lo, hi = info["x_min"], info["x_max"]
        outside = a < lo or b > hi
        cards.append((AMBER if outside else OK, S.CARD_CP_TITLE,
                      (S.CARD_CP_BAD if outside else S.CARD_CP_OK).format(
                          a, b, lo, hi)))

    saves = num_saves(results)
    planned = planned_saves(results)
    if saves is not None and (stopped or planned is not None):
        if planned == 0:
            cards.append((AMBER, S.CARD_STOP_TITLE,
                          S.CARD_STOP_UNLIMITED.format(saves)))
        elif stopped or saves < planned:
            cards.append((AMBER, S.CARD_STOP_TITLE, S.CARD_STOP_BAD.format(
                saves, planned if planned is not None else S.UNKNOWN)))
        else:
            cards.append((OK, S.CARD_STOP_TITLE,
                          S.CARD_STOP_OK.format(saves)))

    if d is not None and "effective_sample_size" in d:
        ess = float(d["effective_sample_size"])
        level = RED if ess < ESS_BAD else AMBER if ess < ESS_LOW else OK
        cards.append((level, S.CARD_ESS_TITLE.format(ess),
                      {RED: S.CARD_ESS_BAD, AMBER: S.CARD_ESS_LOW,
                       OK: S.CARD_ESS_OK}[level]))
    return cards


def comparison_summary(rows):
    """
    What the comparison table shows, in a few sentences, per data file: how
    far apart the medians of the fraction of runs with the same settings
    are (the run-to-run error of the sampler), and how far apart those of
    different settings; and which is the larger. Rows that are not chosen
    (a run that did not converge, or one the user unticked) are left out.
    """
    rows = [r for r in rows if r["q50"] is not None and r.get("chosen", True)]
    files = sorted({str(r["data_file"]) for r in rows})
    lines = []
    for data_file in files:
        mine = [r for r in rows if str(r["data_file"]) == data_file]
        if len(mine) < 2:
            continue
        groups = {}
        for r in mine:
            groups.setdefault(r["settings"], []).append(r["q50"])
        if len(files) > 1:
            lines.append(S.SUMMARY_DATA.format(data_file))
        spreads = [max(v) - min(v) for v in groups.values() if len(v) > 1]
        spread = max(spreads) if spreads else None
        if spread is None:
            lines.append(S.SUMMARY_ONE_SEED)
        else:
            lines.append(S.SUMMARY_SEEDS.format(spread))
        if len(groups) > 1:
            means = [sum(v) / len(v) for v in groups.values()]
            lo, hi = min(means), max(means)
            lines.append(S.SUMMARY_SETTINGS.format(lo, hi, hi - lo))
            if spread is not None:
                lines.append(S.SUMMARY_BIGGER if hi - lo > spread
                             else S.SUMMARY_SMALLER)
    return lines or [S.SUMMARY_EMPTY]


def _g(value):
    try:
        return "{0:g}".format(float(value))
    except (TypeError, ValueError):
        return S.UNKNOWN


def _pair(value, separator=", "):
    if isinstance(value, list) and len(value) == 2:
        return _g(value[0]) + separator + _g(value[1])
    return S.UNKNOWN


def settings_cell(results):
    """
    The settings of a run that matter for the comparison, in one line.
    """
    a = assumptions(results)
    # Without narrow_peak_nu the sampler uses 0.1 to 100
    nu = a.get("narrow_peak_nu", list(config.NU_LIMITS))
    return S.SETTINGS_CELL.format(
        nu=_pair(nu), cp=_pair(a.get("control_points")),
        narrow=a.get("max_num_narrow_peaks", S.UNKNOWN),
        wide=a.get("max_num_wide_peaks", S.UNKNOWN),
        edges=_g(a.get("left_edge")) + "–" + _g(a.get("right_edge")))


def comparison_row(results, archive):
    """
    One row of the comparison table: the archive, its data file, settings
    and seed, the quantiles of the fraction and the weight below 0.2 and
    at the cap (None without a diagnosis).
    """
    c = run_config(results)
    a = assumptions(results)
    row = {"archive": archive, "data_file": results.info.get("data_file"),
           "settings": settings_cell(results), "seed": c.get("seed"),
           "config": {"control_points": a.get("control_points"),
                      "narrow_peak_nu": a.get("narrow_peak_nu",
                                              list(config.NU_LIMITS)),
                      "max_num_narrow_peaks": a.get("max_num_narrow_peaks"),
                      "max_num_wide_peaks": a.get("max_num_wide_peaks"),
                      "left_edge": a.get("left_edge"),
                      "right_edge": a.get("right_edge"),
                      "dnest4_options_file": c.get("dnest4_options_file")}}
    d = results.diagnosis
    for q in ("q05", "q25", "q50", "q75", "q95"):
        row[q] = None if d is None else float(d["fraction"][q])
    row["below_0.2"] = None if d is None \
        else float(d["weight_fraction_below_0.2"])
    row["at_cap"] = None if d is None else float(d["weight_narrow_at_cap"])
    sampler = results.sampler or {}
    row["options"] = c.get("dnest4_options_file")
    row["saves"] = num_saves(results)
    row["planned"] = planned_saves(results)
    row["log_z"] = float(sampler["log_z"]) if "log_z" in sampler else None
    row["ess"] = float(d["effective_sample_size"]) if d is not None \
        else (float(sampler["effective_sample_size"])
              if "effective_sample_size" in sampler else None)
    # Set by mark_log_z, once the other rows are known
    row["dlog_z"] = None
    # Whether the run goes into the joint report, and whether the user
    # ticked or unticked it (otherwise mark_log_z chooses)
    row["chosen"] = True
    row["chosen_by_user"] = False
    row["results"] = results
    return row


def group_of(row):
    """
    The runs whose log(Z) can be compared: the same data file and the same
    settings of the model (not of the sampler).
    """
    return (str(row["data_file"]), row["settings"])


def mark_log_z(rows):
    """
    Give each row its log(Z) less the best of its group (dlog_z), and
    choose for the joint report the rows the user has not ticked or
    unticked: all but those that failed a red check.
    """
    best = {}
    for r in rows:
        if r["log_z"] is not None:
            key = group_of(r)
            best[key] = max(best.get(key, r["log_z"]), r["log_z"])
    for r in rows:
        r["dlog_z"] = None if r["log_z"] is None \
            else r["log_z"] - best[group_of(r)]
        if not r["chosen_by_user"]:
            r["chosen"] = check_level(r) != RED


def row_checks(row):
    """
    The checks of a run of the comparison: (level, text) for each that
    fails. Red: log(Z) below the best of its group by LOG_Z_GAP or more
    (the run did not converge), or over 5% of the weight at a fraction
    below 0.2. Amber: stopped before its planned saves, a small effective
    sample size, or over 5% of the weight at the cap of narrow peaks.
    """
    checks = []
    if row.get("dlog_z") is not None and row["dlog_z"] <= -LOG_Z_GAP:
        checks.append((RED, S.CHECK_LOG_Z.format(-row["dlog_z"])))
    if row.get("below_0.2") is not None and row["below_0.2"] > WEIGHT_WARNING:
        checks.append((RED, S.CHECK_LOW))
    saves, planned = row.get("saves"), row.get("planned")
    if saves is not None and planned and saves < planned:
        checks.append((AMBER, S.CHECK_STOPPED.format(saves, planned)))
    if row.get("ess") is not None and row["ess"] < ESS_LOW:
        checks.append((AMBER, S.CHECK_ESS.format(row["ess"])))
    if row.get("at_cap") is not None and row["at_cap"] > WEIGHT_WARNING:
        checks.append((AMBER, S.CHECK_CAP))
    return checks


def check_level(row):
    levels = [level for level, _ in row_checks(row)]
    return RED if RED in levels else AMBER if AMBER in levels else OK


def check_text(row):
    return "; ".join(text for _, text in row_checks(row)) or S.CHECK_OK


def seeds_word(n):
    """
    "сид", "сида" or "сидов" after the number n.
    """
    if n % 10 == 1 and n % 100 != 11:
        return S.SEED_FORMS[0]
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return S.SEED_FORMS[1]
    return S.SEED_FORMS[2]


def joint_report(rows):
    """
    The chosen rows together (amorph_seeds.pool). Returns the pooled
    results (None if they cannot be pooled), the notes on them as
    (level, text), and the line for a paper.
    """
    chosen = [r for r in rows if r["chosen"] and r.get("results") is not None
              and r.get("q50") is not None]
    if not chosen:
        return None, [("info", S.JOINT_NONE)], ""
    if len({str(r["data_file"]) for r in chosen}) > 1:
        return None, [(RED, S.JOINT_DATA)], ""
    try:
        pooled = amorph_seeds.pool([r["results"] for r in chosen])
    except ValueError as e:
        return None, [(RED, str(e))], ""

    notes = []
    q = pooled["quantiles"]
    n = len(chosen)
    if len({r["settings"] for r in chosen}) > 1:
        notes.append((AMBER, S.JOINT_SETTINGS))
    if n == 1:
        notes.append((AMBER, S.JOINT_ONE))
    else:
        width = q[3] - q[1]
        agree = pooled["spread"] <= SPREAD_AGREES * width
        notes.append((OK if agree else AMBER, (
            S.JOINT_AGREE if agree else S.JOINT_DISAGREE).format(
                pooled["spread"], width)))
    gaps = [-r["dlog_z"] for r in chosen if r.get("dlog_z") is not None
            and r["dlog_z"] <= -LOG_Z_GAP]
    if gaps:
        notes.append((RED, S.JOINT_BAD_LOG_Z.format(max(gaps))))

    count = S.PAPER_ONE_SEED if n == 1 else S.PAPER_SEEDS.format(
        n, seeds_word(n), pooled["spread"])
    stem = os.path.splitext(str(chosen[0]["data_file"]))[0]
    paper = S.PAPER_LINE.format(data=stem, q50=q[2], q25=q[1], q75=q[3],
                                count=count)
    return pooled, notes, paper


def archive_text(row):
    """
    The archive of a row, with its folder: the archives of the seeds of a
    run, or the run.amorph files of a workflow, have the same names.
    """
    path = row["archive"]
    folder = os.path.basename(os.path.dirname(path))
    name = os.path.basename(path)
    return folder + "/" + name if folder else name


def fraction_text(row):
    if row["q50"] is None:
        return "—"
    return "{0:.3f} [{1:.3f}, {2:.3f}]".format(row["q50"], row["q25"],
                                               row["q75"])


def weight_text(value):
    return "—" if value is None else "{0:.1%}".format(value)


def seed_text(row):
    return S.NO_SEED if row["seed"] is None else str(row["seed"])


def sampler_text(row):
    """
    The options file of the sampler and the saves: "OPTIONS · 4479 из
    10000".
    """
    saves = row.get("saves")
    planned = row.get("planned")
    if saves is None:
        count = S.UNKNOWN
    elif planned:
        count = S.SAVES_CELL.format(saves, planned)
    else:
        count = str(saves)
    return S.SAMPLER_CELL.format(options=row.get("options") or S.UNKNOWN,
                                 saves=count)


def ess_text(row):
    return "—" if row.get("ess") is None else "{0:.0f}".format(row["ess"])


def dlog_z_text(row):
    value = row.get("dlog_z")
    if value is None:
        return "—"
    return "0.0" if value == 0.0 else "{0:.1f}".format(value).replace(
        "-", "−")


def rows_csv(rows):
    """
    The comparison table as CSV, one column per number and setting.
    """
    table = []
    for row in rows:
        c = row["config"]

        def part(key, i):
            value = c.get(key)
            return value[i] if isinstance(value, list) and len(value) == 2 \
                else None

        table.append({
            "archive": row["archive"], "data_file": row["data_file"],
            "seed": row["seed"],
            "control_point_1": part("control_points", 0),
            "control_point_2": part("control_points", 1),
            "narrow_peak_nu_min": part("narrow_peak_nu", 0),
            "narrow_peak_nu_max": part("narrow_peak_nu", 1),
            "max_num_narrow_peaks": c.get("max_num_narrow_peaks"),
            "max_num_wide_peaks": c.get("max_num_wide_peaks"),
            "left_edge": c.get("left_edge"),
            "right_edge": c.get("right_edge"),
            "dnest4_options_file": c.get("dnest4_options_file"),
            "fraction_q05": row["q05"], "fraction_q25": row["q25"],
            "fraction_q50": row["q50"], "fraction_q75": row["q75"],
            "fraction_q95": row["q95"],
            "weight_fraction_below_0.2": row["below_0.2"],
            "weight_narrow_at_cap": row["at_cap"],
            "saves": row.get("saves"), "planned_saves": row.get("planned"),
            "effective_sample_size": row.get("ess"),
            "log_z": row.get("log_z"), "dlog_z": row.get("dlog_z"),
            "check": check_text(row), "chosen": row.get("chosen", True)})
    buffer = io.StringIO()
    pd.DataFrame(table).to_csv(buffer, index=False)
    return buffer.getvalue()


def rows_markdown(rows):
    """
    The comparison table as a Markdown table, as the screen shows it.
    """
    def cell(text):
        return str(text).replace("|", "\\|")

    header = [S.COLUMN_ARCHIVE, S.COLUMN_DATA, S.COLUMN_SETTINGS,
              S.COLUMN_SEED, S.COLUMN_SAMPLER, S.COLUMN_ESS, S.COLUMN_LOG_Z,
              S.COLUMN_FRACTION, S.COLUMN_LOW, S.COLUMN_CAP, S.COLUMN_CHECK]
    lines = ["| " + " | ".join(header) + " |",
             "|" + " --- |" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(cell(v) for v in (
            archive_text(row), row["data_file"],
            row["settings"], seed_text(row), sampler_text(row),
            ess_text(row), dlog_z_text(row), fraction_text(row),
            weight_text(row["below_0.2"]), weight_text(row["at_cap"]),
            check_text(row))) + " |")
    return "\n".join(lines) + "\n"
