#!/usr/bin/env python3
"""Serve the local filesystem read-only over the tailnet."""

import functools
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


bind_ip = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8377
handler = functools.partial(SimpleHTTPRequestHandler, directory="/")
ThreadingHTTPServer((bind_ip, port), handler).serve_forever()
