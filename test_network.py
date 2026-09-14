# /// script
# requires-python = ">=3.11"
# ///
import json
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from http.client import HTTPConnection
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from serve import listener_addresses


class ListenerAddressesTest(unittest.TestCase):
    def addresses(self, lan="192.168.1.217", tailnet=True):
        interfaces = [
            {"ifname": "enp37s0", "addr_info": [{"local": lan}]},
            {"ifname": "cni0", "addr_info": [{"local": "10.42.0.1"}]},
        ]
        if tailnet:
            interfaces.append({"ifname": "tailscale0", "addr_info": [{"local": "100.96.0.113"}]})
        with patch("serve.subprocess.run", side_effect=[
            SimpleNamespace(stdout=json.dumps([{"dev": "enp37s0", "metric": 100}])),
            SimpleNamespace(stdout=json.dumps(interfaces)),
        ]):
            return listener_addresses()

    def test_only_lan_tailnet_and_loopback(self):
        self.assertEqual(self.addresses(), ["127.0.0.1", "192.168.1.217", "100.96.0.113"])

    def test_lan_works_without_tailscale(self):
        self.assertEqual(self.addresses(tailnet=False), ["127.0.0.1", "192.168.1.217"])

    def test_public_lan_address_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Desktop LAN address must be private"):
            self.addresses(lan="8.8.8.8")


class ListenerRefreshTest(unittest.TestCase):
    def test_running_server_adds_and_removes_addresses(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+t") as log:
            addresses_file = Path(directory, "addresses.json")

            def discover(*addresses):
                replacement = addresses_file.with_suffix(".new")
                replacement.write_text(json.dumps(addresses))
                replacement.replace(addresses_file)

            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", 0))
                port = reservation.getsockname()[1]

            discover("127.0.0.1", "127.0.0.2")
            process = subprocess.Popen(
                [sys.executable, "-c", """
import json
import sys
from pathlib import Path
import serve

addresses_file = Path(sys.argv[1])
serve.PORT = int(sys.argv[2])
serve.ADDRESS_REFRESH_SECONDS = 0.02
serve.listener_addresses = lambda: json.loads(addresses_file.read_text())
serve.runtime_allowed_files_dir = lambda: addresses_file.parent / "allowed-files"
sys.argv = ["serve.py"]
serve.main()
""", str(addresses_file), str(port)],
                cwd=Path(__file__).parent,
                stdout=subprocess.DEVNULL,
                stderr=log,
                text=True,
            )

            def wait_for_listener(address, expected):
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        log.seek(0)
                        self.fail(f"Server exited: {log.read()}")
                    connection = HTTPConnection(address, port, timeout=0.2)
                    try:
                        connection.request("GET", "/")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.read(), b"show-in-browser\n")
                        reachable = True
                    except ConnectionRefusedError:
                        reachable = False
                    finally:
                        connection.close()
                    if reachable == expected:
                        return
                    time.sleep(0.01)
                self.fail(f"Listener {address} did not become {'reachable' if expected else 'closed'}")

            try:
                wait_for_listener("127.0.0.1", True)
                wait_for_listener("127.0.0.2", True)
                wait_for_listener("127.0.0.3", False)

                # Tailscale becomes available after the server starts.
                discover("127.0.0.1", "127.0.0.2", "127.0.0.3")
                wait_for_listener("127.0.0.3", True)
                wait_for_listener("127.0.0.2", True)

                # The LAN address changes and Tailscale disconnects.
                discover("127.0.0.1", "127.0.0.4")
                wait_for_listener("127.0.0.4", True)
                wait_for_listener("127.0.0.2", False)
                wait_for_listener("127.0.0.3", False)
                wait_for_listener("127.0.0.1", True)
            finally:
                process.terminate()
                try:
                    process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate()


if __name__ == "__main__":
    unittest.main()
