#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rebuild only the amoadd device image in a fresh directory, using an existing SDK."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--manycore", type=Path, required=True)
p.add_argument("--basejump", type=Path, required=True)
p.add_argument("--riscv-bin", type=Path, required=True)
p.add_argument("--build-dir", type=Path, required=True)
p.add_argument("--make", default="make")
p.add_argument("--iterations", type=int, default=7, help="Device amoadd loop count")
p.add_argument("--output-file", type=Path, help="NBF destination; required for non-smoke builds")
a = p.parse_args()
if not 1 <= a.iterations <= 1000000:
    p.error("--iterations must be between 1 and 1000000")
if a.iterations != 7 and a.output_file is None:
    p.error("Specify --output-file to preserve the seven-iteration smoke image")
mc, bj, rv, out = map(lambda v: v.resolve(), (a.manycore, a.basejump, a.riscv_bin, a.build_dir))
out.mkdir(parents=True, exist_ok=False)
pin = "0052ce8594864befae2b85d55193706c88b14584"
assert (
    subprocess.check_output(["git", "-C", str(mc), "rev-parse", "HEAD"], text=True).strip() == pin
)
src = mc / "software/spmd/bsg_barrier_amoadd_test"
original_source = (src / "main.c").read_text()
assert original_source.count("#define N 7") == 1
(out / "main.c").write_text(original_source.replace("#define N 7", f"#define N {a.iterations}"))
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
    "BSG_MACHINE_PATH=" + str(mc / "machines/pod_1x1"),
    "SPMD_COMPILER=gcc",
    "PYTHON=python3",
    "RISCV_LINK_EXTRA_OPTS=-Wl,-Map=main.map",
]
with (out / "build.log").open("w") as log:
    result = subprocess.run(cmd, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
if result.returncode:
    print((out / "build.log").read_text()[-10000:])
    raise SystemExit(result.returncode)
nbf = (out / "main.nbf").read_text()
rows = nbf.splitlines()
assert rows[-1] == "ff_ff_ffffffff_ffffffff"
assert len(rows) < 2**18
# Freeze CSR deassertions must release the complete physical 16x8 pod.
release = {
    (int(v[0], 16), int(v[1], 16))
    for r in rows
    if len(v := r.split("_")) == 4 and v[2] == "00008000" and v[3] == "00000000"
}
assert release == {(x, y) for x in range(16, 32) for y in range(8, 16)}, release
root = Path(__file__).resolve().parents[2]
resource = (
    a.output_file.resolve() if a.output_file else root / "designs/HammerBlade/tests/amoadd.nbf"
)
resource.parent.mkdir(parents=True, exist_ok=True)
resource.write_text(nbf)
record = {
    "manycore": pin,
    "iterations": a.iterations,
    "adaptation": "Only #define N changes when iterations differs from seven",
    "original_source_sha256": hashlib.sha256(original_source.encode()).hexdigest(),
    "command": cmd,
    "nbf_records": len(rows),
    "sha256": {
        name: hashlib.sha256((out / name).read_bytes()).hexdigest()
        for name in ["main.c", "main.riscv", "main.nbf"]
    },
    "gcc": subprocess.check_output(
        [str(rv / "riscv32-unknown-elf-dramfs-gcc"), "--version"], text=True
    ),
}
(out / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
