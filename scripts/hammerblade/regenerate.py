#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rebuild only the amoadd device image in a fresh directory, using an existing SDK."""

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--manycore", type=Path, required=True)
p.add_argument("--basejump", type=Path, required=True)
p.add_argument("--riscv-bin", type=Path, required=True)
p.add_argument("--build-dir", type=Path, required=True)
p.add_argument("--make", default="make")
p.add_argument("--configuration", choices=["16x8", "2x1"], default="16x8")
p.add_argument("--output-file", type=Path, required=True, help="NBF destination")
a = p.parse_args()
mc, bj, rv, out = map(lambda v: v.resolve(), (a.manycore, a.basejump, a.riscv_bin, a.build_dir))
out.mkdir(parents=True, exist_ok=False)
root = Path(__file__).resolve().parents[2]
small = a.configuration == "2x1"
machine = root / "scripts/hammerblade/machines/2x1" if small else mc / "machines/pod_1x1"
tiles_x, tiles_y = (2, 1) if small else (16, 8)
origin_x, origin_y = (2, 2) if small else (16, 8)
pin = "0052ce8594864befae2b85d55193706c88b14584"
assert (
    subprocess.check_output(["git", "-C", str(mc), "rev-parse", "HEAD"], text=True).strip() == pin
)
src = mc / "software/spmd/bsg_barrier_amoadd_test"
original_source = (src / "main.c").read_text()
assert original_source.count("#define N 7") == 1
device_source = original_source.replace(
    "#define N 7",
    'volatile unsigned int rtlmeter_iterations __attribute__((section(".rtlmeter_iterations"), used)) = 0x48424954;',
)
device_source = device_source.replace(
    "  bsg_set_tile_x_y();",
    """  bsg_set_tile_x_y();
  const int N = (int)rtlmeter_iterations;
  if (N < 1 || N > 1000000) {
    bsg_fail();
    bsg_wait_while(1);
  }""",
)
(out / "main.c").write_text(device_source)
make = (src / "Makefile").read_text()
make = make.replace(
    "include ../Makefile.include", "include $(BSG_MANYCORE_DIR)/software/spmd/Makefile.include"
)
make = make.replace(
    "include ../../mk/Makefile.tail_rules",
    "include $(BSG_MANYCORE_DIR)/software/mk/Makefile.tail_rules",
)
(out / "Makefile").write_text(make)
env = os.environ.copy()
env.update(
    BSG_MANYCORE_DIR=str(mc),
    BASEJUMP_STL_DIR=str(bj),
    BSG_IP_CORES_DIR=str(bj),
    RISCV_BIN_DIR=str(rv),
    PYTHONDONTWRITEBYTECODE="1",
)
cmd = [
    a.make,
    "-j2",
    "main.nbf",
    "BSG_PLATFORM=verilator",
    "IGNORE_CADENV=1",
    "BSG_MACHINE_PATH=" + str(machine),
    "SPMD_COMPILER=gcc",
    "PYTHON=python3",
    "RISCV_LINK_EXTRA_OPTS=-Wl,-Map=main.map",
]
if small:
    # The upstream test Makefile hard-codes a 16x8 tile group.
    cmd += [f"bsg_tiles_X={tiles_x}", f"bsg_tiles_Y={tiles_y}"]
# Generate the pinned linker script, then reserve one word after the interrupt
# table. The section remains part of .dmem, which the upstream NBF tool exports.
link_cmd = cmd.copy()
link_cmd[2] = str(out / "bsg_link.ld")
with (out / "linker.log").open("w") as log:
    subprocess.run(link_cmd, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
linker = (out / "bsg_link.ld").read_text()
linker = re.sub(r" Generated at .*", " Generated from the pinned manycore linker template", linker)
needle = "  *(.dmem.interrupt)"
assert linker.count(needle) == 1
linker = linker.replace(
    needle,
    needle
    + """
  ASSERT(. <= 8, "Interrupt table overlaps iteration word");
  . = 8;
  KEEP(*(.rtlmeter_iterations))
  ASSERT(. == 12, "Iteration word must occupy exactly four bytes");
  ASSERT(rtlmeter_iterations == 8, "Iteration word address changed");""",
)
(out / "bsg_link.ld").write_text(linker)
with (out / "build.log").open("w") as log:
    result = subprocess.run(cmd, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
if result.returncode:
    print((out / "build.log").read_text()[-10000:])
    raise SystemExit(result.returncode)
symbols = subprocess.check_output(
    [str(rv / "riscv32-unknown-elf-dramfs-nm"), "-n", str(out / "main.riscv")], text=True
)
assert "00000008 D rtlmeter_iterations" in symbols
(out / "symbols.txt").write_text(symbols)
nbf = (out / "main.nbf").read_text()
rows = nbf.splitlines()
cache_row_rewrites = 0
if small:
    # The pinned NBF generator uses origin_y + tile_count for the south
    # cache. Singleton RTL reserves one Y coordinate bit, so that row is
    # origin_y + 2, not origin_y + 1. Y=3 contains no compute tile here.
    corrected = []
    for row in rows:
        fields = row.split("_")
        if int(fields[0], 16) in (2, 3) and int(fields[1], 16) == 3:
            fields[1] = "04"
            cache_row_rewrites += 1
        corrected.append("_".join(fields))
    assert cache_row_rewrites > 0
    rows = corrected
    nbf = "\n".join(rows) + "\n"
    (out / "main.raw.nbf").write_text((out / "main.nbf").read_text())
    (out / "main.nbf").write_text(nbf)
    allowed = {(2, 1), (3, 1), (2, 2), (3, 2), (2, 4), (3, 4), (255, 255)}
    assert all(tuple(int(v, 16) for v in row.split("_")[:2]) in allowed for row in rows)
assert rows[-1] == "ff_ff_ffffffff_ffffffff"
assert len(rows) < 2**18
# Freeze CSR deassertions must release exactly the selected physical tile group.
release = {
    (int(v[0], 16), int(v[1], 16))
    for r in rows
    if len(v := r.split("_")) == 4 and v[2] == "00008000" and v[3] == "00000000"
}
assert release == {
    (x, y) for x in range(origin_x, origin_x + tiles_x) for y in range(origin_y, origin_y + tiles_y)
}, release
patches = [
    r.split("_") for r in rows if r.split("_")[2] == "00000002" and r.split("_")[3] == "48424954"
]
assert len(patches) == tiles_x * tiles_y
assert {(int(r[0], 16), int(r[1], 16)) for r in patches} == release
resource = a.output_file.resolve()
resource.parent.mkdir(parents=True, exist_ok=True)
resource.write_text(nbf)
record = {
    "manycore": pin,
    "iterations": "runtime +iterations (1..1000000)",
    "iteration_byte_address": 8,
    "iteration_marker": "48424954",
    "linker_command": link_cmd,
    "configuration": a.configuration,
    "physical_tiles": [tiles_x, tiles_y],
    "origin": [origin_x, origin_y],
    "south_cache_row_rewrites": cache_row_rewrites,
    "adaptation": "Runtime loop bound in linker-reserved per-tile DMEM word; singleton south-cache NBF correction for 2x1",
    "original_source_sha256": hashlib.sha256(original_source.encode()).hexdigest(),
    "command": cmd,
    "nbf_records": len(rows),
    "sha256": {
        name: hashlib.sha256((out / name).read_bytes()).hexdigest()
        for name in ["main.c", "bsg_link.ld", "main.riscv", "main.nbf"]
    },
    "gcc": subprocess.check_output(
        [str(rv / "riscv32-unknown-elf-dramfs-gcc"), "--version"], text=True
    ),
}
(out / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
