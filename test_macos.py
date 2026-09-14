# /// script
# requires-python = ">=3.11"
# ///
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class MacAutomationTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.log = root / "calls.jsonl"
        mock = root / "mock"
        mock.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
if Path(sys.argv[0]).name == "uname":
    print("Darwin")
    sys.exit()
script = sys.argv[2] if sys.argv[1] == "-e" else sys.stdin.read()
with open(os.environ["CALL_LOG"], "a") as log:
    log.write(json.dumps(script) + "\\n")
if script.startswith("id of application"):
    print("com.vivaldi.Vivaldi")
elif os.environ["FAIL_SCRIPT"] in script:
    print(os.environ["SCRIPT_ERROR"], file=sys.stderr)
    sys.exit(1)
elif "get name of first process" in script:
    print("Terminal")
else:
    print("already open")
''')
        mock.chmod(0o755)
        for name in ("uname", "osascript"):
            (root / name).symlink_to(mock)
        self.env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}",
                        CALL_LOG=str(self.log))

    def run_script(self, target, error):
        return subprocess.run(
            ["bash", str(Path(__file__).with_name("show-in-browser.sh")),
             "/tmp/report with spaces.html", "last"],
            env=self.env | {"FAIL_SCRIPT": target, "SCRIPT_ERROR": error},
            capture_output=True, text=True,
        )

    def test_denied_frontmost_query_explains_permission_before_browser_mutation(self):
        error = "40:85: execution error: Not authorized to send Apple events to System Events. (-1743)"
        result = self.run_script("get name of first process", error)
        self.assertEqual(result.returncode, 1)
        self.assertIn(error, result.stderr)
        self.assertIn("System Settings > Privacy & Security > Automation", result.stderr)
        self.assertIn("app running this command", result.stderr)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertFalse(any("make new tab" in call for call in calls))

    def test_denied_browser_event_gets_permission_guidance(self):
        error = "execution error: Not authorized to send Apple events to Vivaldi. (-1743)"
        result = self.run_script("make new tab", error)
        self.assertEqual(result.returncode, 1)
        self.assertIn(error, result.stderr)
        self.assertIn("System Settings > Privacy & Security > Automation", result.stderr)

    def test_other_errors_are_not_reported_as_permission_failures(self):
        error = "execution error: Vivaldi got an error: Invalid index. (-1719)"
        result = self.run_script("make new tab", error)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.strip(), error)

    def test_success_keeps_result(self):
        result = self.run_script("never matches", "")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "already open")
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
