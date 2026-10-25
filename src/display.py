"""
Show the results of an AMORPH run. Run showresults.py in the folder of the
run: it does the DNest4 post-processing and then calls display(), which

- prints the report (amorph_results.report_lines): log(Z), the information
  and the effective sample size of the sampler, the amorphous fraction and
  the shape of the wide component of the posterior samples, and the
  diagnosis of the posterior;
- writes macroquantities.csv, one row per posterior sample;
- stores everything in a run archive (amorph_archive.py), which keeps the
  results when the next run overwrites the output files;
- shows the figures one after another (amorph_results.FIGURES).
"""

import matplotlib.pyplot as plt

import amorph_archive
import amorph_results


def display(archive=True):
    """
    Report, archive and show the results of the run in this folder.
    """
    results = amorph_results.from_run(".")
    if results.posterior is None:
        raise SystemExit("display: no posterior_sample.txt here; run "
                         "showresults.py, which writes it")
    for line in amorph_results.report_lines(results):
        print(line)

    # One row per posterior sample, with the columns of earlier versions
    print("Saving macroquantities.csv")
    macroquantities = results.posterior[[
        "num_narrow_peaks", "fraction", "wide_center_of_mass",
        "wide_halfwidth", "wide_skewness", "wide_nongaussianity"]].rename(
            columns={"fraction": "amorph/(amorph + crystal)"})
    macroquantities.index = range(1, len(macroquantities) + 1)
    macroquantities.to_csv("macroquantities.csv",
                           index_label="Sample number")

    if archive:
        filename = amorph_archive.write(results,
                                        amorph_archive.default_name(results))
        print("Saved the results of the run in {0}".format(filename))

    for _, _, draw in amorph_results.available_figures(results):
        fig = plt.figure()
        draw(fig, results)
        plt.show()
        plt.close(fig)


if __name__ == "__main__":
    display()
