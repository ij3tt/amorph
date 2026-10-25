"""
Diagnose the posterior of an AMORPH run: is the amorphous fraction well
determined, or does part of the posterior describe the amorphous hump with
narrow peaks instead?

Run it on a folder with the output of the sampler after the DNest4
post-processing (showresults.py or summarize_run.py):

    python diagnose_posterior.py RUN_FOLDER --data RUN_FOLDER/data.txt \
        --json diagnosis.json --table particles.csv.gz

It reads sample.txt and sample_info.txt (every saved particle), levels.txt
or weights.txt (their posterior weights) and posterior_sample.txt, and
reports

- the posterior quantiles of the amorphous fraction and the weight of the
  posterior with a fraction of 0, below 0.2 and below 0.45;
- for each of these bands of the fraction: the number of particles, their
  weight, and the median log likelihood, number of narrow peaks, shape nu of
  the narrow peaks and misfit (RMS of model - data);
- the weight of particles with a number of narrow peaks near its maximum,
  which shows that the prior limit, not the data, sets that number;
- the posterior of the noise parameters and of nu of the narrow peaks.

--range LOW HIGH also gives the posterior quantiles of the amorphous fraction
within that range of x: runs on different ranges of the same measurement
can then be compared on the range they share.

--table writes one row per saved particle with these quantities, a small
file instead of the hundreds of megabytes of sample.txt.

The computation is that of src/amorph_results.py, which showresults.py and
the run archives (src/amorph_archive.py) use too.
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import amorph_results
import amorph_stats


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("folder", help="folder with the output of the sampler")
    p.add_argument("--data", required=True,
                   help="the two-column data file that was analysed")
    p.add_argument("--json", help="write the diagnosis to this JSON file")
    p.add_argument("--table", help="write one row per saved particle to this "
                                   "CSV file (.gz to compress it)")
    p.add_argument("--range", nargs=2, type=float, metavar=("LOW", "HIGH"),
                   help="also give the amorphous fraction within this range "
                        "of x")
    args = p.parse_args()

    if args.range is not None:
        x = amorph_stats.load_data(args.data)[0]
        if ((x >= args.range[0]) & (x <= args.range[1])).sum() < 2:
            p.error("--range {0} {1}: fewer than two data points in it".format(
                *args.range))

    results = amorph_results.from_run(args.folder, data_file=args.data,
                                      fraction_range=args.range)
    if results.diagnosis is None:
        sys.exit("diagnose_posterior: {0} needs sample.txt, sample_info.txt "
                 "and levels.txt or weights.txt".format(args.folder))

    for line in amorph_results.diagnosis_lines(results.diagnosis):
        print(line)

    if args.json:
        with open(args.json, "w") as fout:
            json.dump(results.diagnosis, fout, indent=2)
    if args.table:
        results.particles.to_csv(args.table, index=False,
                                 float_format="%.6g")


if __name__ == "__main__":
    main()
