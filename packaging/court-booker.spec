# PyInstaller build of the app, run by tools/build_app.py.
#
# One folder, not one file: a one-file app has a parent process that outlives a kill and
# unpacks to %TEMP% on every run, and the daily task needs a steady path. No console: the app
# and the task must not open a window, so sys.stdout is None, as under pythonw.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

REPO = Path(SPECPATH).parent
SOURCES = REPO / "src" / "court_booker"

analysis = Analysis(
    [str(SOURCES / "__main__.py")],
    pathex=[str(REPO / "src")],
    datas=[
        (str(SOURCES / "assets"), "court_booker/assets"),
        (str(REPO / "ui" / "dist"), "court_booker/ui"),
        *collect_data_files("uiautomator2"),
        *collect_data_files("adbutils"),
        *copy_metadata("adbutils"),
    ],
    # Uvicorn picks its loop and protocols by name, and importlib.resources needs the packages.
    hiddenimports=[
        *collect_submodules("uvicorn"),
        *collect_submodules("websockets"),
        "adbutils.binaries",
    ],
    excludes=["tkinter", "pytest"],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="court-booker",
    console=False,
    upx=False,
)
COLLECT(exe, analysis.binaries, analysis.datas, name="court-booker", upx=False)
