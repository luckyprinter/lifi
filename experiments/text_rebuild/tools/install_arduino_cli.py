#!/usr/bin/env python3
import json
import os
import platform
import shutil
import stat
import sys
import tarfile
import tempfile
import urllib.request
import zipfile


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BIN_DIR = os.path.join(ROOT_DIR, "tools", "bin")
TMP_DIR = os.path.join(ROOT_DIR, "tools", "tmp")
RELEASE_API = "https://api.github.com/repos/arduino/arduino-cli/releases/latest"


def system_key():
    system = platform.system().lower()
    machine = platform.machine().lower()

    if system == "windows":
        os_key = "Windows"
        ext = ".zip"
    elif system == "linux":
        os_key = "Linux"
        ext = ".tar.gz"
    elif system == "darwin":
        os_key = "macOS"
        ext = ".tar.gz"
    else:
        raise SystemExit(f"Unsupported OS for automatic Arduino CLI install: {platform.system()}")

    if machine in ("x86_64", "amd64"):
        arch = "64bit"
    elif machine in ("aarch64", "arm64"):
        arch = "ARM64"
    elif machine.startswith("arm"):
        arch = "ARMv7"
    else:
        raise SystemExit(f"Unsupported CPU architecture for automatic Arduino CLI install: {platform.machine()}")

    return os_key, arch, ext


def fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "lifi-text-rebuild-installer"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def choose_asset(release):
    os_key, arch, ext = system_key()
    assets = release.get("assets", [])
    matches = []
    for asset in assets:
        name = asset.get("name", "")
        if os_key in name and arch in name and name.endswith(ext):
            matches.append(asset)

    if not matches:
        available = "\n".join(asset.get("name", "") for asset in assets)
        raise SystemExit(f"No Arduino CLI asset matched {os_key} {arch} {ext}.\n\nAvailable assets:\n{available}")

    return matches[0]


def download(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": "lifi-text-rebuild-installer"})
    with urllib.request.urlopen(request, timeout=120) as response, open(dest, "wb") as out:
        shutil.copyfileobj(response, out)


def extract_cli(archive_path, work_dir):
    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(work_dir)
    else:
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(work_dir)

    exe_name = "arduino-cli.exe" if platform.system().lower() == "windows" else "arduino-cli"
    for root, _dirs, files in os.walk(work_dir):
        if exe_name in files:
            return os.path.join(root, exe_name)

    raise SystemExit(f"Could not find {exe_name} in downloaded Arduino CLI archive.")


def main():
    if any(arg in ("-h", "--help") for arg in sys.argv[1:]):
        print("Install Arduino CLI into experiments/text_rebuild/tools/bin.")
        print("Usage: python3 experiments/text_rebuild/tools/install_arduino_cli.py")
        return

    os.makedirs(BIN_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    exe_name = "arduino-cli.exe" if platform.system().lower() == "windows" else "arduino-cli"
    dest = os.path.join(BIN_DIR, exe_name)

    print("Checking latest Arduino CLI release...")
    release = fetch_json(RELEASE_API)
    asset = choose_asset(release)
    url = asset["browser_download_url"]
    name = asset["name"]
    print(f"Downloading {name}...")

    with tempfile.TemporaryDirectory(dir=TMP_DIR) as temp_dir:
        archive_path = os.path.join(temp_dir, name)
        download(url, archive_path)
        extracted_cli = extract_cli(archive_path, temp_dir)
        shutil.copy2(extracted_cli, dest)

    if platform.system().lower() != "windows":
        mode = os.stat(dest).st_mode
        os.chmod(dest, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"Installed Arduino CLI to: {dest}")
    print("You can now use Compile/Upload from the LiFi Text Debug GUI.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"INSTALL_ERROR:{exc}")
        sys.exit(1)
