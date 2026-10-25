"""
Run archives: everything about an AMORPH run in one compressed file.

The output of the sampler takes hundreds of megabytes or more, mostly the
curves of every saved sample. An archive (.amorph, a zip file) keeps what
the report and the figures of the run need, and the parameters of every
peak of every saved sample, in a few megabytes. showresults.py writes one
in the folder of the run; so does

    python amorph_archive.py [RUN_FOLDER] [--out FILE.amorph]

after the DNest4 post-processing (showresults.py) has written
posterior_sample.txt. To look at an archive later:

    python amorph_archive.py --show FILE.amorph
    python amorph_archive.py --figures FOLDER FILE.amorph

print its report and write its figures as PNG files. Any zip program opens
it too; README.txt inside says what each file holds, and report.html is the
whole report with the figures, for a web browser.
"""

import argparse
import base64
import datetime
import html
import io
import json
import os
import platform
import sys
import time
import zipfile

import numpy as np
import pandas as pd

import amorph_results

FORMAT = "AMORPH run archive"
FORMAT_VERSION = 1

README = """AMORPH run archive
==================

This zip file holds the results of one run of AMORPH, written by
amorph_archive.py. Open report.html in a web browser for the report and the
figures. The other files:

report.txt      the report, as showresults.py prints it
summary.json    the numbers of the report: the data, the settings, the
                sampler (log(Z), information, effective sample size), the
                posterior mean, standard deviation and quantiles of each
                quantity, and the diagnosis of the posterior
manifest.json   when and with what software the archive was written
input/          config.yaml, the DNest4 options file and the data file
dnest4/         levels.txt, sample_info.txt and weights.txt of the sampler
log/            the output of the sampler, where it was kept
sampler.csv     one row per saved sample: level, log likelihood, log(X) and
                posterior weight
particles.csv   one row per saved sample: its parameters, log likelihood,
                posterior weight, amorphous fraction and the shape of its
                wide component
posterior.csv   one row per posterior sample (posterior_sample.txt, equally
                weighted): number of peaks, noise parameters, amorphous
                fraction, shape of the wide component and RMS of model - data
peaks.npz       every peak of every saved sample: particle (row of
                particles.csv, from 0), component (1 narrow, 2 wide),
                center, log_amplitude and width (float32)
curves.npz      x and y of the data; for each curve of the model (bg, wide,
                narrow, model_curve) its posterior mean (_mean), quantiles
                5, 16, 50, 84 and 95% (_quantiles) and the first 50
                posterior samples (_examples); the standardised residuals

Read the .npz files with numpy: numpy.load("curves.npz"), or read the whole
archive with amorph_archive.read() and draw its figures with
amorph_results.FIGURES.
"""


def default_name(results, folder="."):
    """
    The data file and the time of the last save of the run:
    folder/easy_data_2026-10-25_1530.amorph.
    """
    stamp = results.info.get("last_save")
    if stamp:
        stamp = datetime.datetime.fromisoformat(stamp)
    else:
        stamp = datetime.datetime.now()
    stem = os.path.splitext(results.info["data_file"])[0]
    return os.path.join(folder, "{0}_{1}.amorph".format(
        stem, stamp.strftime("%Y-%m-%d_%H%M")))


def _npz(arrays):
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    return buffer.getvalue()


def _csv(frame):
    # Python writes the shortest text that reads back as the same number
    return frame.to_csv(index=False)


def _read_csv(data):
    # pandas 3 reads them back exactly by default; older versions on request
    exact = {} if int(pd.__version__.split(".")[0]) >= 3 \
        else {"float_precision": "round_trip"}
    return pd.read_csv(io.BytesIO(data), **exact)


def figure_png(results, draw, dpi=100):
    """
    One figure of the results as PNG bytes.
    """
    from matplotlib.figure import Figure
    fig = Figure(figsize=(9, 5))
    draw(fig, results)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=dpi)
    return buffer.getvalue()


def html_report(results):
    """
    The report and all the figures in one HTML page.
    """
    info = results.info
    title = "AMORPH: {0}".format(info["data_file"])
    parts = ["<!doctype html>", '<html lang="en">', "<head>",
             '<meta charset="utf-8">',
             "<title>{0}</title>".format(html.escape(title)),
             "<style>body{font-family:system-ui,sans-serif;margin:24px;"
             "max-width:1000px;color:#1b2430}pre{background:#f4f6f8;"
             "padding:12px;overflow-x:auto}img{max-width:100%}"
             "figure{margin:24px 0}</style>",
             "</head>", "<body>",
             "<h1>{0}</h1>".format(html.escape(title)),
             "<h2>Report</h2>",
             "<pre>{0}</pre>".format(html.escape(
                 "\n".join(amorph_results.report_lines(results))))]
    figures = amorph_results.available_figures(results)
    if figures:
        parts.append("<h2>Figures</h2>")
    for name, caption, draw in figures:
        png = base64.b64encode(figure_png(results, draw)).decode("ascii")
        parts.append('<figure id="{0}"><img src="data:image/png;base64,{1}" '
                     'alt="{2}"><figcaption>{2}</figcaption></figure>'.format(
                         name, png, html.escape(caption)))
    config = results.attachments.get("input/config.yaml")
    if config is not None:
        parts.append("<h2>config.yaml</h2>")
        parts.append("<pre>{0}</pre>".format(html.escape(
            config.decode("utf-8", errors="replace"))))
    parts += ["</body>", "</html>", ""]
    return "\n".join(parts)


def write(results, filename):
    """
    Write the results of a run to the archive filename.
    """
    files = {"README.txt": README,
             "report.txt": "\n".join(amorph_results.report_lines(results))
             + "\n",
             "report.html": html_report(results),
             "summary.json": json.dumps(amorph_results.summary(results),
                                        indent=2)}
    files.update(results.attachments)

    if results.sampler is not None:
        s = results.sampler
        files["sampler.csv"] = _csv(pd.DataFrame({
            "level": s["sample_info"][:, 0],
            "log_likelihood": s["sample_info"][:, 1],
            "log_x": s["log_x"], "weight": s["weight"]}))
    if results.particles is not None:
        files["particles.csv"] = _csv(results.particles)
        files["peaks.npz"] = _npz({
            "particle": results.peaks["particle"].astype(np.int32),
            "component": results.peaks["component"].astype(np.int8),
            "center": results.peaks["center"].astype(np.float32),
            "log_amplitude": results.peaks["log_amplitude"]
            .astype(np.float32),
            "width": results.peaks["width"].astype(np.float32)})
    if results.posterior is not None:
        files["posterior.csv"] = _csv(results.posterior)
    curves = dict(results.curves) if results.curves is not None else {}
    curves["x"], curves["y"] = results.x, results.y
    files["curves.npz"] = _npz(curves)

    manifest = {
        "format": FORMAT,
        "version": FORMAT_VERSION,
        "created": datetime.datetime.now().astimezone().isoformat(
            timespec="seconds"),
        "data_file": results.info["data_file"],
        "software": {"python": platform.python_version(),
                     "numpy": np.__version__, "pandas": pd.__version__,
                     "system": platform.platform()},
        "files": sorted(files) + ["manifest.json"],
    }
    files["manifest.json"] = json.dumps(manifest, indent=2)

    with zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(files):
            content = files[name]
            if isinstance(content, str):
                content = content.encode("utf-8")
            z.writestr(name, content)
    return filename


def read(filename):
    """
    The results stored in the archive filename.
    """
    results = amorph_results.Results()
    with zipfile.ZipFile(filename) as z:
        names = set(z.namelist())
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("format") != FORMAT:
            raise ValueError("{0} is not an AMORPH run archive".format(
                filename))
        if manifest.get("version", 0) > FORMAT_VERSION:
            raise ValueError("{0} is an archive of version {1}; this "
                             "program reads version {2} and older".format(
                                 filename, manifest["version"],
                                 FORMAT_VERSION))
        summary = json.loads(z.read("summary.json"))
        results.info = summary["info"]
        results.diagnosis = summary.get("diagnosis")
        results.attachments = {name: z.read(name) for name in names
                               if name.startswith(("input/", "dnest4/",
                                                   "log/"))}

        with np.load(io.BytesIO(z.read("curves.npz"))) as f:
            curves = {key: f[key] for key in f.files}
        results.x, results.y = curves["x"], curves["y"]
        results.curves = curves

        if "sampler.csv" in names:
            table = _read_csv(z.read("sampler.csv"))
            results.sampler = dict(summary["sampler"])
            for key in ("num_levels", "num_saves"):
                results.sampler.pop(key, None)
            results.sampler["levels"] = amorph_results.parse_table(
                results.attachments["dnest4/levels.txt"].decode())
            results.sampler["sample_info"] = amorph_results.parse_table(
                results.attachments["dnest4/sample_info.txt"].decode())
            results.sampler["log_x"] = table["log_x"].to_numpy()
            results.sampler["weight"] = table["weight"].to_numpy()
        if "particles.csv" in names:
            results.particles = _read_csv(z.read("particles.csv"))
            with np.load(io.BytesIO(z.read("peaks.npz"))) as f:
                results.peaks = {key: f[key] for key in f.files}
        if "posterior.csv" in names:
            results.posterior = _read_csv(z.read("posterior.csv"))
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("source", nargs="?", default=".",
                   help="the folder of a run (default: this one), or an "
                        "archive with --show or --figures")
    p.add_argument("--out", help="the archive to write; by default the "
                                 "name of the data file and the time of the "
                                 "last save, in the folder of the run")
    p.add_argument("--range", nargs=2, type=float, metavar=("LOW", "HIGH"),
                   help="also give the amorphous fraction within this range "
                        "of x")
    p.add_argument("--show", action="store_true",
                   help="print the report of the archive SOURCE")
    p.add_argument("--figures", metavar="FOLDER",
                   help="write the figures of SOURCE as PNG files to FOLDER")
    args = p.parse_args()

    if os.path.isdir(args.source):
        if not os.path.isfile(os.path.join(args.source,
                                           "posterior_sample.txt")):
            print("amorph_archive: {0} has no posterior_sample.txt; run "
                  "showresults.py there first for the posterior samples"
                  .format(args.source), file=sys.stderr)
        start = time.time()
        results = amorph_results.from_run(args.source,
                                          fraction_range=args.range)
        if not (args.show or args.figures) or args.out:
            out = args.out or default_name(results, args.source)
            write(results, out)
            print("Wrote {0} ({1:.1f} MB) in {2:.0f} s".format(
                out, os.path.getsize(out) / 1E6, time.time() - start))
    else:
        results = read(args.source)

    if args.show:
        print("\n".join(amorph_results.report_lines(results)))
    if args.figures:
        os.makedirs(args.figures, exist_ok=True)
        for name, _, draw in amorph_results.available_figures(results):
            with open(os.path.join(args.figures, name + ".png"), "wb") as f:
                f.write(figure_png(results, draw))
        print("Wrote the figures to {0}".format(args.figures))


if __name__ == "__main__":
    main()
