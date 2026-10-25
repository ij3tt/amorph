"""
The runs of the sampler: one QProcess at a time, in the folder of the run.
While it works, a worker thread counts its saves and levels and reads its
last saved sample every second; when it ends, another worker
post-processes it and writes the run archive, while the next seed runs.
"""

import codecs
import os
import time

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

import amorph_stats

from amorph_gui import runfiles
from amorph_gui import strings as S
from amorph_gui.tasks import Tasks

WAITING = "waiting"
RUNNING = "running"
STOPPING = "stopping"
POSTPROCESSING = "postprocessing"
DONE = "done"
INCOMPLETE = "incomplete"
FAILED = "failed"
CANCELLED = "cancelled"

# The states of a run that is not over yet
ACTIVE = (WAITING, RUNNING, STOPPING, POSTPROCESSING)

STATUS_TEXT = {WAITING: S.STATUS_WAITING, RUNNING: S.STATUS_RUNNING,
               STOPPING: S.STATUS_STOPPING,
               POSTPROCESSING: S.STATUS_POSTPROCESSING, DONE: S.STATUS_DONE,
               INCOMPLETE: S.STATUS_INCOMPLETE, FAILED: S.STATUS_FAILED,
               CANCELLED: S.STATUS_CANCELLED}

# How often the progress of the sampler is read, in milliseconds
POLL_INTERVAL = 1000


class Run(object):
    """
    One run of the sampler: its folder and seed, the planned number of
    saves (0: no limit), the analysed data (x, y), and what has happened
    so far.
    """

    def __init__(self, folder, seed, planned, x, y):
        self.folder = folder
        self.seed = seed
        self.planned = planned
        self.x = x
        self.y = y
        self.status = WAITING
        self.saves = 0
        self.levels = 0
        self.sample = None
        self.started = None
        self.ended = None
        self.log = []
        self.stopped = False
        self.error = None
        self.results = None
        self.archive = None
        # The last complete levels.txt, in case killing the sampler cuts it
        self.saved_levels = None
        self.reader = runfiles.SampleReader(os.path.join(folder,
                                                         "sample.txt"))
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._polling = False
        self._poll_again = False

    @property
    def name(self):
        return os.path.basename(self.folder)

    def elapsed(self):
        if self.started is None:
            return 0.0
        return (self.ended if self.ended is not None
                else time.monotonic()) - self.started

    def log_text(self):
        return "".join(self.log)


def format_time(seconds):
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return "{0}:{1:02d}:{2:02d}".format(h, m, s) if h \
        else "{0:02d}:{1:02d}".format(m, s)


def append_log(run, text):
    with open(os.path.join(run.folder, runfiles.LOG_FILE), "a",
              encoding="utf-8") as f:
        f.write(text)


class RunQueue(QObject):
    """
    Runs the sampler for each run, one after another.

    changed(run): the state or progress of a run changed.
    output(run, text): the sampler of a run wrote text.
    postprocessed(run): a run has its results (or failed to get them).
    finished(runs): every run started since the last finished() is over.
    """

    changed = Signal(object)
    output = Signal(object, str)
    postprocessed = Signal(object)
    finished = Signal(list)

    def __init__(self, tasks, parent=None):
        super().__init__(parent)
        self.tasks = tasks
        # One post-processing at a time: each reads the whole sample.txt
        self.post_tasks = Tasks(max_threads=1, parent=self)
        self.runs = []
        self.batch = []
        self.current = None
        self.process = None
        self.program = None
        self.arguments = []
        self.timer = QTimer(self)
        self.timer.setInterval(POLL_INTERVAL)
        self.timer.timeout.connect(self._tick)

    def busy(self):
        return any(r.status in ACTIVE for r in self.batch)

    def start(self, runs, program, arguments=()):
        """
        Queue runs, and start the first if no sampler is running. program
        and arguments start the sampler.
        """
        self.program = program
        self.arguments = list(arguments)
        self.runs.extend(runs)
        self.batch.extend(runs)
        for run in runs:
            self.changed.emit(run)
        if self.process is None:
            self._next()

    def stop(self):
        """
        Kill the sampler that is running, keep its complete saves and
        post-process them, and cancel the runs that wait.
        """
        for run in self.batch:
            if run.status == WAITING:
                run.status = CANCELLED
                self.changed.emit(run)
        if self.process is not None and self.current is not None:
            run = self.current
            run.stopped = True
            run.status = STOPPING
            self._save_levels(run, runfiles.levels_text(run.folder))
            self.changed.emit(run)
            self.process.kill()
        self._check_finished()

    def shutdown(self):
        """
        When the window closes: kill the sampler, leave its complete saves
        in its folder for showresults.py, and wait for the workers.
        """
        for run in self.batch:
            if run.status == WAITING:
                run.status = CANCELLED
        run, process = self.current, self.process
        if process is not None:
            run.stopped = True
            self._save_levels(run, runfiles.levels_text(run.folder))
            process.blockSignals(True)
            process.kill()
            process.waitForFinished(5000)
            run.status = INCOMPLETE
            try:
                runfiles.restore_levels(run.folder, run.saved_levels)
                kept = amorph_stats.trim_outputs(run.folder)
                append_log(run, S.RUN_STOPPED_LOG.format(kept) + "\n")
            except (OSError, SystemExit):
                pass
            self.process = None
        self.timer.stop()
        self.post_tasks.wait()

    # -------------------------------------------------------- the sampler

    def _next(self):
        waiting = [r for r in self.batch if r.status == WAITING]
        if not waiting:
            self.current = None
            self.timer.stop()
            self._check_finished()
            return
        run = waiting[0]
        self.current = run
        process = QProcess(self)
        process.setWorkingDirectory(run.folder)
        process.setProcessChannelMode(QProcess.MergedChannels)
        process.readyReadStandardOutput.connect(
            lambda: self._read(run, process))
        process.finished.connect(
            lambda code, status: self._ended(run, process, code, status))
        process.errorOccurred.connect(
            lambda error: self._error(run, process, error))
        run.status = RUNNING
        run.started = time.monotonic()
        self.process = process
        self.changed.emit(run)
        process.start(self.program, self.arguments)
        # AMORPH.exe in a console of its own waits for Enter after an error:
        # give it the end of its input instead
        process.closeWriteChannel()
        self.timer.start()

    def _read(self, run, process):
        data = bytes(process.readAllStandardOutput().data())
        text = run._decoder.decode(data)
        if text:
            run.log.append(text)
            append_log(run, text)
            self.output.emit(run, text)

    def _error(self, run, process, error):
        # A sampler that never started gets no finished()
        if error != QProcess.FailedToStart:
            return
        run.status = FAILED
        run.error = S.CANNOT_START.format(self.program, process.errorString())
        run.ended = time.monotonic()
        self._note(run, run.error + "\n")
        self.process = None
        process.deleteLater()
        # The others would fail the same way
        for other in self.batch:
            if other.status == WAITING:
                other.status = CANCELLED
                self.changed.emit(other)
        self.changed.emit(run)
        self._next()

    def _ended(self, run, process, code, status):
        self._read(run, process)
        run.ended = time.monotonic()
        self.process = None
        process.deleteLater()
        self._poll(run)
        if run.stopped:
            self._postprocess(run)
        elif status == QProcess.NormalExit and code == 0:
            self._postprocess(run)
        else:
            run.status = FAILED
            run.error = S.RUN_FAILED.format(code)
            self.changed.emit(run)
        self._next()

    def _note(self, run, text):
        run.log.append(text)
        append_log(run, text)
        self.output.emit(run, text)

    # ------------------------------------------------------- the progress

    def _tick(self):
        if self.current is not None and self.current.status == RUNNING:
            self._poll(self.current)
        elif self.current is not None:
            self.changed.emit(self.current)

    def _poll(self, run):
        if run._polling:
            run._poll_again = True
            return
        run._polling = True
        folder, reader = run.folder, run.reader

        def done(p):
            run._polling = False
            run.saves, run.levels = p["saves"], p["levels"]
            if p["sample"] is not None:
                run.sample = p["sample"]
            if run.status == RUNNING:
                self._save_levels(run, p["levels_text"])
            self.changed.emit(run)
            if run._poll_again:
                run._poll_again = False
                self._poll(run)

        def failed(message):
            run._polling = False

        self.tasks.run(lambda: runfiles.progress(folder, reader), done, failed)

    def _save_levels(self, run, text):
        if text is not None and (run.saved_levels is None
                                 or len(text) >= len(run.saved_levels)):
            run.saved_levels = text

    # -------------------------------------------------- post-processing

    def _postprocess(self, run):
        run.status = POSTPROCESSING
        self.changed.emit(run)
        stopped = run.stopped
        saved_levels = run.saved_levels

        def job():
            note = None
            if stopped:
                runfiles.restore_levels(run.folder, saved_levels)
                kept = amorph_stats.trim_outputs(run.folder)
                note = S.RUN_STOPPED_LOG.format(kept) + "\n"
                append_log(run, note)
            return note, runfiles.postprocess(run.folder)

        def done(result):
            note, (results, archive) = result
            if note is not None:
                run.log.append(note)
                self.output.emit(run, note)
            run.results, run.archive = results, archive
            run.status = INCOMPLETE if run.stopped else DONE
            self.changed.emit(run)
            self.postprocessed.emit(run)
            self._check_finished()

        def failed(message):
            run.status = FAILED
            run.error = S.POSTPROCESS_FAILED.format(message)
            self._note(run, run.error + "\n")
            self.changed.emit(run)
            self.postprocessed.emit(run)
            self._check_finished()

        self.post_tasks.run(job, done, failed)

    def _check_finished(self):
        if self.batch and not self.busy():
            runs, self.batch = self.batch, []
            self.timer.stop()
            self.finished.emit(runs)
