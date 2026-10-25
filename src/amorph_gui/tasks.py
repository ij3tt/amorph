"""
Long work off the UI thread. Tasks.run(fn, done, failed) calls fn() in a
QThreadPool worker, then done(result) or failed(message) back in the UI
thread, so that the window never waits for the post-processing or for
reading a large file.
"""

import sys
import traceback

from PySide6.QtCore import QObject, QThreadPool, Signal


def error_message(error):
    """
    The message of an exception, SystemExit (which trim_outputs raises)
    included.
    """
    text = str(error)
    return text if text else type(error).__name__


class Tasks(QObject):
    """
    A pool of worker threads; max_threads=1 runs the tasks one at a time.
    """

    # Emitted from the worker thread, delivered in the UI thread
    _finished = Signal(object, object, object)

    def __init__(self, max_threads=None, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        if max_threads is not None:
            self.pool.setMaxThreadCount(max_threads)
        self.active = 0
        self._finished.connect(self._deliver)

    def run(self, fn, done=None, failed=None):
        callbacks = (done, failed)

        def job():
            try:
                result = fn()
            except BaseException as e:
                traceback.print_exc(file=sys.stderr)
                self._finished.emit(callbacks, None, error_message(e))
            else:
                self._finished.emit(callbacks, result, None)

        self.active += 1
        self.pool.start(job)

    def _deliver(self, callbacks, result, error):
        self.active -= 1
        done, failed = callbacks
        if error is not None:
            if failed is not None:
                failed(error)
        elif done is not None:
            done(result)

    def wait(self):
        self.pool.waitForDone()
