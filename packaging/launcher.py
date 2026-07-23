"""Windows launcher entry point for the packaged .exe.

PyInstaller builds this into a single N1MMFieldDayTracker.exe. It simply runs
the normal application main(); the browser opens automatically. Kept separate
from app/main.py so the frozen build has a clean, import-safe entry point.
"""

import multiprocessing
import sys

from app.main import main

if __name__ == "__main__":
    multiprocessing.freeze_support()  # harmless if unused; safe for frozen exe
    sys.exit(main())
