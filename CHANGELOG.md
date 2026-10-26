Changelog
=========

The changes of each release of AMORPH. A release is tagged `v<version>`,
where `<version>` is that of `project()` in `CMakeLists.txt`. The notes of
the GitHub Release are the section of that version below, unless the tag is
annotated with a message of more than one line, which is used instead (see
"Releases" in the README). The date of a release is that of its tag.

## 1.1.0

The graphical interface shows the estimate of a run while the sampler
works, reports several seeds of one sample together and draws their
figures for LaTeX. The sampler and its results are those of 1.0.2.
Pre-releases (v1.1.0-rc.1, ...) come before the release, on GitHub only.

### Added

- «Прогоны» shows the estimate of the run while the sampler works: the
  amorphous fraction with its 50% and 90% intervals from all the saves so
  far with their posterior weights, how it moved over the saves, the
  effective sample size, log(Z) and whether the estimate has settled; and
  the background, the amorphous halo, the crystalline peaks and the model,
  each a layer that can be hidden, for the posterior mean so far, the best
  sample or the last saved one, with their levels among those of the
  sampler. It used to show only the last saved sample, which once the
  levels are built is usually from a low level and fits the data worse
  than the posterior. The estimate is updated every second; when it takes
  longer, as on a slow computer or late in a long run, it waits four
  times as long as it took, and the plots are redrawn only for a new
  estimate.
- «Сравнение»: the options file and the saves of each run, its effective
  sample size, log(Z) against the best run of the same data and settings,
  and its checks; a run 5 nats or more below the best did not converge
  and is unticked. The ticked runs make a joint report (the fraction of
  all the seeds together, the spread of their medians, warnings, a line
  for a paper) and a figure, in the style of `doc/figures/xrd_fit.tex` or
  with two panels (`doc/figures/xrd_seeds.tex`), exported as the tables of
  PGFPlots, a folder for LaTeX, PDF and SVG built with the LaTeX
  installed, or PNG. «Добавить папку…» adds every archive of a folder.
- «Данные для PGFPlots…» on «Результаты» writes the tables of
  `export_pgf.py` for the run.
- `doc/figures/xrd_fit.tex` also builds SVG: `latex` and `dvisvgm`.
- `src/amorph_seeds.py` pools the seeds of a sample;
  `export_pgf.write_tables` writes the tables from curves in memory;
  `src/amorph_tex.py` writes the folders of the figures and builds them.

- «Открыть прогоны…» on «Прогоны» (or a folder chosen on «Сравнение», or
  folders dropped on the window) opens runs done earlier or on another
  computer from their folders, many at a time: each on «Прогоны» with its
  output and its estimate rebuilt from its saves, on «Результаты» and on
  «Сравнение». A run without an up-to-date archive is post-processed.
- A splash screen shows as soon as the GUI starts, with the step under way:
  the first start of a newly unpacked package can take a minute while the
  system checks its files, and without a window the program was started
  again and again. The README says so too.

### Fixed

- The axes of the plots of the GUI no longer scale numbers with an SI
  prefix: the histogram of the fraction read 200-800 "(x0.001)".
- The layout of rc.1: an empty table of «Сравнение» squeezed «Архив» and
  «Настройки» to a few letters, and its hint was cut off; the table of
  «Прогоны» scrolled sideways; the empty plot of the fraction ran from
  -0.4 to 0.4.
- In rc.1 and rc.2 the plots of «Прогоны» were updated every 5 seconds,
  behind a fast sampler, and the chips of the layers were all struck
  through, as if hidden.

### Build and CI

- A tag v<version>-rc.<n> (or -beta.<n>, -alpha.<n>) makes a GitHub
  pre-release of the version, with the notes of the version.

## 1.0.2

The programs are those of 1.0.1, and the sampler and its results those of
1.0.0. This is the first release that is also published on
[GitVerse](https://gitverse.ru/ijjjjke/amorph/releases), apart from the GUI
package for Linux, which is larger than GitVerse allows.

### Build and CI

- The GitVerse mirror takes its API key from the secret `RELEASE_API_KEY`:
  GitVerse does not take the name `GITVERSE_API_KEY`, so the mirror of
  v1.0.1 had no key and failed at the upload. Without the key it now stops
  at once instead of after the wait for the GitHub Release (#19).

## 1.0.1

The sampler and its results are those of 1.0.0. The figure export takes
its data file from `config.yaml`. The release was meant to be the first
one on GitVerse too, but its mirror failed (see 1.0.2).

### Changed

- `export_pgf.py` reads the data file that `config.yaml` names in
  `data_file`, like the sampler, unless `--data` names one (`--config`
  names another `config.yaml`); it read `easy_data.txt`. The title of the
  figure is the name of the data file unless `--title` gives one; it was
  the formula of one alloy. `scripts/make_xrd_figure.sh` does the same
  with `src/config.yaml` (#17).

### Build and CI

- The GitVerse mirror of a release waits up to 20 minutes for the GitHub
  Release to be complete, checking every 20 seconds, then downloads each
  file once; if the release is not complete by then, it says so and how to
  run it again (#16). Files larger than 100 MB, which GitVerse refuses
  (the GUI package for Linux), stay on GitHub, and the notes of the
  GitVerse Release link to them.

### Documentation

- README: the runs on 15–70° with four seeds of 10000 saves (the seeds
  disagree by 0.05–0.1, against 0.01 on 20–50°, so the narrower range is
  recommended), and the check that the faster sampler of #14 gives the same
  results as before (#16).

## 1.0.0

The first release, with executables and a graphical interface for Windows,
Linux and macOS. Since the
AMORPH of the paper (Rowe and Brewer, 2018), the fixes of two bugs of the
sampler change the results of every analysis, and those of the
post-processing change some; see "Results change".
The pull requests are those of
[github.com/ij3tt/amorph](https://github.com/ij3tt/amorph/pulls?q=is%3Apr).

### Results change

- The Student-t likelihood is normalised: it had `log(nu/2)` where
  `lgamma(nu/2)` belongs and compared r² with the variance instead of
  ν times the variance, which pushed ν of the noise to the top of its prior
  and made the noise Gaussian in practice. Its scale is now
  `sqrt(sigma0² + sigma1*model)`, as in the paper; σ₀ and σ₁ came out about
  30 times too large (#2).
- The outer knots of the background are at the ends of the data. They were
  at x = 0, so above the upper control point the background was
  extrapolated towards x = 0 and could become negative (#2).
- Posterior samples without a wide component count as 0% amorphous.
  `display.py` dropped them, so the fraction came out too high for nearly
  crystalline materials, and differed from that of `export_pgf.py` (#3).
- The amorphous fraction and the shape of the wide component are integrals
  with trapezoidal weights, right on a non-uniform grid too (#9).
- The resampling of the post-processing is seeded with `seed` of
  `config.yaml` (or 0), so the same run gives the same posterior samples
  every time (#9).

### Added

- A graphical interface, `src/amorph_gui` (PySide6, in Russian): the data
  with the range and the background control points dragged on the plot,
  every setting of `config.yaml` with its checks, runs of several seeds
  with their progress and a live plot, the results with the diagnosis and
  every figure, and the comparison of run archives (#13). Packaged for
  Windows, Linux and macOS with the sampler inside, ready to run without
  Python (#15).
- A faster sampler, with the same model: each peak is evaluated only within
  20 widths of its centre, and the curves are updated by the peaks that
  changed instead of computed anew. In the validation it saved 1.6 to 4.3
  times as many samples per minute (#14).
- Version numbers: AMORPH prints its version in the first line of its
  output, and run archives record it.
- Checks of `config.yaml` and of the data file before the sampler starts,
  with messages that name the file, the line and the setting, and exit
  status 1. A data file may have comments, blank lines, a byte order mark,
  CR LF line ends and commas. `AMORPH.exe` started by a double click waits
  for Enter after an error, so that it can be read. A warning when the
  control points lie outside the data (#4).
- `inference_assumptions.narrow_peak_nu` in `config.yaml`, the bounds of
  the prior on the shape ν of the narrow peaks, and `seed` (#5).
- `scripts/diagnose_posterior.py`: whether the amorphous fraction of a run
  is well determined, per band of the fraction; `--range LOW HIGH` also
  gives the fraction within a range of x (#5, #10).
- The report of `showresults.py`: log(Z), the information and the effective
  sample size, the fraction and the shape of the wide component, the
  diagnosis, and 11 figures (#11).
- Run archives (`.amorph`): the results of a run, its inputs and an HTML
  report with the figures in one zip file of a few megabytes, written by
  `showresults.py`; `amorph_archive.py` writes, reads and shows them. The
  results as data in `amorph_results.py`, for programs (#11).
- Datasets: `G30RAW_amorph.txt` and `N3RAW_amorph.txt` (26–46°), two
  samples whose amorphous fraction is ambiguous (#5), and their whole scans,
  5–70°, with the parts 20–50° and 15–70° (#10).
- README: the shape of the crystalline peaks, the recommended settings, what
  the calibration standards show and how to report results (#5–#9), and a
  Russian translation, `README.ru.md` (#8).

### Fixed

- `display.py` crashed with NumPy 2 when a posterior sample had no wide
  component (#1).
- The post-processing reads the data file by the rules of the sampler; it
  stopped at a blank line and failed on a byte order mark or commas (#9).
- The histogram of the number of narrow peaks lost the last two counts (#9).
- `export_pgf.py` reported 0% when no sample had either component; the
  fraction is undefined then, and it stops with an error (#9).
- A missing or empty data file, a missing key or a wrong type in
  `config.yaml` crashed AMORPH or ran it without data (#4).

### Build and CI

- CMake builds AMORPH with DNest4 and yaml-cpp 0.9.0 vendored in
  `external/`, so the build needs no network access (#1).
- CI on GitHub and GitVerse with shared scripts in `scripts/ci/`: the Linux
  build, the unit tests of the model, the input checks and the Python
  post-processing, and a smoke test; `AMORPH.exe` cross-compiled with
  mingw-w64, without MinGW DLLs, and run on Windows (#1–#4); a macOS build
  on Apple Silicon (#11).
- On-demand workflows: `validate.yml` compares two versions of AMORPH on the
  bundled datasets (#1, #2), `experiment.yml` runs settings on several seeds
  in parallel (#5–#7, #10).
- Releases: `release.yml` builds, tests and packs the three systems on a
  pushed tag `v*`, with SHA-256 checksums, and the GUI packaged with
  PyInstaller on each system, whose self-test runs on the package (#15). The Linux executable needs glibc
  2.34 and the libstdc++ of GCC 13 or newer, the macOS one macOS 11 or
  newer. The actions of the GitHub workflows run on Node 24.
