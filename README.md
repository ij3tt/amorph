AMORPH
========

(c) 2016–2018 [Brendon J. Brewer](https://www.stat.auckland.ac.nz/~brewer/)
and [Michael Rowe](http://www.env.auckland.ac.nz/people/michael-rowe)

AMORPH is free software, released under the GNU General Public License,
version 3. See the LICENSE file for details.

Guide to installing and operating:
==================================

AMORPH is hosted at the following URL:

[https://bitbucket.org/eggplantbren/amorph]([https://bitbucket.org/eggplantbren/amorph)

The repository includess the source code, Python scripts for viewing results,
example datasets, and the Windows executable file (`AMORPH.exe`), which is
the easiest way of using AMORPH. It is located (along with almost everything
else) in the `src` subdirectory.
The Python scripts make use of the packages Numpy, matplotlib, Pandas, and
yaml, and has only
been tested under Python 3. [https://www.anaconda.com/download/](Anaconda) is a
convenient distribution of Python which comes with these packages
pre-installed.

The AMORPH program can be installed anywhere on the computer. All data files to
be analysed by AMORPH need to be in .txt file format, space delimited, with no
headers (i.e., just two columns of numbers). For simplicity, text files for
processing should be located in the same folder as the AMORPH program.
To configure a run, edit the file `config.yaml` to specify all the details of
the data file and other things you might want to tweak.

Four test datasets are stored in the repository
(`0%glass_rhyolite_Emperyon.txt`, `50% glass .02step3secdwell.txt`,
`90%_glass_basalt_Emperyon.txt`, and `easy_data.txt`), and two more
samples, `G30RAW_amorph.txt` and `N3RAW_amorph.txt` (26–46°), that show
the ambiguity described in "The shape of the crystalline peaks" below.
The program is set to run until
10,000 saved parameter sets have been generated. Outputs may be viewed at any
point, however, closing the program before reaching  10,000 will reduce the
accuracy of the final calculations. After running for a while, the output can
be viewed by running the Python script `showresults.py`:

```
python showresults.py
```

Automatically generated figures may be closed or saved. Upon closing the
figures, numerical results will be displayed in Anaconda prompt window,
and a CSV file of (some) output will be written to the disk.
Important: make sure to save the results or copy the output file before
starting another run as results will otherwise be overwritten.

Checks of the input files
=========================

Before the sampler starts, AMORPH checks `config.yaml` and the data file.
If something is wrong, it stops with exit status 1 and a message that names
the file, the line and the setting:

* `config.yaml` must be valid YAML and contain every setting of the bundled
  one. `num_threads`, `max_num_narrow_peaks` and `max_num_wide_peaks` are
  whole numbers of at least 1, `control_points` is a list of two numbers in
  increasing order, and `0 <= left_edge < right_edge <= 1`. The files named
  by `data_file` and `dnest4_options_file` must exist (relative paths start
  from the folder AMORPH runs in).
* The data file has two numbers per line, x and y, separated by spaces, tabs
  or a comma. Blank lines and lines that start with `#` are skipped anywhere
  in the file. There must be at least 10 data points, and x must be strictly
  increasing.

For example:

```
AMORPH: error: config.yaml: missing key 'inference_assumptions.control_points'
AMORPH: error: config.yaml, line 5: 'num_threads' must be at least 1, got '0'
AMORPH: error: config.yaml, line 8: cannot open the file 'my_data.txt' given by 'data_file' (relative paths start from the folder AMORPH runs in)
AMORPH: error: my_data.txt, line 12: expected two numbers (x and y), got '10.22 abc'
AMORPH: error: my_data.txt, line 40: the x values must be strictly increasing, but x = 10.76 follows x = 10.78 (line 39)
```

When `AMORPH.exe` was started by a double click, its window then stays open
until Enter is pressed, so that the message can be read. In a command prompt,
a terminal or a script it exits straight away.

Control points outside the range of the data are allowed, with a warning:

```
# WARNING: the background control points (5, 40) lie outside the range of the data (10 to 40). Check control_points in config.yaml.
```

Recommendations for Use
=======================

Based on experimentation, several recommendations for optimization of use and
accuracy may be suggested to potential users. First, the time of the analysis
is dependent on the number of data points to be analyzed. Thus to optimize
analysis time, we recommend an XRD instrument step of 0.02 degrees/step.
While coarser steps will reduce analysis time, the peak broadening associated
with it may reduce precision of the fitting. We also recommend reducing the
total scan range to between 10–40 degrees (2theta). This has two advantages;
1) it will reduce the number of data points for processing and 2) outside this
range the X-ray diffraction pattern is dominated by only the crystalline
componentry and thus incorporation of higher 2-theta values skews measured
results to higher measured crystallinities.

Background positions are currently optimized for the use of CuKa x-ray sources,
with linear fits between 10–40° 2theta as described in the manuscript. For
other X-ray sources, it may be necessary to adjust these fixed points to
provide the best fit to the diffraction patterns. This may be modified by
changing the values of `control_points` in `config.yaml` (which can be opened
in any text editor). For some analyses, typically when more data points are analysed
(5–50 degrees 2theta) or for highly crystalline materials, the numerical
settings of the DNest4 sampler are not optimal for obtaining useful results,
and need to be made more conservative (making the run slower).
This is typically manifested in Python outputs as pale colours in the model
curves in the output plots (showing hardly any samples from the posterior)
and a low number of data points for subsequent histograms.
The settings can be modified in these instances by opening the OPTIONS file
in any text editor. Parameter values on line 4 (new level interval) and line 8
(Backtracking scale length) can each independently be doubled. Note, while this
will improve model outputs, it significantly lengthens the time of analysis.
Therefore we only recommend changing one of these two parameters at a time.

The shape of the crystalline peaks
==================================

The narrow (crystalline) peaks are Student-t profiles with a shape parameter
ν shared by all of them. Its prior is log-uniform between the two values of
`narrow_peak_nu` in `config.yaml`, by default `[0.1, 100.0]` as in the paper
(the widest range allowed). A Student-t profile is a Pearson VII profile with
exponent m = (ν + 1)/2: ν = 1 is a Lorentzian, a large ν approaches a
Gaussian, and ν < 1 has tails heavier than a Lorentzian.

Near ν = 0.1 a "narrow" peak puts most of its area into wide tails, and a few
hundred of them can take the place of the amorphous hump. For some samples
the data cannot tell the two descriptions apart, and the posterior of the
amorphous fraction then has a second mode at or near 0. In a run on
`src/N3RAW_amorph.txt` (at most 500 narrow and 100 wide peaks, ν in
[0.1, 100]) about 12% of the posterior weight had a fraction below 0.2, with
hundreds of narrow peaks at ν of about 0.14 to 0.19 and a fit as good as that
of the main mode. In the same run on `src/G30RAW_amorph.txt` this mode had no
weight.

A narrower range, such as `narrow_peak_nu: [1.0, 100.0]` (no profile with
tails heavier than a Lorentzian), changes the model of the paper: report it
along with the results. `.github/workflows/experiment.yml` compares such
settings on these two samples.

`config.yaml` may also set `seed`, a whole number from 0 to 4294967295, for
the random number generator of the sampler; without it the time is used.


Using the source code
=====================
If you don't want to use `AMORPH.exe` and would rather compile AMORPH
yourself, you'll need a C++14 compiler and CMake 3.16+.

Both dependencies are vendored, so nothing has to be installed separately
and the build needs no network access: DNest4 in `external/DNest4` and
yaml-cpp in `external/yaml-cpp` (both MIT licence, see their `LICENSE`
files).

### Linux / macOS

```bash
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/AMORPH
```

### Windows (cross-compiled from Linux)

```bash
sudo apt-get install g++-mingw-w64-x86-64
cmake -B build-win -S . -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_SYSTEM_NAME=Windows \
      -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++
cmake --build build-win -j
```

The resulting `build-win/AMORPH.exe` is statically linked and needs no
additional DLLs. A native Windows build (MSYS2 / MinGW-w64) works too - just
drop the `-DCMAKE_SYSTEM_NAME=Windows` and compiler overrides.

### Smoke test

`scripts/smoke_test.sh` runs the sampler on the bundled example dataset with a
deliberately tiny configuration and checks that it produces the expected
output files:

```bash
bash scripts/smoke_test.sh build/AMORPH build/smoke
```

It also checks that a `config.yaml` naming a missing data file makes AMORPH
exit at once with status 1 and an error message (on Windows: without waiting
for Enter).

### Unit tests

`tests/test_model.cpp` checks the likelihood, the background and the peak
shapes, and `tests/test_input.cpp` the checks of the data file and of
`config.yaml`. Both are built with AMORPH and run by ctest:

```bash
(cd build && ctest --output-on-failure)
```

### Tests of the Python post-processing

`tests/test_postprocess.py` checks `amorph_stats.py`, `display.py` and
`export_pgf.py` on a synthetic run made by `scripts/make_demo_posterior.py`
(it needs numpy, matplotlib, pandas, pyyaml and pytest):

```bash
python -m pytest tests
```

### Continuous integration

The repository is built on two CI services, which run the same scripts from
`scripts/ci/`:

* GitHub Actions (`.github/workflows/build.yml`), on pushes to master and on
  pull requests: builds the Linux executable and runs the tests and the smoke
  test on it, cross-compiles `AMORPH.exe` with mingw-w64 and runs the smoke
  test on it on a Windows runner. Both executables are uploaded as artefacts.
* GitVerse CI (`.gitverse/workflows/build.yml`), on every push: the same
  Linux build and tests, and the cross-compiled `AMORPH.exe` as an artefact
  (kept for 7 days). GitVerse has no Windows runners, so the executable is
  not run there.

`.github/workflows/validate.yml` compares the results of two versions of
AMORPH: it runs both on the four bundled datasets and writes a table of the
posterior summaries (amorphous fraction, the shape of the wide component,
the noise parameters, the numbers of peaks). It takes hours, so it runs on
demand only: "Run workflow" on the GitHub Actions tab (the reference version
is an input, master by default), or the label `validate` on a pull request
(the reference is the base of the pull request; adding the label again
restarts the comparison). Each sampler run stops after 5000 saves or
210 minutes, whichever comes first (both are inputs of "Run workflow"), and
what it saved by then is post-processed; the log of each run reports the
number of saves and levels every 10 minutes.

`.github/workflows/experiment.yml` runs the two ambiguous samples,
`src/N3RAW_amorph.txt` and `src/G30RAW_amorph.txt`, with four settings of
the maximum numbers of peaks and of `narrow_peak_nu`, twice each with
different seeds (16 runs in parallel, a few hours), and writes a table of
how much posterior weight has an amorphous fraction of 0 or below 0.2.
It is started the same way: "Run workflow", or the label `experiment` on a
pull request.

### Diagnosing the posterior

`scripts/diagnose_posterior.py` tells whether the amorphous fraction of a run
is well determined. Run it on the folder of a finished run, after
`showresults.py`:

```bash
python scripts/diagnose_posterior.py src --data src/easy_data.txt --json diagnosis.json --table particles.csv.gz
```

It prints the posterior weight with a fraction of 0, below 0.2 and below
0.45; for each of these bands the weighted medians of the log likelihood, the
number of narrow peaks and their shape ν, and the misfit; and the weight of
particles with nearly the maximum number of narrow peaks. A band with real
weight at a low fraction, with hundreds of narrow peaks at a small ν and the
same likelihood as the main mode, means that the data do not determine the
fraction. `--table` writes one row per saved particle (a few hundred
kilobytes, instead of the hundreds of megabytes of `sample.txt`).

### The legacy Makefile

`src/Makefile` is the original build system and is still functional on Linux
with a DNest4 checkout in `$DNEST4_PATH`. CMake is the recommended route.

Drawing the fit figure with TikZ
=================================

The `showresults.py` script produces `posterior_sample.txt`, which holds the
posterior samples of the model, of the amorphous (wide) component, of the
crystalline (narrow) peaks and of the background. `src/export_pgf.py` turns
those samples into tables that PGFPlots can read, and `doc/figures/xrd_fit.tex`
draws the figure from them:

```
python showresults.py                     # in src/, writes posterior_sample.txt
python export_pgf.py --data easy_data.txt --out ../doc/figures/pgf
cd ../doc/figures && pdflatex xrd_fit.tex  # writes xrd_fit.pdf
```

or, all at once,

```
bash scripts/make_xrd_figure.sh easy_data.txt
```

The tables that are written into `doc/figures/pgf/` are

| file | contents |
| --- | --- |
| `xrd_data.dat` | x and the measured intensity |
| `xrd_mean.dat` | x and the posterior means of the model, the amorphous component, the crystalline peaks and the background |
| `xrd_samples_model.dat` | x and a number of posterior sample curves of the model |
| `xrd_samples_amorph.dat` | the same for the amorphous component |
| `xrd_samples_xtal.dat` | the same for the crystalline peaks |
| `xrd_samples.tex` | the `\addplot` commands for the faint sample curves |
| `xrd_meta.tex` | LaTeX macros: axis limits, title, amorphous fraction |

Useful options of `export_pgf.py`:

* `--title` sets the title of the figure (it is LaTeX markup, by default the
  chemical formula of the sample).
* `--samples N` is the number of faint posterior sample curves per component
  (`0` switches them off).
* `--max-points N` limits the total number of points in the sample curves, so
  that the figure fits in the memory of pdfTeX. Use `--max-points 0` together
  with `lualatex` for the full resolution.

To use the figure inside `doc/ms.tex` rather than as a standalone PDF, add
`\usepackage{pgfplots}` to the preamble and

```
\def\xrddatadir{figures/pgf/}
\input{figures/xrd_fit_body.tex}
```

`scripts/make_demo_posterior.py` generates a synthetic data set and a matching
`posterior_sample.txt`, which is handy for trying the whole chain out without
running the sampler first.
