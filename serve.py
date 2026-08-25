#!/usr/bin/env python3
"""Serve the local filesystem read-only over the tailnet, gzipping text."""

import functools
import gzip
import io
import os
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


COMPRESSIBLE = ("text/", "application/javascript", "application/json",
                "application/xhtml+xml", "image/svg+xml")

# Reports run to tens of megabytes of HTML that gzip to a fifth of that, and
# live reload refetches the whole file every second, so compressed bodies are
# kept until the file changes. One entry: polling hammers a single file.
cache = {}


class GzipHandler(SimpleHTTPRequestHandler):
    # Without a charset the browser decodes text as Windows-1252, and unlike
    # HTML, Markdown has no <meta charset> to override that.
    def guess_type(self, path):
        ctype = super().guess_type(path)
        return ctype + "; charset=utf-8" if ctype.startswith("text/") else ctype

    def send_head(self):
        path = self.translate_path(self.path)
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


bind_ip = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8377
handler = functools.partial(GzipHandler, directory="/")
ThreadingHTTPServer((bind_ip, port), handler).serve_forever()
