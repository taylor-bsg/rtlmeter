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
p.add_argument("--configuration", choices=["16x8", "2x1"], default="16x8")
a = p.parse_args()
sim = a.simulator.resolve()
root = Path(__file__).resolve().parents[2]
out = a.out.resolve()
out.mkdir(parents=True, exist_ok=False)
resource = "tests/2x1/amoadd.nbf" if a.configuration == "2x1" else "tests/16x8/amoadd.nbf"
good = (root / "designs/HammerBlade" / resource).read_text()
# main.map: data starts at EVA 0x81000000. The pinned 16x8 iPoly mapping
# sends data[0] to north cache (22,7), word EPA 0x20000.
# The 2x1 non-iPoly mapping uses north cache (2,1), word EPA 0x100000.
record = "02_01_00100000_00000000" if a.configuration == "2x1" else "16_07_00020000_00000000"
assert good.splitlines().count(record) == 1
bad = good.replace(record, record[:-8] + "00000001")
# Preserve each malformed image and log, including failures before time advances.
lines = good.splitlines()
marker = next(r for r in lines if r.endswith("_00000002_48424954"))
missing = "\n".join(r for r in lines if r != marker) + "\n"
duplicate = good.replace(marker, marker + "\n" + marker)
wrong_marker = good.replace(marker, marker[:-8] + "00000001")
without_fence = good.replace("ff_ff_00000000_00000000\n", "")
cases = [
    ("device-failure", bad, ["+iterations=7"], 2000000, "BSG_FAIL"),
    ("watchdog", good, ["+iterations=7"], 10, "BSG_TIMEOUT"),
    ("missing-count", good, [], 2000000, "Missing +iterations"),
    ("zero-count", good, ["+iterations=0"], 2000000, "Invalid +iterations"),
    ("negative-count", good, ["+iterations=-1"], 2000000, "Invalid +iterations"),
    ("large-count", good, ["+iterations=1000001"], 2000000, "Invalid +iterations"),
    ("overflow-count", good, ["+iterations=4294967297"], 2000000, "Invalid +iterations"),
    ("malformed-count", good, ["+iterations=7x"], 2000000, "Invalid +iterations"),
    ("missing-word", missing, ["+iterations=7"], 2000000, "Invalid NBF"),
    ("duplicate-word", duplicate, ["+iterations=7"], 2000000, "Invalid NBF"),
    ("wrong-marker", wrong_marker, ["+iterations=7"], 2000000, "Invalid NBF"),
    ("missing-fence", without_fence, ["+iterations=7"], 2000000, "Invalid NBF"),
    (
        "missing-terminator",
        good.replace("ff_ff_ffffffff_ffffffff\n", ""),
        ["+iterations=7"],
        2000000,
        "Invalid NBF",
    ),
]
rows = []
for name, image, args, cycles, marker in cases:
    case = out / name
    (case / "_execute").mkdir(parents=True)
    (case / "input.nbf").write_text(image)
    cmd = [
        str(sim),
        "+verilator+quiet",
        "+nbf_file=input.nbf",
        "+num_finish=1",
        f"+max_cycle={cycles}",
        *args,
    ]
    (case / "command.json").write_text(json.dumps(cmd, indent=2) + "\n")
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
