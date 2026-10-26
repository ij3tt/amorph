"""
Export the results of an AMORPH run to tables that PGFPlots can read.

Usage (run from the folder holding posterior_sample.txt):

    python export_pgf.py --out ../doc/figures/pgf

Inputs
------
data_file           The two-column text file that was analysed: by default
                    the data_file of config.yaml (--config), or --data.
posterior_sample.txt
                    Written by `python showresults.py` (DNest4 postprocess).
                    Its first line holds the comma-separated column names.

Outputs (written into the --out folder)
--------------------------------------
xrd_data.dat             x and the measured intensity
xrd_mean.dat             x and the posterior means of the model, the
                         amorphous (wide) component, the crystalline
                         (narrow) peaks and the background
xrd_samples_model.dat    x and a number of posterior sample curves of the
xrd_samples_amorph.dat   complete model, of the amorphous component and
xrd_samples_xtal.dat     of the crystalline peaks
xrd_meta.tex             LaTeX macros: axis limits, title, amorphous
                         fraction and the number of sample curves

The tables are consumed by doc/figures/xrd_fit.tex.
"""

import argparse
import os
import numpy as np

import amorph_stats


def load_data(filename):
    """
    Read the two-column data file with the rules of the sampler. Returns
    (x, y).
    """
    return amorph_stats.load_data(filename)


def load_column_names(filename):
    """
    Read the header of posterior_sample.txt and return
    (names, indices), where indices maps a column name to its position.
    """
    with open(filename, "r") as f:
        line = f.readline()
    names = line.replace("#", "").replace(" ", "").strip().split(",")
    names = [n for n in names if n]
    indices = {}
    for i, n in enumerate(names):
        indices.setdefault(n, i)
    return names, indices


def load_posterior(filename, columns, max_rows=0):
    """
    Read the requested columns of posterior_sample.txt.
    """
    kwargs = {"skiprows": 1, "usecols": columns}
    if max_rows > 0:
        kwargs["max_rows"] = max_rows
    return np.loadtxt(filename, **kwargs)


def column_block(indices, first, n):
    """
    Column indices of the block of n values starting at column `first`.
    """
    return list(range(indices[first], indices[first] + n))


def amorphous_fraction(wide, narrow, x=None):
    """
    Posterior mean of (amorphous)/(amorphous + crystalline) in percent,
    calculated from the integrals of the two components over the data grid x
    with the same function as display.py. NaN if no sample has either
    component: the fraction is then undefined, not 0%.
    """
    frac = amorph_stats.amorphous_fraction(wide, narrow, x)
    frac = frac[np.isfinite(frac)]
    if frac.size == 0:
        return float("nan")
    return 100.0 * frac.mean()


def sample_indices(n_points, n_curves, stride=0, max_points=0):
    """
    The x indices that the faint sample curves are written on.

    With stride > 0 every n-th point is used. With stride == 0 the stride
    is chosen so that the total number of points stays below max_points,
    which keeps the memory use of PGFPlots within what pdfTeX can handle.
    """
    if stride <= 0:
        stride = 1
        if max_points > 0:
            stride = int(np.ceil(n_curves * n_points / float(max_points)))
            stride = max(1, stride)
    return np.arange(0, n_points, stride), stride


def pick_rows(n_total, n_wanted):
    """
    Indices of n_wanted rows spread evenly over the posterior sample.
    """
    if n_wanted <= 0 or n_total == 0:
        return np.array([], dtype=int)
    n_wanted = min(n_wanted, n_total)
    return np.unique(np.linspace(0, n_total - 1, n_wanted).astype(int))


def write_table(filename, header, columns):
    """Write a whitespace separated table with column names on the first line."""
    with open(filename, "w") as f:
        f.write(header + "\n")
        np.savetxt(f, columns, fmt="%.6g")


def latex_escape(text):
    """
    Escape the characters that would break a LaTeX macro definition.
    The title is LaTeX markup already, so only the comment character and
    a couple of specials are touched.
    """
    return text.replace("%", r"\%").replace("#", r"\#")


# Plain text in LaTeX: the characters that LaTeX would read as markup
_LATEX_SPECIALS = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}",
                   "$": r"\$", "&": r"\&", "#": r"\#", "^": r"\^{}",
                   "_": r"\_", "%": r"\%", "~": r"\~{}"}


def latex_text(text):
    """
    Plain text, such as the name of a file, as LaTeX that prints it as it
    is.
    """
    return "".join(_LATEX_SPECIALS.get(c, c) for c in text)


def data_file_from_config(config_file):
    """
    The data file that config_file names in data_file, as a path from the
    current folder: AMORPH reads it from the folder of config.yaml.
    Raises ValueError if config_file cannot tell.
    """
    import yaml
    try:
        with open(config_file, encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except OSError:
        raise ValueError("{0} not found, so the data file is unknown: run "
                         "in the folder of the run, or give --config or "
                         "--data".format(config_file))
    except yaml.YAMLError as e:
        raise ValueError("{0} is not valid YAML: {1}".format(config_file, e))
    data_file = config.get("data_file") if isinstance(config, dict) else None
    if not isinstance(data_file, str) or not data_file.strip():
        raise ValueError("{0} names no data_file: give --data".format(
            config_file))
    return os.path.join(os.path.dirname(config_file), data_file)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default=None,
                   help="the two-column data file that was analysed "
                        "(default: the data_file of --config)")
    p.add_argument("--config", default="config.yaml",
                   help="config.yaml of the run, which names the data file "
                        "unless --data does (default: config.yaml)")
    p.add_argument("--posterior", default="posterior_sample.txt",
                   help="posterior samples written by showresults.py")
    p.add_argument("--out", default="pgf",
                   help="output folder for the tables (default: pgf)")
    p.add_argument("--samples", type=int, default=50,
                   help="number of posterior sample curves to export "
                        "(0 disables them)")
    p.add_argument("--sample-stride", type=int, default=0,
                   help="write the sample curves using every n-th data point "
                        "(0 = choose the stride automatically)")
    p.add_argument("--max-points", type=int, default=24000,
                   help="maximum number of points in the sample curves, so "
                        "that the figure fits in the memory of pdfTeX "
                        "(0 = no limit, use lualatex)")
    p.add_argument("--title", default=None,
                   help="title of the figure, as LaTeX markup (default: the "
                        "name of the data file)")
    p.add_argument("--max-rows", type=int, default=0,
                   help="use at most this many posterior samples (0 = all)")
    args = p.parse_args()

    if args.data is None:
        try:
            args.data = data_file_from_config(args.config)
        except ValueError as e:
            raise SystemExit(str(e))
    if not os.path.isfile(args.data):
        raise SystemExit("Data file not found: " + args.data)
    if args.title is None:
        title = latex_text(os.path.basename(args.data))
    else:
        title = latex_escape(args.title)
    if not os.path.isfile(args.posterior):
        raise SystemExit("Posterior sample file not found: " + args.posterior)

    os.makedirs(args.out, exist_ok=True)

    try:
        x, y = load_data(args.data)
    except ValueError as e:
        raise SystemExit(str(e))
    n = len(x)

    names, indices = load_column_names(args.posterior)
    for needed in ("bg[0]", "narrow[0]", "wide[0]", "model_curve[0]"):
        if needed not in indices:
            raise SystemExit("Column {0} missing from {1}".format(needed,
                                                                 args.posterior))
    # The four blocks of curve values all have one entry per data point.
    blocks = (("bg[0]", "narrow[0]"), ("narrow[0]", "wide[0]"),
              ("wide[0]", "model_curve[0]"))
    for first, second in blocks:
        if indices[second] - indices[first] != n:
            raise SystemExit(
                "The block {0}--{1} holds {2} values, but the data file has "
                "{3} data points.".format(first, second,
                                         indices[second] - indices[first], n))

    bg_cols = column_block(indices, "bg[0]", n)
    nar_cols = column_block(indices, "narrow[0]", n)
    wide_cols = column_block(indices, "wide[0]", n)
    mod_cols = column_block(indices, "model_curve[0]", n)
    columns = bg_cols + nar_cols + wide_cols + mod_cols

    print("Reading {0} ...".format(args.posterior))
    raw = load_posterior(args.posterior, columns, args.max_rows)
    if raw.ndim == 1:
        raw = raw.reshape(1, -1)

    bg = raw[:, 0:n]
    narrow = raw[:, n:2 * n]
    wide = raw[:, 2 * n:3 * n]
    model = raw[:, 3 * n:4 * n]

    print("  {0} posterior samples, {1} data points".format(raw.shape[0], n))

    mean_model = model.mean(axis=0)
    mean_wide = wide.mean(axis=0)
    mean_narrow = narrow.mean(axis=0)
    mean_bg = bg.mean(axis=0)

    frac = amorphous_fraction(wide, narrow, x)
    if not np.isfinite(frac):
        raise SystemExit("The amorphous fraction is undefined: no posterior "
                         "sample in {0} has a wide or a narrow "
                         "component".format(args.posterior))

    # ------------------------------------------------------------------
    # Tables
    # ------------------------------------------------------------------
    write_table(os.path.join(args.out, "xrd_data.dat"),
                "x intensity", np.column_stack((x, y)))

    write_table(os.path.join(args.out, "xrd_mean.dat"),
                "x model amorph xtal background",
                np.column_stack((x, mean_model, mean_wide, mean_narrow,
                                 mean_bg)))

    rows = pick_rows(raw.shape[0], args.samples)
    if rows.size:
        # The faint sample curves are only decoration, so they are written
        # on a coarser grid to keep the memory use of PGFPlots manageable.
        n_curves = 3 * len(rows)
        sel, stride = sample_indices(n, n_curves, args.sample_stride,
                                     args.max_points)
        xs = x[sel]
        print("  {0} points per sample curve (stride {1})".format(
            len(sel), stride))
        for name, block in (("xrd_samples_model.dat", model),
                            ("xrd_samples_amorph.dat", wide),
                            ("xrd_samples_xtal.dat", narrow)):
            cols = np.column_stack([xs] + [block[r][sel] for r in rows])
            header = "x " + " ".join("sample{0}".format(i + 1)
                                     for i in range(len(rows)))
            write_table(os.path.join(args.out, name), header, cols)

        # The list of \addplot commands for the pale sample curves. This is
        # written out rather than looped over in LaTeX, because PGFPlots
        # does not like \addplot inside a \foreach.
        plots = os.path.join(args.out, "xrd_samples.tex")
        with open(plots, "w") as f:
            f.write("% Generated by export_pgf.py -- do not edit by hand.\n")
            for i in range(len(rows)):
                f.write("\\addplot[xrd sample, xrdgreen!28] "
                        "table[x index=0, y index={0}] "
                        "{{\\xrddatadir xrd_samples_model.dat}};\n".format(i + 1))
                f.write("\\addplot[xrd sample, blue!28] "
                        "table[x index=0, y index={0}] "
                        "{{\\xrddatadir xrd_samples_amorph.dat}};\n".format(i + 1))
                f.write("\\addplot[xrd sample, red!28] "
                        "table[x index=0, y index={0}] "
                        "{{\\xrddatadir xrd_samples_xtal.dat}};\n".format(i + 1))
    else:
        # No sample curves: remove the leftovers of an earlier run
        for name in ("xrd_samples_model.dat", "xrd_samples_amorph.dat",
                     "xrd_samples_xtal.dat", "xrd_samples.tex"):
            path = os.path.join(args.out, name)
            if os.path.isfile(path):
                os.remove(path)

    # ------------------------------------------------------------------
    # Axis limits
    # ------------------------------------------------------------------
    ymax = max(y.max(), mean_model.max())
    ymax = 50.0 * np.ceil(1.2 * ymax / 50.0)
    xmin = np.floor(x.min())
    xmax = np.ceil(x.max())

    # ------------------------------------------------------------------
    # Macros for the LaTeX side
    # ------------------------------------------------------------------
    meta = os.path.join(args.out, "xrd_meta.tex")
    with open(meta, "w") as f:
        f.write("% Generated by export_pgf.py -- do not edit by hand.\n")
        f.write("\\def\\xrdtitle{{{0}}}\n".format(title))
        f.write("\\def\\xrdamorph{{{0:.1f}\\%}}\n".format(frac))
        f.write("\\def\\xrdxmin{{{0}}}\n".format(xmin))
        f.write("\\def\\xrdxmax{{{0}}}\n".format(xmax))
        f.write("\\def\\xrdymin{{0}}\n")
        f.write("\\def\\xrdymax{{{0}}}\n".format(ymax))
        f.write("\\def\\xrdnsamples{{{0}}}\n".format(len(rows)))

    print("Amorphous fraction = {0:.1f}%".format(frac))
    print("Tables written to {0}/".format(args.out))


if __name__ == "__main__":
    main()
