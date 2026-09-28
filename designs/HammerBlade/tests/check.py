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
if packets != [("8", "16")]:
    raise SystemExit("Expected exactly one finish from physical tile (16,8)")
print("PASS: HammerBlade 16x8 amoadd (all device checks passed)")
