#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Serve web pages, their assets, and media files from the user's home on the trusted desktop LAN and tailnet."""

import functools
import gzip
import hashlib
import io
import ipaddress
import json
import selectors
from contextlib import ExitStack
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


class FileHandler(SimpleHTTPRequestHandler):
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


def listener_addresses():
    routes = json.loads(subprocess.run(
        ["ip", "-j", "-4", "route", "show", "default"],
        check=True, capture_output=True, text=True,
    ).stdout)
    lan_device = min(routes, key=lambda route: route.get("metric", 0))["dev"]
    interfaces = json.loads(subprocess.run(
        ["ip", "-j", "-4", "address", "show", "scope", "global"],
        check=True, capture_output=True, text=True,
    ).stdout)
    addresses = ["127.0.0.1"]
    for interface in interfaces:
        if interface["ifname"] not in (lan_device, "tailscale0"):
            continue
        for info in interface["addr_info"]:
            address = info["local"]
            if interface["ifname"] == lan_device and not any(
                ipaddress.ip_address(address) in ipaddress.ip_network(network)
                for network in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")
            ):
                raise ValueError(f"Desktop LAN address must be private: {address}")
            addresses.append(address)
    return addresses


def main():
    allowed_files_dir = runtime_allowed_files_dir()
    if len(sys.argv) > 2 and sys.argv[1] == "allow":
        for argument in sys.argv[2:]:
            print(allow_file(Path(argument), allowed_files_dir))
        return
    if len(sys.argv) != 1:
        raise SystemExit(f"usage: {sys.argv[0]} [allow FILE...]")

    handler = functools.partial(
        FileHandler,
        directory="/",
        home_root=Path.home().resolve(),
        allowed_files_dir=allowed_files_dir,
    )
    with ExitStack() as stack, selectors.DefaultSelector() as selector:
        for address in listener_addresses():
            server = stack.enter_context(ThreadingHTTPServer((address, PORT), handler))
            selector.register(server, selectors.EVENT_READ, server)
        while True:
            for key, _ in selector.select():
                key.data.handle_request()


if __name__ == "__main__":
    main()
