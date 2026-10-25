"""Builds dist/Stash.alfredworkflow from the checkout: uv run python scripts/build.py"""

import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLE = os.path.join(ROOT, "dist", "Stash.alfredworkflow")
FILES = ("info.plist", "icon.png", "run.py")
PACKAGE = "stash"


def package_files():
    folder = os.path.join(ROOT, PACKAGE)
    return sorted(os.path.join(PACKAGE, name) for name in os.listdir(folder) if name.endswith(".py"))


def build():
    subprocess.run([sys.executable, os.path.join(ROOT, "make_plist.py")], cwd=ROOT, check=True)
    os.makedirs(os.path.dirname(BUNDLE), exist_ok=True)
    with zipfile.ZipFile(BUNDLE, "w", zipfile.ZIP_DEFLATED) as bundle:
        for path in (*FILES, *package_files()):
            bundle.write(os.path.join(ROOT, path), path)
    print(BUNDLE)


if __name__ == "__main__":
    build()
