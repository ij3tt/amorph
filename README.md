AMORPH
========

(c) 2016–2018 [Brendon J. Brewer](https://www.stat.auckland.ac.nz/~brewer/)
and [Michael Rowe](http://www.env.auckland.ac.nz/people/michael-rowe)

AMORPH is free software, released under the GNU General Public License,
version 3. See the LICENSE file for details.

*Русская версия этого файла: [README.ru.md](README.ru.md).*

Downloads
=========

Each release of AMORPH on the
[Releases page](https://github.com/ij3tt/amorph/releases) has the
command-line version and the graphical interface (see "The graphical
interface" below) for three systems, ready to run:

| file | system |
|---|---|
| `AMORPH-<tag>-windows-x64.zip` | Windows 10 or newer, 64-bit (x86-64) |
| `AMORPH-<tag>-linux-x64.tar.gz` | Linux on x86-64 with glibc 2.34 and the libstdc++ of GCC 13 or newer: Ubuntu 24.04, Debian 13, Fedora 39 or newer |
| `AMORPH-<tag>-macos-arm64.zip` | macOS 11 or newer on Apple Silicon (M1 or newer) |
| `AMORPH-GUI-<tag>-windows-x64.zip` | the graphical interface, Windows 10 or newer, 64-bit |
| `AMORPH-GUI-<tag>-linux-x64.tar.gz` | the graphical interface, Linux on x86-64 (built on Ubuntu 24.04, as the command-line version) |
| `AMORPH-GUI-<tag>-macos-arm64.zip` | the graphical interface, macOS on Apple Silicon |
| `AMORPH-<tag>-SHA256SUMS.txt` | the SHA-256 checksums of the six |

`<tag>` is the version, such as `v1.0.1`; [CHANGELOG.md](CHANGELOG.md) says
what changed in each. From v1.0.2 on, the releases are also on
[GitVerse](https://gitverse.ru/ijjjjke/amorph/releases), apart from the
GUI package for Linux, which is larger than GitVerse allows. Each archive holds one folder, `AMORPH-<tag>-<system>`,
with

* `AMORPH` (`AMORPH.exe` on Windows), the sampler;
* the Python post-processing: `showresults.py` and the modules it uses,
  `display.py`, `dnest_functions.py`, `amorph_stats.py`,
  `amorph_results.py` and `amorph_archive.py`;
* `config.yaml`, the settings of a run, set up for `easy_data.txt`;
* `OPTIONS` and `OPTIONS_AGGRESSIVE`, the settings of the DNest4 sampler;
* `easy_data.txt`, an example dataset (the others are in `src/` of the
  repository);
* `README.md` and `README.ru.md` (this file), `LICENSE` (GNU GPL version 3)
  and, in `licenses/`, the licences of the libraries built into the
  executable: DNest4, yaml-cpp and, on Windows, the mingw-w64 runtime.

An archive of the graphical interface holds one folder, `AMORPH-GUI`, with
the program and everything it needs, the sampler included: Python and its
packages need not be installed. Unpack it anywhere and start
`AMORPH-GUI.exe` (Windows), `AMORPH-GUI.app` (macOS) or `./AMORPH-GUI`
(Linux) in that folder. It is about 100–200 MB unpacked. The folder also has
the READMEs, `LICENSE` and, in `licenses/`, the licences of what the program
bundles (Qt for Python is under the GNU LGPL; its libraries are separate
files of the program).

Unpack a command-line archive anywhere and run AMORPH in that folder: it
reads `config.yaml` from the folder it runs in (see "Guide to installing and
operating" below).
On Linux and macOS that is `./AMORPH` in a terminal; on Windows a double
click on `AMORPH.exe` works too. The source code of a release is on its page
as well. The executables that CI builds for every change are artefacts of
the GitHub Actions runs, which expire after a few weeks; the releases stay.

To check a download against the checksums: on Linux
`sha256sum -c --ignore-missing AMORPH-<tag>-SHA256SUMS.txt`; on macOS
`shasum -a 256 AMORPH-<tag>-macos-arm64.zip`, and on Windows
`Get-FileHash AMORPH-<tag>-windows-x64.zip` in PowerShell, each compared
with its line of the file.

### The executables are not signed

Windows and macOS warn before they run a downloaded program that is not
signed by a known developer, and the executables of AMORPH are not.

**Windows (SmartScreen).** The first time `AMORPH.exe` is started by a
double click, Windows may show "Windows protected your PC". Click "More
info", then "Run anyway". Or, before unpacking the zip file: right click
it → Properties → tick "Unblock" → OK; the unpacked files then carry no
mark of a download.

**macOS (Gatekeeper).** macOS refuses to open `AMORPH` the first time
("cannot be opened because the developer cannot be verified", or "Apple
could not verify..."). Allow it once:

* macOS 14 and older: in the Finder, right click (or Control-click)
  `AMORPH` → Open, and Open again in the dialog;
* macOS 15 and newer: try to open it once, then System Settings → Privacy &
  Security, and "Open Anyway" next to the message about `AMORPH`;
* or, in Terminal in the folder of AMORPH, remove the mark of the download:
  `xattr -d com.apple.quarantine AMORPH`.

Opened from the Finder, AMORPH runs in a Terminal window in your home folder
and stops at once, since it finds no `config.yaml` there; that is expected.
From then on run it from its folder in Terminal: `cd` to the folder, then
`./AMORPH`. The Python scripts need none of this.

The graphical interface is allowed the same way, once: `AMORPH-GUI.exe` on
Windows, and `AMORPH-GUI.app` on macOS, or in Terminal in its folder
`xattr -dr com.apple.quarantine AMORPH-GUI.app` (`-r`: the app is a folder
of files). It runs the sampler packed inside it, which then needs nothing
more.

**The first start of the interface is slow.** The first time after
unpacking, the interface may take up to a minute to open, while the system
checks every file of it: Microsoft Defender on Windows looks unsigned files
up in its cloud, and Gatekeeper on macOS checks them too. The AMORPH splash
screen shows at once with the step under way, and the window opens by
itself: do not start the program again, which only opens another copy.
Later starts take a few seconds.

Guide to installing and operating:
==================================

AMORPH is hosted at the following URL:

[https://bitbucket.org/eggplantbren/amorph]([https://bitbucket.org/eggplantbren/amorph)

The repository includes the source code, Python scripts for viewing results
and example datasets, most of them in the `src` subdirectory. The easiest way
of using AMORPH is a release, with the executable for your system (see
"Downloads" above).
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
the ambiguity described in "The shape of the crystalline peaks" below. The
whole scans of these two samples (Cu Kα, 5–70°, step 0.02°) are
`G30RAW.txt` and `N3RAW.txt`, and `*_20-50.txt` and `*_15-70.txt` are
parts of them.
The program is set to run until
10,000 saved parameter sets have been generated. Outputs may be viewed at any
point, however, closing the program before reaching  10,000 will reduce the
accuracy of the final calculations. After running for a while, the output can
be viewed by running the Python script `showresults.py`:

```
python showresults.py
```

It prints the report of the run: log(Z), the information and the
effective sample size of the sampler, the amorphous fraction and the shape
of the wide component (mean ± standard deviation over the posterior
samples), and the diagnosis of the posterior (see "Diagnosing the
posterior" below). It writes `macroquantities.csv`, one row per posterior
sample, and a run archive (below), and then shows the figures one after
another: the levels of the sampler, the compression and acceptance of the
levels, the likelihood and the posterior weights against log(X), the model
with its parts and the data, the residuals, and the histograms of the
number of narrow peaks, of the amorphous fraction and of the centre,
half-width, skewness and nongaussianity of the wide component.

### Run archives

The next run overwrites the output files, which take hundreds of
megabytes or more. `showresults.py` therefore also stores the results in
one compressed file in the folder of the run, named after the data file and
the time of the last save, such as `easy_data_2026-10-25_1530.amorph`. It
is a zip file of a few megabytes with

* `report.html`: the report and all the figures, for a web browser;
* `report.txt` and `summary.json`: the report as text, and its numbers for
  programs;
* `input/`: `config.yaml`, the DNest4 options and the data file, and
  `dnest4/`: `levels.txt`, `sample_info.txt` and `weights.txt`;
* `particles.csv`: one row per saved sample, with its parameters, log
  likelihood, posterior weight, amorphous fraction and the shape of its
  wide component; `posterior.csv`: the same for the posterior samples;
* `peaks.npz`: the position, log amplitude and width of every peak of
  every saved sample;
* `curves.npz`: the posterior mean, the 5, 16, 50, 84 and 95% quantiles and
  50 posterior samples of the background, the wide and narrow components
  and the model.

`README.txt` in the archive describes each file. To write an archive of a
run folder, print the report of an archive or write its figures:

```
python amorph_archive.py RUN_FOLDER [--out FILE.amorph]
python amorph_archive.py --show FILE.amorph
python amorph_archive.py --figures FOLDER FILE.amorph
```

In Python, `amorph_archive.read("FILE.amorph")` gives back the results of
the run, and `amorph_results.FIGURES` draws each figure of them on a
matplotlib figure.

The graphical interface
=======================

`src/amorph_gui` is a desktop program for all of the above: it opens a
data file, sets up and runs the sampler for one or more seeds, and shows
and compares the results. Its text is in Russian (all of it is in
`src/amorph_gui/strings.py`, so that it can be translated).

Each release has it packaged for Windows, Linux and macOS, with the
sampler inside, ready to run (see "Downloads"). CI packages it with
PyInstaller (`packaging/amorph_gui.spec`, `scripts/ci/gui_package.sh`) on
each system and runs the self-test of the packaged program there; the
packages of every change are artefacts of the Build runs.

From the source code it needs PySide6 and pyqtgraph besides the packages
of the post-processing, and the AMORPH executable (see "Using the source
code"):

```
pip install PySide6 pyqtgraph
cd src
python -m amorph_gui [FILE]
```

`FILE`, if given, is a data file or a run archive to open. The program
runs the AMORPH executable that is next to it (in `src/`, in `build/` of a
CMake build of the repository, or inside the packaged program) or on the
PATH, unless «Настройки…» (or `--amorph PATH`) names another.

It has four screens, listed on the left:

* «Данные и модель»: the data file, read with the rules of the sampler
  (an error names the file and the line), on a plot on which the range to
  analyse and the two background control points are dragged. A band
  shows where the wide peaks may be (`left_edge` and `right_edge`, as
  fractions of the analysed range). The form has every setting of
  `config.yaml`, with the limits that AMORPH enforces, the DNest4 options
  file (`OPTIONS_AGGRESSIVE` or `OPTIONS`) with its maximum number of
  saves, and the number of seeds; it starts with `narrow_peak_nu: [1.0,
  100.0]`. Before a run it checks that the control points lie in the
  analysed range, warns when the data do not reach beyond them on either
  side or when the lower bound of ν is below 1 (see "Recommended settings
  and calibration"), and starts nothing while there is an error.
  «Загрузить config.yaml…» and «Сохранить config.yaml…» read and write
  the settings.
* «Прогоны»: each seed gets a folder `runs/<date>_<data>_seed<k>/` (in
  the folder set in «Настройки…», by default `runs/` in the current one)
  with `config.yaml`, the options file and the points of the analysed
  range: AMORPH has no setting for the range, so the program writes them
  there. The seeds (seed, seed + 1, ...) run one after another. The
  screen shows the number of saves and levels and the time, the output of
  the sampler (also kept in the folder as `run.log`), and the estimate of
  the run so far, computed every second (less often on a slow computer or
  late in a long run, when it takes longer) from all its saves with their
  posterior weights, as the post-processing computes them: the median of
  the amorphous fraction with its 50% and 90% intervals, a plot of how
  they moved over the saves, the effective sample size and log(Z), and
  whether the estimate has settled (its median moved by less than 0.005
  over the last 20% of the saves, at least 1000, since the levels were
  built). The model plot shows the background, the amorphous halo, the
  crystalline peaks and the model, each a layer that can be hidden, for
  the posterior mean so far (with the 90% band of the model), the best
  sample so far, or the last saved sample, with the level of each among
  the levels of the sampler. The last saved sample alone says little:
  once the levels are built, the sampler sends its particles down to low
  levels on purpose, and in a long run about two saves in three fit worse
  than 99% of the posterior. «Остановить» stops the sampler, keeps its
  complete saves, post-processes them and marks the run as incomplete;
  the seeds still waiting are cancelled.

  «Открыть прогоны…» opens runs done earlier or on another computer: a
  run folder (one with `config.yaml`, `sample_info.txt` and
  `levels.txt`), or a folder with run folders in it, down to two levels.
  Run folders and archives can also be dragged onto the window, many at a
  time. Each run then shows on «Прогоны» with its output and its estimate
  (the trace is rebuilt from its saves, which takes about 20 seconds for
  10 000 saves), on «Результаты» and on «Сравнение». Its results come
  from its archive if it is up to date; otherwise it is post-processed as
  at the end of a run, which writes `posterior_sample.txt` and the archive
  into its folder.
* «Результаты»: each run is post-processed as `showresults.py` does it,
  and its archive is written in its folder. The tabs: «Итог», the median
  of the amorphous fraction with its 50% and 90% intervals, cards for the
  diagnosis (red when more than 5% of the posterior weight has a fraction
  below 0.2; amber when more than 5% is at the cap of narrow peaks, when
  the control points lie outside the data, or when the run stopped before
  its planned number of saves) and the effective sample size; «Модель»,
  «Распределения» and «Сэмплер», the figures of `showresults.py` (the
  last with log(Z), the information and the effective sample size); and
  «Полный отчёт», the report. Each figure saves as PNG, and the archive,
  the posterior samples (CSV) and the tables of PGFPlots that
  `export_pgf.py` writes («Данные для PGFPlots…», see "Drawing the fit
  figure with TikZ") save too.
* «Сравнение»: a table of run archives, such as the seeds of a batch,
  all the archives of a folder, or the `run.amorph` files that the
  experiment and validate workflows upload. Every run shown on
  «Результаты» has a row here, once: a run done here (a single seed too),
  a run opened from its folder, an archive opened.
  Per archive: the data file, the settings, the seed, the options file of
  the sampler and its saves, the effective sample size, log(Z) less the
  best log(Z) of the runs of the same data and settings, the median of the
  fraction with its 50% interval, also drawn as a bar on a scale common
  to all rows, the posterior weight below 0.2 and at the cap, and the
  checks of the run. A log(Z) 5 nats or more below the best marks a run
  that did not converge (between seeds that did it differs by 2-3 nats,
  see "Recommended settings and calibration"); so does over 5% of the
  weight below 0.2. Such runs are unticked; the others are ticked. The
  ticked runs make the joint report: the fraction of all of them
  together, each seed counting equally and its saves keeping their
  posterior weights, its intervals, the spread of the medians of the
  seeds against the width of the 50% interval, warnings for runs of other
  settings or with a low log(Z), and a line for a paper. Its figure, in
  the style of `doc/figures/xrd_fit.tex` or with two panels (the scan
  with its parts and the halo of each seed, and the distribution of the
  fraction of each seed and pooled, `doc/figures/xrd_seeds.tex`), is
  previewed and exported: «Данные для PGFPlots…» writes the tables of
  both figures, «TeX…» a folder with the figure, its tables and
  `build.bat` / `build.sh`, «PDF…» and «SVG…» build it with the LaTeX
  installed (TeX Live or MiKTeX: `pdflatex`, and `latex` with
  `dvisvgm`), «PNG…» saves the preview. «Отчёт LaTeX…» writes a folder
  with `report.tex`, the whole report to build with `pdflatex
  report.tex`: the result and the line for a paper, the table of the
  runs with their checks, the data and the settings, the diagnostic
  cards of each seed, both figures with their tables in `pgf/`, and how
  to read the numbers, in Russian or in English as chosen in the menu of
  the button; it needs pgfplots, babel with Russian and the cm-super
  fonts. «Отчёт LaTeX…» on «Результаты» does the same for one
  run. The table exports as CSV and Markdown.

«Открыть архив…», on every screen, shows an archive on «Результаты».
A «?» next to a card, a figure or a group of settings explains in plain
words what it shows (the 50% and 90% intervals, the levels, ESS,
log(Z), the checks, each figure), and «Справка» (F1) has all these
explanations on one page; the numbers, columns and buttons explain
themselves in their tooltips. As «Итог» says, the fraction is a ratio of integrated intensities, not a
mass fraction, and the spread between seeds is the run-to-run error of
the sampler, not the posterior interval (see "Recommended settings and
calibration"). The numbers and figures are those of `amorph_stats.py`,
`amorph_results.py` and `amorph_archive.py`.

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

Background positions. The paper uses linear fits between 10–40° 2theta
with CuKa x-ray sources: the background is a straight line under the
amorphous halo and may bend outside it. The control points therefore belong
where the halo ends, and their choice can change the result noticeably: see
"Recommended settings and calibration". For some analyses, typically when more data points are analysed
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
along with the results. In the experiments summarised under "Recommended
settings and calibration" this range removed the low mode in every run on
N3RAW and G30RAW.
`.github/workflows/experiment.yml` compares such
settings on these two samples.

`config.yaml` may also set `seed`, a whole number from 0 to 4294967295, for
the random number generator of the sampler; without it the time is used.


Recommended settings and calibration
====================================

The experiments on the bundled samples (pull requests #5, #6, #7 and #10,
and later runs, all by `.github/workflows/experiment.yml`) motivate one
setting that differs from the paper, show how much the background control
points and the range of 2θ matter, and give a first look at the accuracy
on three standards. Each material is a single dataset run with a few seeds:
read the numbers below as what was observed on these samples, not as
general accuracies.

* `narrow_peak_nu: [1.0, 100.0]`. With ν < 1 the posterior of the fraction
  can have a second mode at or near 0 (see "The shape of the crystalline
  peaks"); with ν ≥ 1 this mode had no weight in any of the runs on N3RAW
  and G30RAW. This is a change to the model of the paper: report it along
  with the results.
* `control_points`: measure, and analyse, a range of 2θ that reaches well
  beyond the amorphous halo on both sides, and keep the background straight
  under the whole halo, with the control points where the halo ends.
  - With data well beyond the halo, the edges of the data do this. On the
    90% glass standard (5–50°) control points at the edges, `[5, 50]`, gave
    0.83–0.84 against 0.79–0.80 with `[10, 40]`. On the 0% and 50% standards
    the two choices differed by no more than the spread between seeds, apart
    from one collapsed run with `[10, 40]` on the 0% standard (0.33). On
    N3RAW and G30RAW cut to 20–50° (halo near 29–40°), the background
    straight from edge to edge, `[20, 50]`, had a log(Z) about 10 nats higher
    than control points at `[25, 45]` on both samples, more than the 2–3
    nats between seeds: the data favour it. log(Z) compares choices only on
    the same data file.
  - Without data beyond the halo the background is not pinned, and the
    result depends on the choice. On `N3RAW_amorph.txt` (26–46°, halo
    centred near 35°) the fraction was 0.72 with `[10, 40]` and 0.63 with
    `[26, 46]`. The whole scan (`N3RAW.txt`, 5–70°) settled it: with the
    background pinned by data on both sides, the fraction within 26–46° was
    0.56–0.68 in every run, never 0.72, and 0.65–0.68 in the ten runs with
    the straight background over 20–50°. The 0.72 came from the control
    point at 10°, outside the data, where the background was extrapolated:
    AMORPH warns about such a control point. G30RAW gave 0.71–0.73 within
    26–46° on 20–50° with either choice of control points, as it did on
    26–46° alone, and 0.72–0.77 on 15–70°.
  - Even with data beyond the halo some choice remains. On N3RAW cut to
    20–50° the reasonable choices (control points at the edges or at 25°
    and 45°) spread the fraction within 26–46° over 0.63–0.68, more than
    the spread between seeds (0.01–0.02). Prefer the choice with the higher
    log(Z), and quote the spread over the others as an uncertainty of the
    result: for N3RAW within 26–46°, about 0.66, and 0.63–0.68 over the
    reasonable choices.
  - A wider range is not better. On 15–70° (with `left_edge: 0.2`,
    `right_edge: 0.95`, see below, and the caps raised to 1000/200) four
    seeds of 10000 saves gave fractions spread over 0.05–0.1 between seeds,
    against about 0.01 on 20–50°: for N3RAW 0.63–0.68 over 15–70° and
    0.56–0.66 within 26–46°, for G30RAW 0.72–0.78 and 0.72–0.77. The
    posterior has several modes, and the seeds settle in different ones.
    The N3RAW run with 0.56 had a log(Z) of −9581, 15–20 nats below the
    others (−9561 to −9566): a run whose log(Z) is well below that of the
    other seeds on the same data has missed most of the posterior, and is
    left out or run again. Analyse a range that reaches just beyond the
    halo, such as 20–50° here; on a wider one, run four or more seeds and
    quote their spread.
* The fraction depends on the range of 2θ it is integrated over: quote the
  range with it. Make sure that `left_edge` and `right_edge` let the wide
  peaks lie under every amorphous hump in the range. By default they cover
  0.3–0.7 of it: on 15–70° that is 31.5–53.5°, which leaves out the second
  hump of N3RAW and G30RAW near 60°. With `left_edge: 0.2` and
  `right_edge: 0.95` (26–67°) the wide component took in both humps, and
  the fraction over 15–70° was 0.63–0.68 for N3RAW and 0.72–0.78 for
  G30RAW, against 0.63–0.66 and 0.69 over 20–50°.
* Comparing samples measured and analysed the same way is more robust than
  any single fraction: G30RAW came out more amorphous than N3RAW by 0.04–0.08
  on 20–50° with either choice of control points, and by 0.10 on average
  over 15–70°, where single runs scatter more.
* `max_num_narrow_peaks: 500` and `max_num_wide_peaks: 100`. On the
  standards, doubling the caps did not move the measured fraction but made
  the runs up to twice as long. Raise them to 1000/200 if the diagnosis
  (below) shows a large posterior weight at the cap (say, above 20%).

Most of these runs were made before the faster sampler of pull request #14,
which has the same model. Four seeds of 10000 saves each, before and after
it, gave the same results within the spread between seeds: on N3RAW over
20–50° a fraction of 0.640–0.645 before and 0.632–0.641 after (0.659 and
0.656 within 26–46° on average), on the 50% standard 0.498–0.507 and
0.496–0.512, while the uncertainty of each run was ±0.02–0.04; log(Z)
differed by less than its spread between seeds (0.5 nats on N3RAW, 3 on
the 50% standard). The faster sampler made 2.4–3.2 times as many saves per
minute.

Standards
---------

Three of the bundled samples have known glass contents: the 0% (rhyolite)
and 90% (basalt) standards, measured over 5–50°, and the 50% one, measured
over 10–40° with a different step. With ν ≥ 1 and the control points at the
edges of the data (pull request #7: four seeds with each of the two caps),
the medians of the runs were:

| true fraction | measured | remarks |
| --- | --- | --- |
| 0% | 0.00 – 0.05 | several posteriors collapsed onto one value; up to 72% of the weight at the cap of 500 narrow peaks; 3 of the 4 runs with the cap of 1000 stopped by the time budget |
| 50% | 0.50 – 0.53 | |
| 90% | 0.82 – 0.85 | 3 of the 4 runs with the cap of 1000 stopped by the time budget |

What this shows, and what it does not:

* AMORPH measures the ratio of the integrated intensities of the two
  components (`src/amorph_stats.py`), not the mass fraction of glass. How
  the two are related depends on the material and the instrument; the paper
  builds a calibration curve for that. Turning a measured fraction into a
  glass content needs standards of the same kind of material, measured on
  the same instrument over the same range of 2θ.
* These three standards are different materials measured over different
  ranges, and some of their runs are not settled by the criteria below.
  They show the size of the effect at the ends of the scale, about +3
  points at 0% and about −7 points at 90%, but they are not a calibration
  curve: do not correct the fractions of other samples with them. N3RAW and
  G30RAW in particular are other materials, measured over 5–70°.
* The spread between seeds, about ±1–2 points at 50% and 90%, is the
  run-to-run spread of the sampler on one data file. It is neither the
  accuracy of the method nor the reproducibility of a measurement, which
  needs repeated measurements of the sample.

Diagnosis and reporting
-----------------------

Always run `scripts/diagnose_posterior.py` (see "Diagnosing the posterior")
before quoting a fraction:

* A large weight at the cap of narrow peaks (above ~20%) means the prior
  limit, not the data, sets their number: rerun with the caps doubled.
* A collapsed posterior (a tiny [q25, q75] interval) or a low effective
  sample size means the run is not settled: rerun with a different `seed`.
* Near 0% or 100% the sampler sometimes locks onto exactly 0 or 1; read
  fractions below ~0.05 as "approximately zero", and rerun with a second
  seed for fractions above ~0.9.
* A run that the time budget stopped before its planned number of saves is
  preliminary.

Run important samples with at least two seeds, and quote the spread between
them separately from the posterior interval: the interval is the
uncertainty given the data, the spread the run-to-run error of the
sampler. Quote the range of 2θ and the control points with the fraction,
and, where the choice of them moves the fraction more than the seeds do,
that spread too.


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
for Enter), and that the first line of the output is `# AMORPH` and the
version of `CMakeLists.txt`.

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

### Tests of the graphical interface

`tests/gui/` tests the GUI without a screen: the form writes and reads
`config.yaml` back unchanged, the checks before a run, an archive of the
fake run of `tests/test_results.py` on «Результаты», the comparison table,
and the runs, stops and failures of a fake sampler. They need PySide6,
pyqtgraph and pytest-qt, and are skipped without them:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/gui
```

The self-test runs the bundled `easy_data.txt` with the tiny DNest4
options of the smoke test through the GUI itself: two seeds to the end
and a third that it stops, their post-processing and archives, the
comparison and an archive opened again. It saves a screenshot of every
screen to the folder it is given, and the runs to `runs/` in it:

```bash
cd src
QT_QPA_PLATFORM=offscreen python -m amorph_gui --self-test ../build/gui-self-test --amorph ../build/AMORPH
```

### Continuous integration

The repository is built on two CI services, which run the same scripts from
`scripts/ci/`:

* GitHub Actions (`.github/workflows/build.yml`), on pushes to master and on
  pull requests: builds the Linux executable and runs the tests and the smoke
  test on it, cross-compiles `AMORPH.exe` with mingw-w64 and runs the smoke
  test on it on a Windows runner, and builds and tests the macOS executable
  (Apple Silicon) on a macOS runner. The executables and the run archive of
  the Linux smoke test, with its figures, are uploaded as artefacts. A
  fifth job runs the tests of the graphical interface and its self-test
  on Linux without a screen (`scripts/ci/gui.sh`) and uploads the
  screenshots and the archives of the self-test (`gui-screenshots`).
* GitVerse CI (`.gitverse/workflows/build.yml`), on every push: the same
  Linux build and tests, and the cross-compiled `AMORPH.exe` as an artefact
  (kept for 7 days). GitVerse has no Windows runners, so the executable is
  not run there.

### Releases

`.github/workflows/release.yml` makes the releases of "Downloads". It runs
the jobs of `build.yml` (the builds, the tests and the smoke tests of the
three systems), then `scripts/ci/package_release.sh` packs their artefacts
with the READMEs and the licences and writes the checksums. To release
version 1.2.0:

1. Set the version in `project(AMORPH VERSION 1.2.0 ...)` of
   `CMakeLists.txt` and in `AMORPH_VERSION` of `src/amorph_results.py`
   (the tests check that the two agree; AMORPH prints it in the first line
   of its output, and run archives record it in `manifest.json`), and add a
   section `## 1.2.0` to `CHANGELOG.md`.
2. Optionally, a dry run: "Run workflow" for Release on the GitHub Actions
   tab. It builds and packs everything, named after the version of
   `CMakeLists.txt`, and uploads it as the artefact `release-v1.2.0`,
   without making a release; the summary of the run shows the notes. A
   pull request that changes `CHANGELOG.md`, `release.yml` or its scripts
   gets the same dry run.
3. Tag the commit and push the tag to GitHub: `git tag v1.2.0` and
   `git push origin v1.2.0`. The workflow stops unless the tag is
   `v` and the version of `CMakeLists.txt`. It makes the GitHub Release of
   the tag with the files, its notes taken from the section of the version
   in `CHANGELOG.md`; an annotated tag whose message has more than one line
   (`git tag -a v1.2.0`) gives its message as the notes instead.

To try a version before its release, tag a pre-release first:
`git tag v1.2.0-rc.1` and `git push origin v1.2.0-rc.1` (or `-beta.1`,
`-alpha.1`), on the commit to try, with the version of `CMakeLists.txt`
already set. The workflow builds the same files, named after the tag, and
makes a GitHub pre-release with the notes of the version. Pre-releases are
not pushed to GitVerse; once the version is good, tag the release as
above.

`.gitverse/workflows/release.yml` mirrors the release to GitVerse when the
same tag is pushed there (`git push gitverse.ru v1.2.0`): it waits for the
GitHub Release, downloads its seven files, verifies their SHA-256 checksums
and publishes them with the same notes. The GitVerse repository needs a
GitVerse API key with Repositories → Write permission in the secret
`RELEASE_API_KEY` (GitVerse does not take secret names that start with
`GITVERSE_`); without it the mirror stops at once. GitHub took
about 16 minutes to build the release of v1.0.0, and the mirror waits up to
20 minutes of its 30 (`scripts/ci/download_release.sh`). If the GitHub
Release takes longer, the mirror fails and says so: once the GitHub Release
has all seven files, choose "Run workflow" for Release on GitVerse, on the
tag or with the tag in its field. `scripts/ci/gitverse_release.sh` makes
the release and uploads the files through the API of GitVerse, with ten
minutes and retries per file, and skips the files the release has already:
a second run completes a release that a first one left half done. (The
release action of GitVerse, used up to v1.0.2, gave up on the GUI package
for Windows after about 10 seconds and left the release of v1.0.2 with one
file: "Run workflow" on master with the tag v1.0.2 uploads the rest.)

GitVerse takes release files of up to 100 MB, and 4 GB of releases per
account. A larger file, such as the GUI package for Linux (about
120 MB), stays on GitHub only: the notes of the GitVerse Release link to
it. GitVerse has the releases from v1.0.2 on: v1.0.0 was tagged before
the workflow existed, and the workflow of v1.0.1 asks for a secret name
that GitVerse refuses, so these two are on GitHub only.

`.github/workflows/validate.yml` compares the results of two versions of
AMORPH: it runs both on the four bundled datasets and writes a table of the
posterior summaries (amorphous fraction, the shape of the wide component,
the noise parameters, the numbers of peaks) and of the speed of each run
(saves per minute). It takes hours, so it runs on
demand only: "Run workflow" on the GitHub Actions tab (the reference version
is an input, master by default), or the label `validate` on a pull request
(the reference is the base of the pull request; adding the label again
restarts the comparison). Each sampler run stops after 5000 saves or
210 minutes, whichever comes first (both are inputs of "Run workflow"), and
what it saved by then is post-processed; the log of each run reports the
number of saves and levels every 10 minutes.

`.github/workflows/experiment.yml` runs bundled datasets with the settings
listed in `scripts/ci/experiment_settings.json` (the maximum numbers of
peaks, `narrow_peak_nu`, `control_points` and, optionally, other settings
of `config.yaml`), each with several seeds, all in parallel, and writes a
table of the amorphous fraction and of how much posterior weight has a
fraction of 0 or below 0.2. With `"fraction_range"` it also gives the
fraction within that range, to compare runs on different ranges of one
scan. It is started the same way: "Run workflow", or the label
`experiment` on a pull request.

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
`--range LOW HIGH` also gives the fraction within that range of x.

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
python export_pgf.py --out ../doc/figures/pgf
cd ../doc/figures && pdflatex xrd_fit.tex  # writes xrd_fit.pdf
```

and, for an SVG file, through LaTeX too:

```
latex xrd_fit.tex                                # writes xrd_fit.dvi
dvisvgm --no-fonts --exact-bbox xrd_fit.dvi      # writes xrd_fit.svg
```

In the GUI, «Данные для PGFPlots…» on «Результаты» writes the same tables
for a run, and «Сравнение» writes them for the ticked seeds together,
with those of `doc/figures/xrd_seeds.tex`, the figure of several seeds:
(a) the scan with the background, the amorphous halo, the crystalline
peaks, the model and its 90% band, and the halo of each seed; (b) the
distribution of the fraction of each seed and pooled. Its tables are
`seeds_curves.dat` (x, background, halo, model, crystalline peaks and
the band), `seeds_halo.dat`, `seeds_fraction.dat`, the `\addplot` lists
`seeds_halos.tex` and `seeds_densities.tex`, and the macros
`seeds_meta.tex`; it needs `\usepgfplotslibrary{fillbetween,groupplots}`.

or, all at once,

```
bash scripts/make_xrd_figure.sh
```

The data file is the one `config.yaml` names in `data_file`, as for the
sampler; `--data` (or the first argument of `make_xrd_figure.sh`) names
another, and `--config` another `config.yaml`.

The tables that are written into `doc/figures/pgf/` are

| file | contents |
| --- | --- |
| `xrd_data.dat` | x and the measured intensity |
| `xrd_mean.dat` | x and the posterior means of the model, the amorphous component, the crystalline peaks and the background |
| `xrd_samples_model.dat` | x and a number of posterior sample curves of the model |
| `xrd_samples_amorph.dat` | the same for the amorphous component |
| `xrd_samples_xtal.dat` | the same for the crystalline peaks |
| `xrd_samples.tex` | the `\addplot` commands for the faint sample curves |
| `xrd_meta.tex` | LaTeX macros: axis limits, title, amorphous fraction: the median with its 50% interval (`\xrdamorph`, as $62.1^{+3.0}_{-3.9}$ %; the numbers in `\xrdamorphmedian`, `\xrdamorphlo`, `\xrdamorphhi`) |

The first line of every `.dat` file contains column names without a comment
prefix, for example `x model amorph xtal background`. The tables can therefore
be imported not only into PGFPlots, but also into Origin or LabPlot by selecting
the first line as the header and whitespace as the separator.

Useful options of `export_pgf.py`:

* `--title` sets the title of the figure, as LaTeX markup, for example the
  chemical formula of the sample: `--title '$\mathbf{Zr_{48}Ni_{15}Cu_{24}Al_{13}}$'`.
  By default it is the name of the data file. The fonts of the figure have
  no Cyrillic: for a file named in Cyrillic, give a title in Latin letters.
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
