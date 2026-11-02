#!/usr/bin/env python3
"""Replay FunctionFS readiness ordering and gadget configuration transitions.

This models the relevant init commands, not the USB kernel or the USB host.
Run against the original init file to reproduce the early MTP bind and stale
function regressions. Real hardware testing remains necessary.
"""

from pathlib import Path
import shlex
import sys
import unittest


class UsbInit:
    def __init__(self, source, configfs="1"):
        self.actions = []
        conditions = None
        for line in source.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("on "):
                triggers = line[3:].split(" && ")
                conditions = None
                if all(item.startswith("property:") for item in triggers):
                    conditions = dict(item[9:].split("=", 1) for item in triggers)
                    self.actions.append((conditions, []))
            elif conditions is not None:
                self.actions[-1][1].append(shlex.split(line))
        self.props = {"sys.usb.configfs": configfs,
                      "sys.usb.controller": "4e00000.dwc3"}
        self.links = {}
        self.running = set()
        self.bound = set()
        self.bind_attempts = []

    def set(self, name, value):
        if self.props.get(name) == value:
            return
        self.props[name] = value
        for conditions, commands in self.actions:
            if name not in conditions:
                continue
            if not all(self.props.get(key) == expected
                       for key, expected in conditions.items()):
                continue
            for args in commands:
                op, *args = args
                if op == "setprop":
                    self.set(args[0], self.expand(args[1]))
                elif op == "start":
                    self.running.add(args[0])
                elif op == "stop":
                    self.running.discard(args[0])
                elif op == "symlink":
                    # An existing configfs function link cannot be replaced.
                    self.links.setdefault(args[1], args[0].rsplit("/", 1)[-1])
                elif op == "rm":
                    self.links.pop(args[0], None)
                elif op == "write" and args[0].endswith("/UDC"):
                    if args[1] == "none":
                        self.bound.clear()
                    else:
                        functions = set(self.links.values())
                        self.bind_attempts.append(functions)
                        ready = {
                            "ffs.adb": self.props.get("sys.usb.ffs.ready") == "1",
                            "ffs.fastboot": self.props.get("sys.usb.ffs.ready") == "1",
                            "ffs.mtp": self.props.get("sys.usb.ffs.mtp.ready") == "1",
                        }
                        if functions and all(ready.get(fn, False) for fn in functions):
                            self.bound = functions

    def expand(self, value):
        if value.startswith("${") and value.endswith("}"):
            return self.props.get(value[2:-1], "")
        return value


source_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[2] / "recovery/root/init.recovery.usb.rc"
)
source = source_path.read_text()
# Keep the optional source path out of unittest's option parser.
sys.argv = sys.argv[:1]


class UsbTransitions(unittest.TestCase):
    def test_mtp_waits_for_both_descriptor_writers(self):
        for first, second in [("sys.usb.ffs.ready", "sys.usb.ffs.mtp.ready"),
                              ("sys.usb.ffs.mtp.ready", "sys.usb.ffs.ready")]:
            with self.subTest(first=first):
                usb = UsbInit(source)
                usb.set("sys.usb.config", "mtp,adb")
                usb.set(first, "1")
                self.assertEqual(usb.bind_attempts, [], "bound before both descriptors")
                usb.set(second, "1")
                self.assertEqual(usb.bound, {"ffs.adb", "ffs.mtp"})
                self.assertEqual(usb.props.get("sys.usb.state"), "mtp,adb")

    def test_mtp_to_adb_sideload_and_fastboot(self):
        for mode, expected in [("adb", "ffs.adb"), ("sideload", "ffs.adb"),
                               ("fastboot", "ffs.fastboot")]:
            with self.subTest(mode=mode):
                usb = UsbInit(source)
                usb.set("sys.usb.config", "mtp,adb")
                usb.set("sys.usb.ffs.mtp.ready", "1")
                usb.set("sys.usb.ffs.ready", "1")
                self.assertEqual(usb.bound, {"ffs.adb", "ffs.mtp"})
                # TWRP clears MTP readiness before stopping its MTP server.
                usb.set("sys.usb.ffs.mtp.ready", "0")
                usb.set("sys.usb.config", "none")
                self.assertEqual(usb.links, {}, "inactive MTP function retained")
                self.assertFalse(usb.bound)
                self.assertNotIn("adbd", usb.running)
                usb.set("sys.usb.config", mode)
                usb.set("sys.usb.ffs.ready", "1")
                self.assertEqual(usb.bound, {expected})
                self.assertEqual(usb.props.get("sys.usb.state"), mode)

    def test_legacy_shutdown_stops_fastbootd(self):
        usb = UsbInit(source, configfs="0")
        usb.set("sys.usb.config", "fastboot")
        self.assertIn("fastbootd", usb.running)
        usb.set("sys.usb.config", "none")
        self.assertNotIn("fastbootd", usb.running)


if __name__ == "__main__":
    unittest.main(verbosity=2)
