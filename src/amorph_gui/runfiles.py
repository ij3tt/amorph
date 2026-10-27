"""
The files of a run: its folder runs/<date>_<data>_seed<k>/ with
config.yaml, the DNest4 options file and the analysed part of the data;
what the sampler has written so far; the run folders found in a folder,
and a run opened from its folder; and the post-processing that
showresults.py does, followed by the run archive. Nothing here needs Qt,
and the slow parts run in a worker thread of the GUI.
"""

import glob
import os
import re
import threading
import unicodedata

import numpy as np

import amorph_archive
import amorph_results
import amorph_stats
import dnest_functions

from amorph_gui import config

# dnest_functions.postprocess reads and writes the files of the current
# folder, which is shared by all the threads of the program: one at a time
CHDIR_LOCK = threading.Lock()

# The file the GUI keeps the output of the sampler in; from_run puts it in
# the archive as log/run.log
LOG_FILE = "run.log"

# Russian letters in Latin ones, for the names of files and folders
_LATIN = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "i", "k", "l", "m",
     "n", "o", "p", "r", "s", "t", "u", "f", "kh", "ts", "ch", "sh", "shch",
     "", "y", "", "e", "yu", "ya"]))


def safe_name(name):
    """
    A file name with Latin letters, digits, '.', '_' and '-' only. On
    Windows the sampler opens files by their name in the local code page,
    so the data file of a run gets a name like this.
    """
    out = []
    for c in name:
        lower = c.lower()
        if lower in _LATIN:
            latin = _LATIN[lower]
            out.append(latin.capitalize() if c != lower else latin)
        else:
            out.append(c)
    text = unicodedata.normalize("NFKD", "".join(out))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_")
    stem, ext = os.path.splitext(text)
    return (stem.strip("_.") or "data") + ext


def run_folder_name(when, data_file, seed):
    """
    The name of the folder of a run: 2026-10-25_1530_easy_data_seed1.
    when is a datetime.
    """
    stem = os.path.splitext(safe_name(os.path.basename(data_file)))[0]
    return "{0}_{1}_seed{2}".format(when.strftime("%Y-%m-%d_%H%M"), stem,
                                    seed)


def write_data(filename, x, y, source, x_range):
    """
    Write the points (x, y) for the sampler, with a comment that says where
    they come from. repr() keeps every digit.
    """
    with open(filename, "w", encoding="utf-8") as f:
        if x_range is None:
            f.write("# The data of {0}, written by the AMORPH GUI\n".format(
                os.path.basename(source)))
        else:
            f.write("# The points of {0} with x from {1!r} to {2!r}, written "
                    "by the AMORPH GUI\n".format(os.path.basename(source),
                                                 float(x_range[0]),
                                                 float(x_range[1])))
        for a, b in zip(x, y):
            f.write("{0!r} {1!r}\n".format(float(a), float(b)))


def prepare_run(root, settings, data_path, x, y, seed, options_template,
                when):
    """
    Make the folder of one run in root and write into it config.yaml, the
    options file with the maximum number of saves of the settings, and the
    points of the data (x, y) in the analysed range. Returns the folder.
    """
    os.makedirs(root, exist_ok=True)
    base = os.path.join(root, run_folder_name(when, data_path, seed))
    folder = base
    k = 2
    while os.path.exists(folder):
        folder = "{0}_{1}".format(base, k)
        k += 1
    os.makedirs(folder)

    keep = config.selected(x, settings.x_range)
    data_file = safe_name(os.path.basename(data_path))
    write_data(os.path.join(folder, data_file), x[keep], y[keep], data_path,
               settings.x_range)
    with open(os.path.join(folder, settings.dnest4_options_file), "w") as f:
        f.write(config.options_with_max_saves(options_template,
                                              settings.max_saves))
    run_settings = config.Settings(**vars(settings))
    run_settings.data_file = data_file
    run_settings.seed = seed
    config.write_config(run_settings, os.path.join(folder, "config.yaml"))
    return folder


# --------------------------------------------------- the sampler at work

def count_data_lines(filename):
    """
    The number of complete lines of a DNest4 output file that are not
    comments (0 if there is no file yet).
    """
    try:
        with open(filename, "rb") as f:
            return sum(1 for line in f if line.endswith(b"\n")
                       and not line.startswith(b"#"))
    except OSError:
        return 0


def last_line(filename, block_size=1 << 16):
    """
    The last complete line of a file, read from its end, without the
    newline; None if there is none.
    """
    with open(filename, "rb") as f:
        f.seek(0, os.SEEK_END)
        position = f.tell()
        data = b""
        while position > 0:
            step = min(block_size, position)
            position -= step
            f.seek(position)
            data = f.read(step) + data
            end = data.rfind(b"\n")
            if end == -1:
                continue
            start = data.rfind(b"\n", 0, end)
            if start != -1:
                return data[start + 1:end]
            if position == 0:
                return data[:end]
    return None


class SampleReader(object):
    """
    Reads the curves of the last saved sample of sample.txt, with the
    columns of its header.
    """

    def __init__(self, filename):
        self.filename = filename
        self.num_values = None
        self.columns = None

    def read(self):
        """
        The curves bg, wide, narrow and model_curve of the last sample, by
        name; None while there is no complete sample.
        """
        if not os.path.isfile(self.filename):
            return None
        if self.columns is None:
            names = amorph_results.column_names(self.filename)
            if "model_curve[0]" not in names:
                return None
            self.num_values = len(names)
            self.columns = {}
            for name in amorph_results.CURVES:
                first = names.index(name + "[0]")
                n = sum(1 for c in names if c.startswith(name + "["))
                self.columns[name] = slice(first, first + n)
        line = last_line(self.filename)
        if line is None or line.startswith(b"#"):
            return None
        values = line.split()
        if len(values) != self.num_values:
            return None
        values = np.array(values, dtype=float)
        return {name: values[columns]
                for name, columns in self.columns.items()}


def levels_text(folder):
    """
    The contents of levels.txt if every line of it is complete, else None.
    The sampler rewrites the file at every save, so one that is killed at
    the wrong moment leaves it cut off or empty.
    """
    try:
        with open(os.path.join(folder, "levels.txt"), "rb") as f:
            data = f.read()
    except OSError:
        return None
    levels = [line for line in data.splitlines(keepends=True)
              if not line.startswith(b"#")]
    if not levels or any(not line.endswith(b"\n") or len(line.split()) != 7
                         for line in levels):
        return None
    return data


def _num_levels(text):
    return sum(1 for line in text.splitlines() if not line.startswith(b"#"))


def restore_levels(folder, saved):
    """
    After the sampler was killed: put back saved, a copy of levels.txt
    taken while it ran (levels_text), if the file now holds fewer complete
    levels. The sampler only ever adds levels. Returns whether it did.
    """
    if saved is None:
        return False
    current = levels_text(folder)
    if current is not None and _num_levels(current) >= _num_levels(saved):
        return False
    with open(os.path.join(folder, "levels.txt"), "wb") as f:
        f.write(saved)
    return True


def progress(folder, reader):
    """
    What the sampler of the run in folder has done so far: the number of
    saves (data lines of sample_info.txt), of levels (data lines of
    levels.txt), a copy of levels.txt if it is complete (levels_text) and
    the curves of the last saved sample (SampleReader).
    """
    return {"saves": count_data_lines(os.path.join(folder,
                                                   "sample_info.txt")),
            "levels": count_data_lines(os.path.join(folder, "levels.txt")),
            "levels_text": levels_text(folder),
            "sample": reader.read()}


# ------------------------------------------------------ runs done elsewhere

# An archive written up to this many seconds before the last save of its
# run counts as up to date: copied or synced folders keep coarse file times
ARCHIVE_SLACK = 2.0


def is_run_folder(folder):
    """
    Whether folder holds a run: config.yaml and the output of the sampler.
    """
    return all(os.path.isfile(os.path.join(folder, name))
               for name in ("config.yaml", "sample_info.txt", "levels.txt"))


def run_folders(path, depth=2):
    """
    The run folders of path: path itself if it is one, else those among
    its subfolders, down to depth levels, sorted by their paths.
    """
    path = os.path.abspath(path)
    if is_run_folder(path):
        return [path]
    found = []
    for root, dirs, _ in os.walk(path):
        level = 0 if root == path \
            else os.path.relpath(root, path).count(os.sep) + 1
        if level and is_run_folder(root):
            found.append(root)
            dirs[:] = []
        elif level + 1 > depth:
            dirs[:] = []
        dirs.sort()
    return sorted(found)


def loose_archives(path):
    """
    The run archives (.amorph) in path and its subfolders that are not in
    a run folder: the run.amorph files of the CI workflows, say.
    """
    found = []
    for root, dirs, files in os.walk(os.path.abspath(path)):
        if is_run_folder(root):
            dirs[:] = []
            continue
        found += [os.path.join(root, f) for f in files
                  if f.lower().endswith(".amorph")]
    return sorted(found)


def current_archive(folder):
    """
    The newest run archive of the run in folder, if it is not older than
    its last save; else None.
    """
    archives = glob.glob(os.path.join(folder, "*.amorph"))
    if not archives:
        return None
    newest = max(archives, key=os.path.getmtime)
    last_save = os.path.getmtime(os.path.join(folder, "sample_info.txt"))
    return newest if os.path.getmtime(newest) + ARCHIVE_SLACK >= last_save \
        else None


def open_run(folder):
    """
    A run of the sampler done earlier or on another computer, from its
    folder: its settings (config.yaml and the options file), the analysed
    data, the counts of its saves and levels, its output (run.log) and its
    results. These come from its archive if it is up to date; otherwise
    the run is post-processed here as the GUI does at the end of a run,
    which writes posterior_sample.txt and the archive into its folder.
    """
    folder = os.path.abspath(folder)
    settings, options = config.read_config(os.path.join(folder,
                                                        "config.yaml"))
    x, y = amorph_stats.load_data(os.path.join(folder, settings.data_file))
    log = ""
    path = os.path.join(folder, LOG_FILE)
    if os.path.isfile(path):
        with open(path, encoding="utf-8", errors="replace") as f:
            log = f.read()
    archive = current_archive(folder)
    if archive is not None:
        results = amorph_archive.read(archive)
    else:
        results, archive = postprocess(folder)
    return {"folder": folder, "seed": settings.seed,
            "planned": settings.max_saves if options is not None else 0,
            "x": x, "y": y, "log": log, "results": results,
            "archive": archive,
            "saves": count_data_lines(os.path.join(folder,
                                                   "sample_info.txt")),
            "levels": count_data_lines(os.path.join(folder, "levels.txt"))}


# --------------------------------------------------------- post-processing

def postprocess(folder):
    """
    What showresults.py does, in the folder of a run: seed the resampling
    from config.yaml, write posterior_sample.txt with the DNest4
    post-processing, then compute the results and write the run archive.
    (A run that was stopped needs amorph_stats.trim_outputs first.) Returns
    the results and the archive.
    """
    folder = os.path.abspath(folder)
    with CHDIR_LOCK:
        cwd = os.getcwd()
        os.chdir(folder)
        try:
            np.random.seed(amorph_stats.postprocessing_seed("config.yaml"))
            dnest_functions.postprocess(plot=False, verbose=False)
        finally:
            os.chdir(cwd)
        results = amorph_results.from_run(folder)
        archive = amorph_archive.write(
            results, amorph_archive.default_name(results, folder))
    return results, archive
