"""
Write a Markdown table that compares the validation runs of the reference
and the tested version (.github/workflows/validate.yml).

    python compare_runs.py SUMMARY_DIR > comparison.md

SUMMARY_DIR holds one folder per run, named summary-<version>-<dataset>,
each with the summary.json written by summarize_run.py.
"""

import json
import os
import sys

QUANTITIES = [
    ("amorphous_fraction", "amorph / (amorph + crystal)"),
    ("wide_center_of_mass", "centre of mass of the wide component"),
    ("wide_halfwidth", "half-width of the wide component"),
    ("nu", "noise: nu"),
    ("sigma0", "noise: sigma0"),
    ("sigma1", "noise: sigma1"),
    ("num_narrow_peaks", "number of narrow peaks"),
    ("num_wide_peaks", "number of wide peaks"),
]


def interval(s):
    """
    Median [16%, 84%] of a summary, or a dash when there is none.
    """
    if s is None:
        return "-"
    return "{0:.4g} [{1:.4g}, {2:.4g}]".format(s["median"], s["q16"], s["q84"])


def cell(run, what):
    if run is None:
        return "run failed"
    if what in run["quantities"]:
        return interval(run["quantities"][what])
    return "{0:.4g}".format(run[what])


def main():
    root = sys.argv[1]
    runs = {}
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name, "summary.json")
        parts = name.split("-", 2)
        if len(parts) != 3 or not os.path.isfile(path):
            continue
        with open(path) as f:
            runs[(parts[2], parts[1])] = json.load(f)

    print("## AMORPH validation: reference vs tested version")
    print()
    print("Posterior median and 68% interval [16%, 84%]. The runs are "
          "stochastic, so differences well inside the intervals are noise.")
    print()

    for dataset in sorted({d for d, _ in runs}):
        ref = runs.get((dataset, "reference"))
        test = runs.get((dataset, "test"))
        print("### " + (ref or test)["data"])
        print()
        print("| | reference | tested |")
        print("|---|---|---|")
        for key, label in QUANTITIES:
            print("| {0} | {1} | {2} |".format(label, cell(ref, key),
                                               cell(test, key)))
        for key, label in [("no_wide_component",
                            "fraction of samples without a wide component"),
                           ("n_posterior", "posterior samples"),
                           ("log_z", "log(Z)"),
                           ("seconds", "sampler run time (s)")]:
            print("| {0} | {1} | {2} |".format(label, cell(ref, key),
                                               cell(test, key)))
        print()


if __name__ == "__main__":
    main()
