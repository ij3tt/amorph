"""
Write a Markdown table of the runs of the experiment workflow
(.github/workflows/experiment.yml).

    python compare_experiment.py RUNS_DIR > experiment.md

RUNS_DIR holds one folder per run with setting.json (written by the
workflow), summary.json (summarize_run.py) and diagnosis.json
(diagnose_posterior.py).
"""

import json
import os
import sys


def load(folder, name):
    path = os.path.join(folder, name)
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        return json.load(f)


def percent(value):
    return "-" if value is None else "{0:.1f}%".format(100.0 * value)


def main():
    root = sys.argv[1]
    runs = []
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        setting = load(folder, "setting.json")
        if setting is None:
            continue
        runs.append((setting, load(folder, "summary.json"),
                     load(folder, "diagnosis.json")))

    print("## Experiment: the shape of the crystalline peaks")
    print()
    print("Amorphous fraction: posterior median [25%, 75%], and the posterior "
          "weight with a fraction of 0, below 0.2 and below 0.45. "
          "\"at cap\": weight with at least 90% of the maximum number of "
          "narrow peaks. nu_narrow, narrow peaks, noise nu: posterior "
          "medians.")
    print()

    for data in sorted({s["data"] for s, _, _ in runs}):
        print("### " + data)
        print()
        print("| setting | peaks | nu_narrow range | control points | seed "
              "| fraction | = 0 | < 0.2 | < 0.45 | at cap | nu_narrow "
              "| narrow peaks | noise nu | saves | minutes |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for s, summary, d in sorted(
                (r for r in runs if r[0]["data"] == data),
                key=lambda r: (r[0]["setting"], r[0]["seed"])):
            row = [s["setting"],
                   "{0}/{1}".format(s["max_num_narrow_peaks"],
                                    s["max_num_wide_peaks"]),
                   s["narrow_peak_nu"], s.get("control_points", "-"),
                   str(s["seed"])]
            if d is None:
                row += ["run failed"] + ["-"] * 9
            else:
                f = d["fraction"]
                row += ["{0:.3f} [{1:.3f}, {2:.3f}]".format(f["q50"], f["q25"],
                                                           f["q75"]),
                        percent(d["weight_fraction_0"]),
                        percent(d["weight_fraction_below_0.2"]),
                        percent(d["weight_fraction_below_0.45"]),
                        percent(d["weight_narrow_at_cap"]),
                        "{0:.3g}".format(d["nu_narrow"]["median"]),
                        "{0:.0f}".format(d["num_narrow_peaks"]["median"]),
                        "{0:.3g}".format(d["nu"]["median"])]
                if summary is None:
                    row += ["-", "-"]
                else:
                    row += ["{0}{1}".format(summary["saves"],
                                            " (stopped)"
                                            if summary.get("stopped") else ""),
                            "{0:.0f}".format(summary["seconds"] / 60.0)]
            print("| " + " | ".join(row) + " |")
        print()


if __name__ == "__main__":
    main()
