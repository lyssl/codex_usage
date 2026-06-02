from __future__ import annotations

import argparse
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import webview

import codex_usage


APP_TITLE = "Codex 用量统计"
HOST = "127.0.0.1"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Codex usage as a desktop app.")
    parser.add_argument(
        "--codex-home",
        default=str(codex_usage.default_codex_home()),
        help="Path to the Codex home directory.",
    )
    return parser.parse_args()


def build_server(codex_home: Path) -> ThreadingHTTPServer:
    frontend_file = resource_path("codex_usage.html")
    handler = type(
        "DesktopUsageHandler",
        (codex_usage.UsageHandler,),
        {
            "codex_home": codex_home,
            "frontend_file": frontend_file,
        },
    )
    return ThreadingHTTPServer((HOST, 0), handler)


def main() -> int:
    args = parse_args()
    codex_home = Path(args.codex_home).expanduser().resolve()
    server = build_server(codex_home)
    port = server.server_address[1]
    url = f"http://{HOST}:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        webview.create_window(APP_TITLE, url, width=1280, height=860, min_size=(980, 680))
        webview.start()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
