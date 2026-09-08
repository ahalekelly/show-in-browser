# /// script
# requires-python = ">=3.11"
# ///
import json
import unittest
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


if __name__ == "__main__":
    unittest.main()
