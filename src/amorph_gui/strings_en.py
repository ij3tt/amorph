"""
The texts of the report for LaTeX in English (report.py, «Отчёт LaTeX…» →
in English): those of the report itself and those of digest that it
prints, the diagnostic cards, the checks of the runs, the notes of the
joint report and the line for a paper. They have the names of their
Russian counterparts in strings.py.
"""

UNKNOWN = "?"
NO_SEED = "—"
SAVES_CELL = "{0} of {1}"

# The diagnostic cards (digest.diagnostic_cards)
CARD_LOW_TITLE = "Weight with a fraction below 0.2: {0:.1%}"
CARD_LOW_BAD = (
    "Part of the posterior describes the halo with narrow peaks, and the "
    "fraction is poorly determined. Check that the lower bound of ν is at "
    "least 1, and run again with another seed.")
CARD_LOW_OK = "No second mode near zero."
CARD_CAP_TITLE = "Weight at the cap of narrow peaks: {0:.1%}"
CARD_CAP_BAD = (
    "The number of narrow peaks (≥ {0:.0f} of {1}) is set by the cap, not "
    "by the data: double max_num_narrow_peaks and max_num_wide_peaks.")
CARD_CAP_OK = "The number of narrow peaks stays below the cap ({0})."
CARD_CP_TITLE = "Background control points"
CARD_CP_BAD = ("The points ({0:g}, {1:g}) lie outside the data "
               "({2:g}–{3:g}): the background is extrapolated there.")
CARD_CP_OK = "The points ({0:g}, {1:g}) lie within the data ({2:g}–{3:g})."
CARD_STOP_TITLE = "End of the run"
CARD_STOP_BAD = "Stopped after {0} saves of {1}: the result is preliminary."
CARD_STOP_UNLIMITED = ("The number of saves was not limited; stopped after "
                       "{0}: the result is preliminary.")
CARD_STOP_OK = "The run went to the end: {0} saves."
CARD_ESS_TITLE = "Effective sample size: {0:.0f}"
CARD_ESS_BAD = (
    "Too few independent samples: the fraction and its intervals are "
    "unreliable. Run longer (more saves) or with another seed.")
CARD_ESS_LOW = "Few independent samples: the intervals are rough."
CARD_ESS_OK = "Enough independent samples for the intervals."

# The checks of a run (digest.row_checks)
CHECK_OK = "converged"
CHECK_LOG_Z = "log Z {0:.1f} nats below the best: not converged"
CHECK_LOW = "second mode near zero"
CHECK_STOPPED = "stopped: {0} of {1} saves"
CHECK_ESS = "few samples (ESS {0:.0f})"
CHECK_CAP = "at the cap of narrow peaks"

# The joint report (digest.joint_report)
JOINT_NONE = "Tick at least one run."
JOINT_DATA = ("The ticked runs are of different data: a joint report is of "
              "the seeds of one sample.")
JOINT_SETTINGS = ("The ticked runs have different settings of the model: "
                  "their joint fraction mixes different models.")
JOINT_ONE = ("One seed: the spread between runs is not seen. A paper needs "
             "at least two.")
JOINT_AGREE = ("The seeds agree: the spread of their medians is {0:.3f}, "
               "against a 50% interval {1:.3f} wide.")
JOINT_DISAGREE = ("The seeds disagree: the spread of their medians is "
                  "{0:.3f}, against a 50% interval {1:.3f} wide — the result "
                  "depends on the seed.")
JOINT_BAD_LOG_Z = ("The report includes a run whose log Z is {0:.1f} nats "
                   "below the best: it missed the main part of the "
                   "posterior. Leave it out.")
PAPER_LINE = "{data}: {q50:.3f} [{q25:.3f}, {q75:.3f}], {count}"
PAPER_SEEDS = "{0} {1}, spread of the medians {2:.3f}"
PAPER_ONE_SEED = "1 seed"


def seed_word(n):
    """
    "seed" or "seeds" after the number n.
    """
    return "seed" if n == 1 else "seeds"


# The report (report.py)
REPORT_TITLE = "AMORPH report: {0}"
REPORT_DATE = "{date} · AMORPH {version}"
REPORT_HOW_TO_BUILD = ("Build the report in this folder: pdflatex "
                       "report.tex. It needs pgfplots, babel and the cm-super "
                       "fonts; the figures read their tables from pgf/.")
REPORT_RESULT = "Result"
REPORT_FRACTION = ("Amorphous fraction: median {q50:.3f}; with probability "
                   "50% between {q25:.3f} and {q75:.3f}, 90% between "
                   "{q05:.3f} and {q95:.3f}.")
REPORT_POOLED = ("{n} {seeds} together: each seed with an equal weight, its "
                 "saves with their posterior weights. Spread of the medians "
                 "of the seeds {spread:.3f}, effective sample size {ess:.0f} "
                 "in all.")
REPORT_ONE_RUN = "One run; effective sample size {ess:.0f}."
REPORT_PAPER = "Line for a paper:"
REPORT_RUNS = "Runs"
# The columns of the table of the runs, \n where a heading breaks
REPORT_COLUMNS = ["seed", "Options", "Saves", "ESS", "Δ log Z",
                  "Fraction\n[50% interval]", "Weight\n< 0.2",
                  "Weight\nat cap", "Check"]
REPORT_SETTINGS = "Data and settings"
REPORT_SETTINGS_DIFFER = ("The settings of the model differ between the "
                          "runs; these are those of the first.")
REPORT_SETTING_ROWS = [
    ("data_file", "Data file"),
    ("range", "Range of analysis, 2θ"),
    ("points", "Points"),
    ("control_points", "Background control points, 2θ"),
    ("edges", "Region of the wide peaks (share of the range)"),
    ("nu", "ν of the narrow peaks"),
    ("caps", "Maximum number of narrow / wide peaks"),
    ("options", "Options file of the sampler")]
REPORT_DIAGNOSIS = "Diagnosis"
REPORT_DIAGNOSIS_RUN = "seed {0}"
REPORT_FIGURES = "Figures"
REPORT_FIGURE_FIT = (
    "The scan with the posterior means of the model, the amorphous part, the "
    "crystalline peaks and the background; the faint lines are posterior "
    "samples, as many from each seed. “Amorphous” in the figure is the "
    "median of the fraction with its 50% interval, as in the text.")
REPORT_FIGURE_SEEDS = (
    "(a) The scan, the background, the amorphous halo, the crystalline peaks "
    "and the model with its 90% band; dashed, the halo of each seed. (b) The "
    "distribution of the fraction of each seed and pooled.")
REPORT_NOTES = "How to read the numbers"
# What «Как читать» says, as (title, text)
REPORT_NOTE_ITEMS = [
    ("Amorphous fraction",
     "The share of the intensity of the scan (without the background) in "
     "the wide amorphous halo: 0 is crystalline peaks only, 1 the halo only. "
     "It is a ratio of integrated intensities, not a mass fraction of glass, "
     "which needs a calibration with standards."),
    ("50% and 90% intervals",
     "With probability 50% (or 90%) the fraction lies within them, given "
     "these data and these settings of the model. The 50% interval runs "
     "from the 25th to the 75th percentile, the 90% interval from the 5th "
     "to the 95th."),
    ("Seeds and their spread",
     "The seed sets the random numbers of the sampler. Runs with other "
     "seeds are independent repeats; the spread of their medians is the "
     "error of the sampler, which the intervals do not include."),
    ("Effective sample size (ESS)",
     "How many saves of equal weight all the saves with their weights are "
     "worth. Below 30 the intervals are unreliable, below 100 rough."),
    ("log Z",
     "The log of the evidence: how well the model explains the data as a "
     "whole. Comparable only between runs of the same data with the same "
     "settings; a run 5 nats or more below the best did not converge."),
]
