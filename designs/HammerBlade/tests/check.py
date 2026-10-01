#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import re
from pathlib import Path

log = Path("_execute/stdout.log").read_text()
if re.search(r"BSG_FAIL|BSG_TIMEOUT|%Error|Assertion failed", log):
    raise SystemExit("HammerBlade reported failure")
if log.count("RECEIVED BSG_FINISH PACKET from all pods") != 1:
    raise SystemExit("Missing or duplicate completion")
packets = re.findall(r"RECEIVED a finish packet from tile y,x=\s*(\d+),\s*(\d+)", log)
geometry = []
for axis in ("X", "Y"):
    values = re.findall(r"BSG_MACHINE_GLOBAL_" + axis + r"\s*=\s*(\d+)", log)
    if len(values) != 1:
        raise SystemExit("Missing or duplicate physical geometry")
    geometry.append(int(values[0]))
finish = {(16, 8): ("8", "16"), (2, 1): ("2", "2")}.get(tuple(geometry))
if finish is None or packets != [finish]:
    raise SystemExit("Expected exactly one finish from this machine's origin tile")
print(f"PASS: HammerBlade {geometry[0]}x{geometry[1]} amoadd (all device checks passed)")
