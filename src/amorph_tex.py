"""
Figures of one run or several seeds for LaTeX: the tables that PGFPlots
reads, the folder of a figure with its .tex files and build scripts, and
the build of PDF and SVG files with the LaTeX found on the computer.

    pooled = amorph_seeds.pool(runs)
    amorph_tex.write_tables(pooled, "pgf", title)
    amorph_tex.write_figure(pooled, "folder", "fit", title)
    amorph_tex.build("folder", "fit", "pdf", amorph_tex.find_latex())

Two figures, both in doc/figures:

fit     xrd_fit.tex: the scan with the posterior means of the model, the
        amorphous part, the crystalline peaks and the background, and
        faint posterior samples; the tables of export_pgf.py
seeds   xrd_seeds.tex: (a) the scan with the background, the amorphous
        halo, the crystalline peaks, the model and its 90% band, and the
        halo of each seed; (b) the distribution of the fraction of each
        seed and pooled

write_tables() writes the tables of both into one folder (pgf/). PDF comes
from pdflatex, SVG from latex and dvisvgm; nothing here needs Qt.
"""

import glob
import os
import shutil
import subprocess
import sys

import numpy as np

import export_pgf
import figure_labels

# The figures: the .tex file that compiles each, and the files it needs
FIGURES = {"fit": ("xrd_fit.tex", "xrd_fit_body.tex"),
           "seeds": ("xrd_seeds.tex", "xrd_seeds_body.tex")}

# The folder of the tables, as the .tex files expect it
DATA_DIR = "pgf"

# The LaTeX programs a build needs
TOOLS = ("pdflatex", "latex", "dvisvgm")

# How long a build may take, in seconds
TIMEOUT = 300


def template_dir():
    """
    The folder of the .tex files: figures/ next to this module in the
    packaged GUI, doc/figures/ of the repository otherwise.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for folder in (os.path.join(here, "figures"),
                   os.path.join(os.path.dirname(here), "doc", "figures")):
        if all(os.path.isfile(os.path.join(folder, name))
               for files in FIGURES.values() for name in files):
            return folder
    raise FileNotFoundError("the .tex files of the figures ({0}) are not in "
                            "figures/ or doc/figures/".format(", ".join(
                                n for f in FIGURES.values() for n in f)))


def _number(value):
    return "{0:.3f}".format(value)


def write_tables(pooled, out, title, language="en"):
    """
    Write the tables of both figures into the folder out (made if needed)
    for pooled (amorph_seeds.pool): those of export_pgf.py
    (export_pgf.write_tables) and those of xrd_seeds_body.tex, with the
    words of the figures in language ("en" or "ru", figure_labels). title
    is plain text, such as the name of the data file. Returns out.
    """
    words = figure_labels.LABELS[language]
    os.makedirs(out, exist_ok=True)
    x, y, c = pooled["x"], pooled["y"], pooled["curves"]
    ex = pooled["examples"]
    export_pgf.write_tables(
        out, x, y,
        {"model": c["model_curve"], "amorph": c["wide"], "xtal": c["narrow"],
         "background": c["bg"]},
        {"model": ex["model_curve"], "amorph": ex["wide"],
         "xtal": ex["narrow"]},
        export_pgf.latex_text(title),
        [100.0 * pooled["quantiles"][i] for i in (2, 1, 3)],
        language=language)

    halo = c["bg"] + c["wide"]
    lo, hi = pooled["band"]
    export_pgf.write_table(os.path.join(out, "seeds_curves.dat"),
                           "x bg halo model crystal lo hi",
                           np.column_stack((x, c["bg"], halo,
                                            c["model_curve"], c["narrow"],
                                            lo, hi)))
    seeds = pooled["seeds"]
    names = ["seed{0}".format(i + 1) for i in range(len(seeds))]
    export_pgf.write_table(os.path.join(out, "seeds_halo.dat"),
                           " ".join(["x"] + names),
                           np.column_stack([x] + pooled["halos"]))
    h = pooled["histogram"]
    edges = h["edges"]
    centres = 0.5 * (edges[1:] + edges[:-1])
    export_pgf.write_table(os.path.join(out, "seeds_fraction.dat"),
                           " ".join(["f", "pooled"] + names),
                           np.column_stack([centres, h["pooled"]]
                                           + h["densities"]))

    def label(i):
        seed = seeds[i]
        return words["seed"].format(seed) if seed is not None \
            else words["run"].format(i + 1)

    # One colour per seed, in turn (seed1 to seed6 of xrd_seeds_body.tex)
    with open(os.path.join(out, "seeds_halos.tex"), "w",
              encoding="utf-8") as f:
        f.write("% Written by the AMORPH GUI -- do not edit by hand.\n")
        if len(seeds) > 1:
            for i, name in enumerate(names):
                f.write("\\addplot[seeds halo, seed{0}, forget plot] "
                        "table[x=x, y={1}] {{\\xrddatadir seeds_halo.dat}};\n"
                        .format(i % 6 + 1, name))
    with open(os.path.join(out, "seeds_densities.tex"), "w",
              encoding="utf-8") as f:
        f.write("% Written by the AMORPH GUI -- do not edit by hand.\n")
        for i, name in enumerate(names):
            f.write("\\addplot[seeds density, seed{0}] table[x=f, y={1}] "
                    "{{\\xrddatadir seeds_fraction.dat}};\n"
                    "\\addlegendentry{{{2}}}\n".format(
                        i % 6 + 1, name, export_pgf.latex_text(label(i))))

    q = pooled["quantiles"]
    count = len(seeds)
    known = [str(s) for s in seeds if s is not None]
    if known and count > 1:
        which = words["title_seeds"].format(", ".join(known))
    else:
        which = words["title_seed"].format(known[0]) if known else ""
    if pooled["spread"] is None:
        spread = words["one_run"]
    else:
        spread = words["spread"].format(_number(pooled["spread"]))
    ymax = 50.0 * np.ceil(1.2 * max(y.max(), np.max(hi)) / 50.0)
    edges_lo, edges_hi = edges[0], edges[-1]
    with open(os.path.join(out, "seeds_meta.tex"), "w",
              encoding="utf-8") as f:
        f.write("% Written by the AMORPH GUI -- do not edit by hand.\n")
        f.write("\\def\\seedstitle{{{0}}}\n".format(
            export_pgf.latex_text(title + which)))
        f.write("\\def\\seedscount{{{0}}}\n".format(export_pgf.latex_text(
            words["count"].format(count) if count > 1 else words["one"])))
        # The words of the figure, in its language
        for macro, key in (("seedsylabel", "counts"),
                           ("seedslegband", "band"),
                           ("seedslegbg", "background"),
                           ("seedsleghalo", "halo"),
                           ("seedslegmodel", "model"),
                           ("seedslegxtal", "crystal"),
                           ("seedsfractionlabel", "fraction"),
                           ("seedsdensitylabel", "density"),
                           ("seedspooled", "pooled")):
            f.write("\\def\\{0}{{{1}}}\n".format(
                macro, export_pgf.latex_text(words[key])))
        f.write("\\def\\seedsmedian{{{0}}}\n".format(_number(q[2])))
        f.write("\\def\\seedsqlo{{{0}}}\\def\\seedsqhi{{{1}}}\n".format(
            _number(q[1]), _number(q[3])))
        f.write("\\def\\seedsqqlo{{{0}}}\\def\\seedsqqhi{{{1}}}\n".format(
            _number(q[0]), _number(q[4])))
        f.write("\\def\\seedsspread{{{0}}}\n".format(
            export_pgf.latex_text(spread)))
        f.write("\\def\\seedsxmin{{{0}}}\\def\\seedsxmax{{{1}}}\n".format(
            np.floor(x.min()), np.ceil(x.max())))
        f.write("\\def\\seedsymax{{{0}}}\n".format(ymax))
        f.write("\\def\\seedsfmin{{{0:.2f}}}\\def\\seedsfmax{{{1:.2f}}}\n"
                .format(edges_lo, edges_hi))
    return out


def _script_lines(stem, windows):
    commands = ["pdflatex -interaction=nonstopmode -halt-on-error "
                "{0}.tex".format(stem),
                "latex -interaction=nonstopmode -halt-on-error "
                "{0}.tex".format(stem),
                "dvisvgm --no-fonts --exact-bbox -o {0}.svg {0}.dvi".format(
                    stem)]
    if windows:
        return (["@echo off",
                 "rem Build {0}.pdf (pdflatex) and {0}.svg (latex and "
                 "dvisvgm)".format(stem),
                 'cd /d "%~dp0"']
                + [c + " || exit /b 1" for c in commands])
    return (["#!/bin/sh",
             "# Build {0}.pdf (pdflatex) and {0}.svg (latex and dvisvgm)"
             .format(stem),
             "set -e", 'cd "$(dirname "$0")"'] + commands)


def write_figure(pooled, folder, figure, title, language="en"):
    """
    The folder of a figure ("fit" or "seeds"), ready for LaTeX: the tables
    in pgf/ (write_tables, with the words in language), the .tex files of
    the figure, and build.sh and build.bat that make its PDF and SVG.
    Returns the path of its .tex file.
    """
    os.makedirs(folder, exist_ok=True)
    write_tables(pooled, os.path.join(folder, DATA_DIR), title, language)
    source = template_dir()
    for name in FIGURES[figure]:
        shutil.copyfile(os.path.join(source, name),
                        os.path.join(folder, name))
    stem = os.path.splitext(FIGURES[figure][0])[0]
    with open(os.path.join(folder, "build.sh"), "w", newline="\n") as f:
        f.write("\n".join(_script_lines(stem, False)) + "\n")
    os.chmod(os.path.join(folder, "build.sh"), 0o755)
    with open(os.path.join(folder, "build.bat"), "w", newline="\r\n") as f:
        f.write("\n".join(_script_lines(stem, True)) + "\n")
    return os.path.join(folder, FIGURES[figure][0])


def _latex_folders():
    """
    Where LaTeX is often installed, newest first, for when it is not on
    PATH (a program started from the desktop may not see it).
    """
    folders = []
    if sys.platform == "win32":
        folders += sorted(glob.glob(r"C:\texlive\*\bin\windows")
                          + glob.glob(r"C:\texlive\*\bin\win64")
                          + glob.glob(r"C:\texlive\*\bin\win32"),
                          reverse=True)
        for base in (os.environ.get("LOCALAPPDATA", ""),
                     os.environ.get("ProgramFiles", r"C:\Program Files")):
            if base:
                folders.append(os.path.join(base, "Programs", "MiKTeX",
                                            "miktex", "bin", "x64"))
                folders.append(os.path.join(base, "MiKTeX", "miktex", "bin",
                                            "x64"))
    elif sys.platform == "darwin":
        folders.append("/Library/TeX/texbin")
    else:
        folders += sorted(glob.glob("/usr/local/texlive/*/bin/*"),
                          reverse=True)
    return folders


def find_latex():
    """
    The paths of the LaTeX programs (TOOLS) by name: from PATH, or else
    from the first usual folder that holds all of them. Programs that are
    not found are missing from the dict.
    """
    found = {name: shutil.which(name) for name in TOOLS}
    found = {k: v for k, v in found.items() if v}
    if len(found) == len(TOOLS):
        return found
    for folder in _latex_folders():
        paths = {name: shutil.which(name, path=folder) for name in TOOLS}
        if all(paths.values()):
            return paths
    return found


class BuildError(RuntimeError):
    pass


def _run(command, folder):
    try:
        result = subprocess.run(command, cwd=folder, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, timeout=TIMEOUT,
                                creationflags=getattr(
                                    subprocess, "CREATE_NO_WINDOW", 0))
    except subprocess.TimeoutExpired:
        raise BuildError("{0} did not finish in {1} s".format(
            os.path.basename(command[0]), TIMEOUT))
    if result.returncode != 0:
        text = result.stdout.decode("utf-8", "replace").splitlines()
        errors = [line for line in text if line.startswith("!")]
        tail = errors[:3] or text[-12:]
        raise BuildError("{0} failed:\n{1}".format(
            os.path.basename(command[0]), "\n".join(tail)))


def build(folder, figure, kind, tools):
    """
    Build the PDF ("pdf": pdflatex) or the SVG ("svg": latex and dvisvgm)
    of the figure in folder (write_figure), with the programs tools
    (find_latex). Returns the path of the file. Raises BuildError with the
    first errors of LaTeX if it fails, or names the programs that are
    missing.
    """
    tex = FIGURES[figure][0]
    stem = os.path.splitext(tex)[0]
    needed = ["pdflatex"] if kind == "pdf" else ["latex", "dvisvgm"]
    missing = [name for name in needed if name not in tools]
    if missing:
        raise BuildError("not found: " + ", ".join(missing))
    options = ["-interaction=nonstopmode", "-halt-on-error"]
    if kind == "pdf":
        _run([tools["pdflatex"]] + options + [tex], folder)
        return os.path.join(folder, stem + ".pdf")
    _run([tools["latex"]] + options + [tex], folder)
    _run([tools["dvisvgm"], "--no-fonts", "--exact-bbox", "-o",
          stem + ".svg", stem + ".dvi"], folder)
    return os.path.join(folder, stem + ".svg")
