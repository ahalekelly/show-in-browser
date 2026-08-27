import functools
import gzip
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from serve import TailnetFileHandler, allow_file


class TailnetFileHandlerTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.allowed_files = Path(self.home.name, "allowed-files")
        handler = functools.partial(
            TailnetFileHandler,
            directory="/",
            home_root=Path(self.home.name).resolve(),
            allowed_files_dir=self.allowed_files,
        )
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.home.cleanup()

    def url(self, path):
        return self.origin + quote(str(path))

    def assert_not_found(self, path):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url(path))
        self.assertEqual(error.exception.code, 404)
        error.exception.close()

    def test_health_check(self):
        with urlopen(self.origin + "/") as response:
            self.assertEqual(response.read(), b"show-in-browser\n")

    def test_serves_html_and_markdown(self):
        for name in ("report.html", "notes.md"):
            path = Path(self.home.name, name)
            path.write_text(name)
            with urlopen(self.url(path)) as response:
                self.assertEqual(response.read().decode(), name)

    def test_gzips_text(self):
        path = Path(self.home.name, "report.html")
        path.write_text("report")
        request = Request(self.url(path), headers={"Accept-Encoding": "gzip"})
        with urlopen(request) as response:
            self.assertEqual(response.headers["Content-Encoding"], "gzip")
            self.assertEqual(gzip.decompress(response.read()), b"report")

    def test_rejects_other_file_types_and_directories(self):
        text = Path(self.home.name, "private.txt")
        text.write_text("private")
        self.assert_not_found(text)
        self.assert_not_found(Path(self.home.name))

    def test_rejects_paths_outside_home_and_symlink_escapes(self):
        with tempfile.TemporaryDirectory() as outside:
            secret = Path(outside, "secret.html")
            secret.write_text("secret")
            self.assert_not_found(secret)
            link = Path(self.home.name, "secret.html")
            link.symlink_to(secret)
            self.assert_not_found(link)

    def test_serves_an_explicitly_allowed_file(self):
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside, "data.csv")
            path.write_text("value")
            self.assert_not_found(path)
            allow_file(path, self.allowed_files)
            with urlopen(self.url(path)) as response:
                self.assertEqual(response.read(), b"value")


if __name__ == "__main__":
    unittest.main()
