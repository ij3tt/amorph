"""
The report of one run or of several seeds together, as a LaTeX document to
build with pdflatex: a folder with report.tex, the .tex bodies of both
figures of amorph_tex and their tables in pgf/, and build.bat / build.sh.
The report has the result (the pooled fraction, as the joint report of
«Сравнение» has it, and the line for a paper), the table of the runs with
their checks, the data and the settings, the diagnostic cards of each run,
both figures, and how to read the numbers, in Russian or in English
(LANGUAGES). Nothing here needs Qt.

    rows = [digest.comparison_row(results, archive) for ...]
    digest.mark_log_z(rows)
    report.write_report(rows, "folder", language="en")
"""

import datetime
import os
import shutil

import amorph_results
import amorph_tex
import export_pgf

from amorph_gui import digest, helptext, strings, strings_en

REPORT = "report.tex"

# The languages of the report: the module of its texts, the encodings of
# fontenc and the languages of babel, the main one last
LANGUAGES = {"ru": (strings, "T2A", "english,russian"),
             "en": (strings_en, "T2A,T1", "russian,english")}

# Characters of the texts of the interface that LaTeX with T2A or T1 and
# utf8 does not print by itself
UNICODE = {"−": "$-$", "Δ": "$\\Delta$", "≤": "$\\le$", "≥": "$\\ge$",
           "ν": "$\\nu$", "θ": "$\\theta$", "σ": "$\\sigma$",
           "·": "$\\cdot$", "±": "$\\pm$", "≈": "$\\approx$",
           "×": "$\\times$", "→": "$\\to$", "°": "\\textdegree{}",
           "…": "\\ldots{}"}

# The topics of helptext that «Как читать» explains in Russian
NOTES = ["fraction", "intervals", "seeds", "ess", "log_z"]

PREAMBLE = r"""\documentclass[a4paper,11pt]{article}
\usepackage[ENCODINGS]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[LANGUAGES]{babel}
% One space after a stop or a colon, in English as in Russian
\frenchspacing
\usepackage[margin=2cm]{geometry}
\usepackage{booktabs}
\usepackage{array}
\usepackage{graphicx}
\usepackage{pgfplots}
\usepgfplotslibrary{fillbetween,groupplots}
\pgfplotsset{compat=1.18}
% The tables of the figures
\def\xrddatadir{pgf/}
% The table of the runs, measured before it is set
\newsavebox{\runsbox}
"""


def latex(text):
    """
    Plain text of the interface as LaTeX that prints it as it is.
    """
    return "".join(UNICODE.get(c) or export_pgf.latex_text(c)
                   for c in str(text))


def settings(results, lang=strings):
    """
    The data and the settings of a run: (label, plain text) in the order
    of lang.REPORT_SETTING_ROWS.
    """
    def value(v):
        return lang.UNKNOWN if v is None else v

    def pair(v):
        if isinstance(v, (list, tuple)) and len(v) == 2:
            return "{0:g} – {1:g}".format(float(v[0]), float(v[1]))
        return lang.UNKNOWN

    info = results.info
    a = digest.assumptions(results)
    c = digest.run_config(results)
    values = {
        "data_file": value(info.get("data_file")),
        "range": pair([info["x_min"], info["x_max"]])
        if "x_min" in info and "x_max" in info else lang.UNKNOWN,
        "points": value(info.get("num_points")),
        "control_points": pair(a.get("control_points")),
        "edges": pair([a["left_edge"], a["right_edge"]])
        if "left_edge" in a and "right_edge" in a else lang.UNKNOWN,
        "nu": pair(a.get("narrow_peak_nu", [0.1, 100.0])),
        "caps": "{0} / {1}".format(value(a.get("max_num_narrow_peaks")),
                                   value(a.get("max_num_wide_peaks"))),
        "options": value(c.get("dnest4_options_file"))}
    return [(label, str(values[key]))
            for key, label in lang.REPORT_SETTING_ROWS]


def _heading(text):
    # A heading of the table, on two lines where it has a line break; {}
    # keeps a "[" after the break from being read as its spacing
    return r"\shortstack{" + r"\\{}".join(latex(part)
                                          for part in text.split("\n")) + "}"


def _runs_table(chosen, lang):
    # In a box first: shrunk to the width of the text if it is wider, as
    # with long names of the options files
    lines = [r"\sbox{\runsbox}{\footnotesize\setlength{\tabcolsep}{3.5pt}",
             r"\begin{tabular}{rlrrrlrr>{\raggedright\arraybackslash}"
             r"p{3.0cm}}",
             r"\toprule",
             " & ".join(_heading(c) for c in lang.REPORT_COLUMNS) + r" \\",
             r"\midrule"]
    for row in chosen:
        saves, planned = row.get("saves"), row.get("planned")
        if saves is None:
            count = lang.UNKNOWN
        elif planned:
            count = lang.SAVES_CELL.format(saves, planned)
        else:
            count = str(saves)
        cells = [digest.seed_text(row), row.get("options") or lang.UNKNOWN,
                 count, digest.ess_text(row), digest.dlog_z_text(row),
                 digest.fraction_text(row),
                 digest.weight_text(row["below_0.2"]),
                 digest.weight_text(row["at_cap"]),
                 digest.check_text(row, lang)]
        lines.append(" & ".join(latex(c) for c in cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}}",
              r"\ifdim\wd\runsbox>\textwidth",
              r"\resizebox{\textwidth}{!}{\usebox{\runsbox}}",
              r"\else\usebox{\runsbox}\fi"]
    return lines


def _figure(body, caption):
    return [r"\begin{figure}[htbp]", r"\centering",
            r"\resizebox{\textwidth}{!}{\input{" + body + "}}",
            r"\caption{" + latex(caption) + "}", r"\end{figure}"]


def _reading(lang):
    # What «Как читать» says: in Russian, the tooltips of helptext
    if lang is strings:
        return [helptext.TOPICS[topic][:2] for topic in NOTES]
    return lang.REPORT_NOTE_ITEMS


def report_text(rows, pooled, notes, paper, title, date=None,
                language="ru"):
    """
    The text of report.tex for the chosen rows (digest.comparison_row)
    pooled as pooled, with the notes and the line for a paper of
    digest.joint_report, in language ("ru" or "en").
    """
    lang, encodings, languages = LANGUAGES[language]
    chosen = [r for r in rows if r["chosen"] and r.get("results") is not None
              and r.get("q50") is not None]
    q = pooled["quantiles"]
    n = len(chosen)
    date = date or datetime.date.today().isoformat()
    out = ["% " + line for line in (lang.REPORT_TITLE.format(title),
                                    lang.REPORT_HOW_TO_BUILD)]
    out.append(PREAMBLE.replace("ENCODINGS", encodings)
               .replace("LANGUAGES", languages))
    out += [r"\title{" + latex(lang.REPORT_TITLE.format(title)) + "}",
            r"\author{}",
            r"\date{" + latex(lang.REPORT_DATE.format(
                date=date, version=amorph_results.AMORPH_VERSION)) + "}",
            r"\begin{document}", r"\maketitle", ""]

    # The result
    out += [r"\section*{" + latex(lang.REPORT_RESULT) + "}",
            latex(lang.REPORT_FRACTION.format(q05=q[0], q25=q[1], q50=q[2],
                                              q75=q[3], q95=q[4])), ""]
    if n > 1:
        out.append(latex(lang.REPORT_POOLED.format(
            n=n, seeds=digest.seeds_word(n, lang), spread=pooled["spread"],
            ess=pooled["ess"])))
    else:
        out.append(latex(lang.REPORT_ONE_RUN.format(ess=pooled["ess"])))
    # Ragged: monospaced text does not stretch to fill a line
    out += ["", latex(lang.REPORT_PAPER),
            r"\begin{quote}\raggedright\texttt{" + latex(paper)
            + r"}\end{quote}", ""]
    if notes:
        out.append(r"\begin{itemize}")
        out += [r"\item " + latex(text) for _, text in notes]
        out.append(r"\end{itemize}")

    # The runs
    out += ["", r"\section*{" + latex(lang.REPORT_RUNS) + "}",
            r"\begin{center}"] + _runs_table(chosen, lang) \
        + [r"\end{center}", ""]

    # The data and the settings
    out.append(r"\section*{" + latex(lang.REPORT_SETTINGS) + "}")
    if len({r["settings"] for r in chosen}) > 1:
        out += [latex(lang.REPORT_SETTINGS_DIFFER), ""]
    out += [r"\begin{center}", r"\begin{tabular}{ll}", r"\toprule"]
    out += [latex(label) + " & " + latex(value) + r" \\"
            for label, value in settings(chosen[0]["results"], lang)]
    out += [r"\bottomrule", r"\end{tabular}", r"\end{center}", ""]

    # The diagnostic cards of each run
    out.append(r"\section*{" + latex(lang.REPORT_DIAGNOSIS) + "}")
    for row in chosen:
        if n > 1:
            out.append(r"\subsection*{" + latex(
                lang.REPORT_DIAGNOSIS_RUN.format(digest.seed_text(row)))
                + "}")
        out.append(r"\begin{itemize}")
        for level, card_title, text in digest.diagnostic_cards(
                row["results"], lang=lang):
            mark = "" if level == digest.OK else r"\textbf{!} "
            out.append(r"\item " + mark + r"\textbf{" + latex(card_title)
                       + "}. " + latex(text))
        out.append(r"\end{itemize}")

    # The figures
    out += ["", r"\section*{" + latex(lang.REPORT_FIGURES) + "}"]
    out += _figure(amorph_tex.FIGURES["fit"][1], lang.REPORT_FIGURE_FIT)
    out += _figure(amorph_tex.FIGURES["seeds"][1], lang.REPORT_FIGURE_SEEDS)

    # How to read the numbers
    out += [r"\clearpage", r"\section*{" + latex(lang.REPORT_NOTES) + "}",
            r"\begin{itemize}"]
    for name, text in _reading(lang):
        out.append(r"\item \textbf{" + latex(name) + "}. " + latex(text))
    out += [r"\end{itemize}", "", r"\end{document}", ""]
    return "\n".join(out)


def _scripts(folder):
    command = "pdflatex -interaction=nonstopmode -halt-on-error " + REPORT
    with open(os.path.join(folder, "build.bat"), "w", newline="\r\n") as f:
        f.write("@echo off\nrem Build report.pdf\ncd /d \"%~dp0\"\n"
                + command + "\n")
    with open(os.path.join(folder, "build.sh"), "w", newline="\n") as f:
        f.write("#!/bin/sh\n# Build report.pdf\nset -e\ncd \"$(dirname "
                "\"$0\")\"\n" + command + "\n")
    os.chmod(os.path.join(folder, "build.sh"), 0o755)


def write_report(rows, folder, title=None, date=None, language="ru"):
    """
    Write the report of the chosen rows into folder (made if needed), in
    language ("ru" or "en"): report.tex, the bodies of the figures, their
    tables in pgf/ and the build scripts. title is plain text, the data
    file by default. Returns the path of report.tex; ValueError if the
    rows cannot be pooled.
    """
    pooled, notes, paper = digest.joint_report(rows, LANGUAGES[language][0])
    if pooled is None:
        raise ValueError("; ".join(text for _, text in notes))
    chosen = [r for r in rows if r["chosen"] and r.get("results") is not None
              and r.get("q50") is not None]
    title = title or str(chosen[0]["data_file"])
    os.makedirs(folder, exist_ok=True)
    # The figures in the language of the report
    amorph_tex.write_tables(pooled, os.path.join(folder, amorph_tex.DATA_DIR),
                            title, language)
    source = amorph_tex.template_dir()
    for figure in ("fit", "seeds"):
        body = amorph_tex.FIGURES[figure][1]
        shutil.copyfile(os.path.join(source, body), os.path.join(folder, body))
    path = os.path.join(folder, REPORT)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(report_text(rows, pooled, notes, paper, title, date,
                            language))
    _scripts(folder)
    return path


def results_rows(results, archive):
    """
    The rows of the report of one run: in it whatever its checks say, as
    the user asked for its report.
    """
    rows = [digest.comparison_row(results, archive)]
    digest.mark_log_z(rows)
    rows[0]["chosen"] = True
    return rows
