"""Stable launcher. Future logic updates are ZIP files, not replacement EXEs."""
import os
import sys
import json
import hashlib
import shutil
import runpy
import zipfile
import subprocess
import ctypes
from ctypes import wintypes
import time
from pathlib import Path
import tkinter
from tkinter import messagebox, filedialog
import cv2
import numpy
from PIL import Image, ImageTk, ImageGrab


def validate(folder):
    manifest = json.loads((folder/'version.json').read_text(encoding='utf-8'))
    if set(manifest['sha256']) != {'seal_app.py', 'vision_tracker.py'}:
        raise ValueError('Invalid update manifest')
    for name, digest in manifest['sha256'].items():
        data = (folder/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Update checksum failed: '+name)
        compile(data, name, 'exec')
    return manifest


def promote(home, source):
    validate(source)
    runtime = home/'runtime'
    # Keep recoverable backups; do not remove existing data or calibration.
    backup = home/('backup-'+str(time.time_ns()))
    staged = home/('staged-'+str(time.time_ns()))
    shutil.copytree(source, staged)
    if runtime.exists():
        runtime.rename(backup)
    try:
        staged.rename(runtime)
    except Exception:
        if backup.exists() and not runtime.exists():
            backup.rename(runtime)
        raise


def main():
    home = Path(os.environ.get('LOCALAPPDATA', str(Path.home())))/'SealVision'
    home.mkdir(parents=True, exist_ok=True)
    runtime = home/'runtime'
    seed = Path(getattr(sys, '_MEIPASS', Path(__file__).parent))/'app_seed'
    if not runtime.exists():
        promote(home, seed)
    pending = home/'pending_update'
    if (pending/'version.json').exists():
        promote(home, pending)
        pending.rename(home/('applied-update-'+str(time.time_ns())))
    validate(runtime)
    os.environ['SEAL_VISION_LAUNCHER'] = sys.executable
    sys.path.insert(0, str(runtime))
    runpy.run_path(str(runtime/'seal_app.py'), run_name='__main__')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror('Seal Vision', 'เปิดโปรแกรมไม่สำเร็จ: '+str(error))
        root.destroy()
