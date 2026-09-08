# /// script
# requires-python = ">=3.11"
# ///
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RemoteRoutingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        config = self.root / ".config/show-in-browser"
        config.mkdir(parents=True)
        (config / "host").write_text("Mac.local\nmac.example.ts.net\n")
        self.file = self.root / "report.html"
        self.file.write_text("report")
        self.log = self.root / "calls.jsonl"
        mock = self.root / "mock"
        mock.write_text('''#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
import json, os, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ["CALL_LOG"], "a") as log:
    log.write(json.dumps([name, *args]) + "\\n")
if name == "uname":
    print("Linux")
elif name == "hostname":
    print("desktop")
elif name == "tailscale":
    print(json.dumps({"Self": {"DNSName": "desktop.example.ts.net.", "TailscaleIPs": ["100.64.0.1"]}}))
elif name == "ssh":
    if os.environ.get("FAIL_ALL") or ("Mac.local" in args and os.environ.get("FAIL_LOCAL")):
        sys.exit(255)
    if "Mac.local" in args and any("curl" in arg for arg in args) and os.environ.get("FAIL_LOCAL_HTTP"):
        sys.exit(1)
''')
        mock.chmod(0o755)
        for name in ("uname", "hostname", "ssh", "curl", "tailscale", "systemctl"):
            (self.root / name).symlink_to(mock)
        self.env = dict(os.environ, HOME=str(self.root), XDG_RUNTIME_DIR=str(self.root),
                        PATH=f"{self.root}:{os.environ['PATH']}", CALL_LOG=str(self.log))

    def run_script(self, *args, **env):
        return subprocess.run(
            ["bash", str(Path(__file__).with_name("show-in-browser.sh")), *args],
            env=self.env | env, capture_output=True, text=True,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_local_route_never_uses_tailscale(self):
        result = self.run_script(str(self.file), "last")
        self.assertEqual(result.returncode, 0, result.stderr)
        calls = self.calls()
        self.assertFalse(any(call[0] == "tailscale" for call in calls))
        opened = calls[-1]
        self.assertIn("Mac.local", opened)
        self.assertIn("http://desktop.local:8377", opened[-1])
        self.assertIn("HostKeyAlias=mac", opened)

    def test_unavailable_local_ssh_uses_tailnet(self):
        result = self.run_script(str(self.file), FAIL_LOCAL="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        opened = self.calls()[-1]
        self.assertIn("mac.example.ts.net", opened)
        self.assertIn("http://desktop.example.ts.net:8377", opened[-1])

    def test_unavailable_local_http_uses_tailnet(self):
        result = self.run_script(str(self.file), FAIL_LOCAL_HTTP="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mac.example.ts.net", self.calls()[-1])

    def test_no_route_fails_without_opening_browser(self):
        result = self.run_script(str(self.file), FAIL_ALL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot reach the Mac", result.stderr)
        self.assertFalse(any("~/Git/show-in-browser/show-in-browser.sh" in call[-1]
                             for call in self.calls()))

    def test_url_is_quoted_for_remote_shell(self):
        url = "https://example.com/?x=1&y=$(touch /tmp/unwanted)"
        result = self.run_script(url)
        self.assertEqual(result.returncode, 0, result.stderr)
        command = self.calls()[-1][-1]
        self.assertIn(r"\&", command)
        self.assertIn(r"\$", command)
        self.assertFalse(any(call[0] == "tailscale" for call in self.calls()))


if __name__ == "__main__":
    unittest.main()
