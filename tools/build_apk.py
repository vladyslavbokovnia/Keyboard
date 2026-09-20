#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import argparse
import shutil
import subprocess
import tempfile


def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run([str(x) for x in cmd], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--patcher", type=Path, default=Path(__file__).with_name("patch_theme_pb.py"))
    ap.add_argument("--keystore", type=Path, required=True)
    ap.add_argument("--storepass", default="android")
    ap.add_argument("--alias", default="gboardpatch")
    args = ap.parse_args()
    root = Path(tempfile.mkdtemp(prefix="gboard-build-"))
    try:
        extracted = root / "extracted"
        patched = root / "patched"
        unsigned = root / "unsigned.apk"
        aligned = root / "aligned.apk"
        with ZipFile(args.source) as zin:
            zin.extractall(extracted)
        theme_in = extracted / "assets" / "theme"
        theme_out = patched / "assets" / "theme"
        run(["python3", args.patcher, "--input", theme_in, "--output", theme_out])
        changed = {p.name: p for p in theme_out.glob("*.binarypb")}
        with ZipFile(args.source, "r") as zin, ZipFile(unsigned, "w", ZIP_DEFLATED, compresslevel=6) as zout:
            for info in zin.infolist():
                if info.filename.startswith("META-INF/"):
                    continue
                name = info.filename.rsplit("/", 1)[-1]
                if info.filename.startswith("assets/theme/") and name in changed:
                    data = changed[name].read_bytes()
                else:
                    data = zin.read(info.filename)
                zout.writestr(info, data)
        run(["zipalign", "-f", "-p", "4", unsigned, aligned])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        run(["apksigner", "sign", "--ks", args.keystore,
             "--ks-pass", f"pass:{args.storepass}",
             "--key-pass", f"pass:{args.storepass}",
             "--ks-key-alias", args.alias, "--out", args.output, aligned])
        run(["apksigner", "verify", "--verbose", args.output])
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
