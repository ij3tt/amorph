Changelog
=========

The changes of each release of AMORPH. A release is tagged `v<version>`,
where `<version>` is that of `project()` in `CMakeLists.txt`. The notes of
the GitHub Release are the section of that version below, unless the tag is
annotated with a message of more than one line, which is used instead (see
"Releases" in the README). The date of a release is that of its tag.

## 1.0.0

The first release, with executables for Windows, Linux and macOS. Since the
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
  pushed tag `v*`, with SHA-256 checksums. The Linux executable needs glibc
  2.34 and the libstdc++ of GCC 13 or newer, the macOS one macOS 11 or
  newer. The actions of the GitHub workflows run on Node 24.
