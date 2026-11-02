#!/usr/bin/env python3
"""Check that the manual HAL test refuses unsafe startup conditions."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

tree = Path(__file__).resolve().parents[2]
source = (tree / "recovery/root/system/bin/a05s-crypto-test").read_text()
fake_tool = r'''#!/usr/bin/env python3
import json, os
from pathlib import Path
import sys
root = Path(os.environ["A05S_GUARD_TEST_DIR"])
tool = Path(sys.argv[0]).name
args = sys.argv[1:]
props = json.loads((root / "props.json").read_text())
with (root / "calls.jsonl").open("a") as output:
    output.write(json.dumps([tool, *args]) + "\n")
if tool == "getprop":
    print(props.get(args[0], ""))
elif tool in ["resetprop", "setprop"]:
    if not (tool == "resetprop" and os.environ["A05S_GUARD_CASE"] == "bad-properties"):
        props[args[0]] = args[1]
        (root / "props.json").write_text(json.dumps(props))
elif tool == "awk":
    # Model an existing writable mount, or no EFS mount at all.
    if "ro(,|$)" in args[0]:
        sys.exit(1)
    sys.exit(0 if os.environ["A05S_GUARD_CASE"] == "writable-efs" else 1)
elif tool not in ["mkdir", "mount"]:
    raise SystemExit("Unexpected test command: " + tool)
'''

for case in ["outside-recovery", "wrong-firmware", "bad-properties", "writable-efs", "allowed"]:
    with tempfile.TemporaryDirectory(prefix="a05s-crypto-guard-") as directory:
        root = Path(directory)
        tools = root / "bin"
        tools.mkdir()
        for name in ["getprop", "setprop", "resetprop", "awk", "mkdir", "mount"]:
            tool = tools / name
            tool.write_text(fake_tool)
            tool.chmod(0o755)
        props = {
            "ro.twrp.boot": "0" if case == "outside-recovery" else "1",
            "ro.bootloader": "other-firmware" if case == "wrong-firmware" else "A057MUBSFDZE2",
            "ro.build.version.security_patch": "2099-12-31",
        }
        (root / "props.json").write_text(json.dumps(props))
        script = root / "crypto-test.sh"
        script.write_text(source.replace(
            "exec >> /tmp/a05s-crypto-test.log 2>&1",
            "exec >> " + shlex.quote(str(root / "test.log")) + " 2>&1",
        ))
        env = dict(os.environ, PATH=str(tools) + os.pathsep + os.environ["PATH"],
                   A05S_GUARD_TEST_DIR=str(root), A05S_GUARD_CASE=case)
        result = subprocess.run(["sh", str(script)], env=env, capture_output=True, text=True)
        calls = [json.loads(line) for line in (root / "calls.jsonl").read_text().splitlines()]
        final_props = json.loads((root / "props.json").read_text())
        ready = final_props.get("a05s.crypto.test.ready") == "1"
        mounts = [call for call in calls if call[0] == "mount"]
        if case == "allowed":
            assert result.returncode == 0 and ready, (case, result.returncode, final_props)
            assert mounts == [["mount", "-t", "ext4", "-o", "ro,noload",
                               "/dev/block/bootdevice/by-name/efs", "/mnt/vendor/efs"]], mounts
        else:
            assert result.returncode != 0 and not ready, (case, result.returncode, final_props)
            assert not mounts, (case, mounts)
        print("PASS:", case)
