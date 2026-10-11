#!/usr/bin/env python3
"""Web flasher helper.

  python main.py build               merge ../build and ../build_custom into firmware/*.bin + manifests
  python main.py [serve] [PORT]      serve this folder (default http://localhost:8000)

Build the firmware first (see the top-level README); variants whose build dir is missing are skipped.
Web Serial only works on https:// or http://localhost, so host the folder on any
static HTTPS host (e.g. GitHub Pages) to let other people flash from the browser.
"""
import functools
import http.server
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "firmware"


VARIANTS = {
    "devkit": ("DJI FCC patcher (dev board)", HERE.parent / "build"),
    "custom": ("DJI FCC patcher (custom PCB)", HERE.parent / "build_custom"),
}


def build():
    OUT.mkdir(exist_ok=True)
    built = 0
    for key, (name, build_dir) in VARIANTS.items():
        flasher_args = build_dir / "flasher_args.json"
        if not flasher_args.exists():
            print(f"skipping {key}: {flasher_args} not found")
            continue
        args = json.loads(flasher_args.read_text())
        parts = sorted((int(off, 16), build_dir / f) for off, f in args["flash_files"].items())
        image = bytearray()
        for off, path in parts:
            image.extend(b"\xff" * (off - len(image)))
            image.extend(path.read_bytes())
        (OUT / f"{key}.bin").write_bytes(image)
        (HERE / f"manifest-{key}.json").write_text(json.dumps({
            "name": name,
            "new_install_prompt_erase": True,
            "builds": [{
                "chipFamily": "ESP32-S3",
                "parts": [{"path": f"firmware/{key}.bin", "offset": 0}],
            }],
        }, indent=2) + "\n")
        print(f"{key}: {len(image)} bytes")
        built += 1
    if not built:
        sys.exit("nothing built")


def serve(port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    with http.server.ThreadingHTTPServer(("", port), handler) as srv:
        print(f"Serving on http://localhost:{port}  (open in Chrome or Edge)")
        srv.serve_forever()


if __name__ == "__main__":
    argv = sys.argv[1:]
    if argv[:1] == ["build"]:
        build()
    else:
        if argv[:1] == ["serve"]:
            argv = argv[1:]
        serve(int(argv[0]) if argv else 8000)
