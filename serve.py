#!/usr/bin/env python3
"""Serve web pages, their assets, and media files from the user's home over the tailnet."""

import functools
import gzip
import hashlib
import io
import os
import subprocess
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


COMPRESSIBLE = ("text/", "application/javascript", "application/json",
                "application/xhtml+xml", "application/xml", "application/wasm",
                "application/manifest+json", "image/svg+xml")
# Documents plus everything a page references: scripts, styles, data, fonts,
# images, audio, and video. Other data files need an explicit allow.
SERVABLE_SUFFIXES = {
    ".html", ".htm", ".xhtml", ".md", ".pdf",
    ".css", ".js", ".mjs", ".json", ".xml", ".wasm", ".webmanifest",
    ".woff", ".woff2", ".ttf", ".otf",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".svg", ".ico",
    ".mp3", ".m4a", ".wav", ".ogg", ".mp4", ".webm",
}
PORT = 8377

# Reports run to tens of megabytes of HTML that gzip to a fifth of that, and
# live reload refetches the whole file every second, so compressed bodies are
# kept until the file changes. One entry: polling hammers a single file.
cache = {}


class TailnetFileHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, home_root, allowed_files_dir, **kwargs):
        self.home_root = home_root
        self.allowed_files_dir = allowed_files_dir
        super().__init__(*args, **kwargs)

    # Without a charset the browser decodes text as Windows-1252, and unlike
    # HTML, Markdown has no <meta charset> to override that.
    def guess_type(self, path):
        ctype = super().guess_type(path)
        return ctype + "; charset=utf-8" if ctype.startswith("text/") else ctype

    def send_head(self):
        if urlsplit(self.path).path == "/":
            body = b"show-in-browser\n"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            return io.BytesIO(body)

        path = Path(self.translate_path(self.path)).resolve()
        default_allowed = (
            self.home_root in path.parents
            and path.suffix.lower() in SERVABLE_SUFFIXES
        )
        explicitly_allowed = approval_path(path, self.allowed_files_dir).exists()
        if not path.is_file() or not (default_allowed or explicitly_allowed):
            self.send_error(HTTPStatus.NOT_FOUND)
            return None

        ctype = self.guess_type(path)
        if not (ctype.startswith(COMPRESSIBLE)
                and "gzip" in self.headers.get("Accept-Encoding", "")
                and os.path.isfile(path)):
            return super().send_head()

        stat = os.stat(path)
        last_modified = self.date_time_string(stat.st_mtime)
        # Browsers echo the Last-Modified they were sent, so matching the string
        # is enough to recognize an unchanged file.
        if self.headers.get("If-Modified-Since") == last_modified:
            self.send_response(HTTPStatus.NOT_MODIFIED)
            self.end_headers()
            return None

        key = (path, stat.st_mtime_ns, stat.st_size)
        body = cache.get(key)
        if body is None:
            with open(path, "rb") as f:
                body = gzip.compress(f.read(), 6)
            cache.clear()
            cache[key] = body

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Last-Modified", last_modified)
        self.send_header("Vary", "Accept-Encoding")
        self.end_headers()
        return io.BytesIO(body)


def approval_path(path, allowed_files_dir):
    digest = hashlib.sha256(str(path).encode()).hexdigest()
    return allowed_files_dir / digest


def runtime_allowed_files_dir():
    return Path(os.environ["XDG_RUNTIME_DIR"], "show-in-browser", "allowed-files")


def allow_file(path, allowed_files_dir):
    path = path.resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"not a regular file: {path}")
    allowed_files_dir.mkdir(parents=True, exist_ok=True)
    approval_path(path, allowed_files_dir).touch()
    return path


def main():
    allowed_files_dir = runtime_allowed_files_dir()
    if len(sys.argv) == 3 and sys.argv[1] == "allow":
        print(allow_file(Path(sys.argv[2]), allowed_files_dir))
        return
    if len(sys.argv) != 1:
        raise SystemExit(f"usage: {sys.argv[0]} [allow FILE]")

    bind_ip = subprocess.run(
        ["tailscale", "ip", "--4"], check=True, capture_output=True, text=True
    ).stdout.strip()
    handler = functools.partial(
        TailnetFileHandler,
        directory="/",
        home_root=Path.home().resolve(),
        allowed_files_dir=allowed_files_dir,
    )
    ThreadingHTTPServer((bind_ip, PORT), handler).serve_forever()


if __name__ == "__main__":
    main()
