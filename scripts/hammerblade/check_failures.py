#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise actual device-failure and watchdog paths using an existing simulator."""

import argparse
import json
import subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--simulator", type=Path, required=True)
p.add_argument("--out", type=Path, required=True)
a = p.parse_args()
sim = a.simulator.resolve()
root = Path(__file__).resolve().parents[2]
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
good = (root / "designs/HammerBlade/tests/amoadd.nbf").read_text()
# main.map: data starts at EVA 0x81000000. The pinned 16x8 iPoly mapping
# sends data[0] to north cache (22,7), word EPA 0x20000.
record = "16_07_00020000_00000000"
assert good.splitlines().count(record) == 1
bad = good.replace(record, "16_07_00020000_00000001")
rows = []
for name, image, cycles, marker in [
    ("device-failure", bad, 2000000, "BSG_FAIL"),
    ("watchdog", good, 10, "BSG_TIMEOUT"),
]:
    case = out / name
    (case / "_execute").mkdir(parents=True)
    (case / "input.nbf").write_text(image)
    cmd = [
        str(sim),
        "+verilator+quiet",
        "+nbf_file=input.nbf",
        "+num_finish=1",
        f"+max_cycle={cycles}",
    ]
    with (case / "_execute/stdout.log").open("w") as log:
        run = subprocess.run(cmd, cwd=case, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    log = (case / "_execute/stdout.log").read_text()
    assert run.returncode != 0, (name, "simulator unexpectedly succeeded")
    assert marker in log, (name, "wrong failure", log[-1500:])
    check = subprocess.run(
        ["python3", str(root / "designs/HammerBlade/tests/check.py")],
        cwd=case,
        capture_output=True,
        text=True,
    )
    assert check.returncode != 0, (name, "checker unexpectedly succeeded")
    rows.append(
        dict(
            case=name,
            simulator_returncode=run.returncode,
            expected_marker=marker,
            checker_returncode=check.returncode,
        )
    )
(out / "results.json").write_text(json.dumps(rows, indent=2) + "\n")
print(json.dumps(rows, indent=2))
