import sys
import os
import logging
import threading
import traceback
from logging.handlers import RotatingFileHandler

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

LOG_PATH = os.path.join(os.path.expanduser("~"), ".plexNFOPro", "error.log")
logger = logging.getLogger("plexnfopro")


def setup_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)


class ErrorReporter(QObject):
    errorOccurred = pyqtSignal(str, str)   # short summary, full traceback

    def __init__(self):
        super().__init__()                  # create this on the UI thread so the dialog opens there
        self._dialog_open = False
        self.errorOccurred.connect(self._show_dialog)

    def report(self, exc_type, exc_value, exc_tb):
        """Safe to call from any thread."""
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.error(details)               # always written to the log file
        self.errorOccurred.emit(f"{exc_type.__name__}: {exc_value}", details)

    def _show_dialog(self, summary, details):
        if self._dialog_open:               # don't stack up 50 dialogs if something fails in a loop
            return
        self._dialog_open = True
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("NFOPro for Plex - Unexpected Error")
        box.setText("Something went wrong:")
        box.setInformativeText(summary + f"\n\nA full report was saved to:\n{LOG_PATH}")
        box.setDetailedText(details)        # adds a "Show Details..." button with the traceback
        box.exec()
        self._dialog_open = False


def install_global_handlers(reporter):
    def excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        reporter.report(exc_type, exc_value, exc_tb)

    def thread_excepthook(args):            # for plain Python threads
        reporter.report(args.exc_type, args.exc_value, args.exc_traceback)

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook