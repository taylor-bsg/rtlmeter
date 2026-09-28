#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Import the pinned HammerBlade SPMD source closure; no builds or downloads."""

import argparse
import re
import subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--manycore", type=Path, required=True)
p.add_argument("--basejump", type=Path, required=True)
a = p.parse_args()
mc, bj = a.manycore.resolve(), a.basejump.resolve()
hf = mc / "imports/HardFloat"
root = Path(__file__).resolve().parents[2]
dst = root / "designs/HammerBlade"
pins = {
    "manycore": "0052ce8594864befae2b85d55193706c88b14584",
    "basejump": "fa07b1f180d0d313e15dc828249eea07b341852b",
    "hardfloat": "5b7d5fe2df7e297b5ba095b3eb8a9517dc2e9d88",
}
for name, repo in [("manycore", mc), ("basejump", bj), ("hardfloat", hf)]:
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    if head != pins[name]:
        raise SystemExit(f"{name}: expected {pins[name]}, found {head}")
    if subprocess.check_output(["git", "-C", str(repo), "diff", "HEAD", "--"], text=True):
        raise SystemExit(f"{name}: tracked modifications must be reviewed before importing")


def write(rel, data):
    out = dst / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(data)


def relpath(src):
    for base, label in [(hf, "hardfloat"), (mc, "manycore"), (bj, "basejump")]:
        if src.is_relative_to(base):
            return Path("src") / label / src.name
    raise ValueError(src)


variables = {"BSG_MANYCORE_DIR": str(mc), "BASEJUMP_STL_DIR": str(bj)}


def expand(s):
    for k, v in variables.items():
        s = s.replace("$(" + k + ")", v)
    return Path(s)


arch = (mc / "machines/arch_filelist.mk").read_text()
files = [
    expand(m.group(1)) for m in re.finditer(r"^(?:VHEADERS|VSOURCES)\s*\+=\s*(\S+)", arch, re.M)
]
sim_names = [
    "bsg_manycore_mem_cfg_pkg.sv",
    "bsg_manycore_network_cfg_pkg.sv",
    "bsg_nonsynth_clock_gen.sv",
    "bsg_nonsynth_reset_gen.sv",
    "bsg_cycle_counter.sv",
    "bsg_serial_in_parallel_out_full.sv",
    "bsg_round_robin_1_to_n.sv",
    "bsg_one_fifo.sv",
    "bsg_trace_replay.sv",
    "bsg_tag_trace_replay.sv",
    "bsg_tag_master.sv",
    "bsg_nonsynth_manycore_tag_master.sv",
    "bsg_nonsynth_manycore_io_complex.sv",
    "bsg_nonsynth_manycore_spmd_loader.sv",
    "bsg_nonsynth_manycore_monitor.sv",
    "bsg_nonsynth_wormhole_test_mem.sv",
    "bsg_nonsynth_manycore_testbench.sv",
    "spmd_testbench.sv",
]
sim = (mc / "machines/sim_filelist.mk").read_text()
for m in re.finditer(r"^(?:VHEADERS|VSOURCES)\s*\+=\s*(\S+)", sim, re.M):
    f = expand(m.group(1))
    if f.name in sim_names:
        files.append(f)
files = list(dict.fromkeys(files))
incdirs = [
    expand(m.group(1)) for m in re.finditer(r"^VINCLUDES\s*\+=\s*(\S+)", arch + "\n" + sim, re.M)
]
includes = {f for f in files if f.suffix == ".svh" or f.name == "bsg_defines.sv"}
sources = [f for f in files if f not in includes]
queue = list(files)
seen = set(queue)
while queue:
    f = queue.pop()
    for name in re.findall(r'^\s*\x60include\s+"([^"]+)"', f.read_text(), re.M):
        candidate = next((d / name for d in [f.parent] + incdirs if (d / name).is_file()), None)
        if candidate is None:
            raise SystemExit(f"Missing include {name} from {f}")
        includes.add(candidate)
        if candidate not in seen:
            queue.append(candidate)
            seen.add(candidate)
for f in seen:
    write(relpath(f), f.read_text())

# Keep the existing test-memory branch and hardware. Omit the unused DRAMSim3
# alternative and profiler binds from this standalone, dependency-free harness.
tbrel = "src/manycore/bsg_nonsynth_manycore_testbench.sv"
tb = (dst / tbrel).read_text()
start = tb.index("  else if (mem_cfg_lp[e_vcache_hbm2])")
end = tb.index("  // IO P tie off", start)
tb = (
    tb[:start]
    + """  else begin: unsupported_memory
    initial $fatal(1, "RTLmeter HammerBlade requires e_vcache_test_mem");
  end

"""
    + tb[end:]
)
start = tb.index("// NOTE: Verilator does not allow parameter-controlled module binds")
tb = tb[:start] + "endmodule\n\n\x60BSG_ABSTRACT_MODULE(bsg_nonsynth_manycore_testbench)\n"
write(tbrel, tb)

toprel = "src/manycore/spmd_testbench.sv"
top = (
    (dst / toprel)
    .read_text()
    .replace("endmodule", '\x60include "__rtlmeter_top_include.vh"\nendmodule')
)
write(toprel, top)


# Assert peripheral reset immediately, then retain the original delayed release
# after tag programming. A zero-initialized delay chain alone releases reset
# spuriously for its first three clocks under generated-main two-state simulation.
tbrel = "src/manycore/bsg_nonsynth_manycore_testbench.sv"
tb = (dst / tbrel).read_text()
tb = tb.replace(
    "  logic reset_r;",
    "  logic reset_r, reset_delayed;\n  assign reset_r = ~tag_done_lo | reset_delayed;",
)
tb = tb.replace(",.data_o(reset_r)", ",.data_o(reset_delayed)")
write(tbrel, tb)
toprel = "src/manycore/spmd_testbench.sv"
top = (dst / toprel).read_text()
top = top.replace(
    "  logic reset_r;",
    "  logic reset_r, reset_delayed;\n  assign reset_r = ~tag_done_lo | reset_delayed;",
)
top = top.replace(",.data_o(reset_r)", ",.data_o(reset_delayed)")
top = top.replace(
    "endmodule",
    '\n// Tagged hardware has no initialized state until serial reset completes.\ninitial begin\n  $assertoff;\n  wait (reset_r);\n  @(negedge reset_r);\n  $asserton;\n  $display("HammerBlade: tag reset complete; assertions enabled");\nend\n\n'
    + "endmodule",
)
write(toprel, top)

# The upstream defaults allocate 16M boot entries and read Linux /proc/uptime.
# The imported case needs fewer entries; keep an explicit capacity/bounds check.
loaderrel = "src/manycore/bsg_nonsynth_manycore_spmd_loader.sv"
loader = (dst / loaderrel).read_text().replace("max_nbf_p = 2**24", "max_nbf_p = 2**18")
loader = loader.replace("uptime_p=1", "uptime_p=0").replace("uptime_p = 1", "uptime_p = 0")
loader = loader.replace(
    'void\x27($value$plusargs("nbf_file=%s", nbf_file));',
    """if (!$value$plusargs("nbf_file=%s", nbf_file))
      $fatal(1, "Missing +nbf_file");""",
)
loader = loader.replace(
    "  logic loader_done_r, loader_done_n;",
    """  always @(posedge clk_i)
    if (!reset_i && !done_o && nbf_addr_r == max_nbf_p-1)
      $fatal(1, "NBF exceeds loader capacity or has no terminator");

  logic loader_done_r, loader_done_n;""",
)
write(loaderrel, loader)

monrel = "src/manycore/bsg_nonsynth_manycore_monitor.sv"
mon = (
    (dst / monrel)
    .read_text()
    .replace("uptime_p=1", "uptime_p=0")
    .replace("uptime_p = 1", "uptime_p = 0")
)
mon = mon.replace(
    'void\x27($value$plusargs("num_finish=%d", num_finish));',
    """if (!$value$plusargs("num_finish=%d", num_finish) || num_finish <= 0)
      $fatal(1, "Missing or invalid +num_finish");""",
)
mon = mon.replace(
    '$display("[INFO][MONITOR] BSG_TIMEOUT reached max_cycle = %d", max_cycle);\n        $finish;',
    '$fatal(1, "BSG_TIMEOUT reached max_cycle = %d", max_cycle);',
)
mon = mon.replace(
    "src_y_cord_i, src_x_cord_i, data_i, $time);\n            $finish;",
    'src_y_cord_i, src_x_cord_i, data_i, $time);\n            $fatal(1, "BSG_FAIL");',
)
write(monrel, mon)

# Generate the existing 1x1-pod reset ROM with the upstream generators.
scratch = root / "work/hammerblade-import"
scratch.mkdir(parents=True, exist_ok=True)
trace = subprocess.check_output(
    ["python3", "-B", str(mc / "testbenches/py/pod_trace_gen.py"), "1", "1"], text=True
)
(scratch / "pod_trace.tr").write_text(trace)
rom = subprocess.check_output(
    [
        "python3",
        "-B",
        str(bj / "bsg_mem/bsg_ascii_to_rom.py"),
        str(scratch / "pod_trace.tr"),
        "bsg_tag_boot_rom",
    ],
    text=True,
)
write(
    "src/generated/bsg_tag_boot_rom.v", rom.replace(str(scratch / "pod_trace.tr"), "pod_trace.tr")
)

for name, f in [
    ("LICENSE-manycore", mc / "LICENSE"),
    ("LICENSE-basejump", bj / "LICENSE"),
    ("LICENSE-HardFloat", hf / "COPYING.txt"),
]:
    write(name, f.read_text())
defines = {}
for line in (mc / "machines/pod_1x1/Makefile.machine.include").read_text().splitlines():
    if m := re.match(r"(BSG_MACHINE_\w+)\s*=\s*(\S+)", line):
        if m[1] not in ("BSG_MACHINE_DRAMSIM3_PKG", "BSG_MACHINE_HETERO_TYPE_VEC"):
            defines[m[1]] = m[2]
defines["HOST_MODULE_PATH"] = "spmd_testbench"
sources = list(dict.fromkeys(sources))
source_rels = [str(relpath(f)) for f in sources] + ["src/generated/bsg_tag_boot_rom.v"]
inc_rels = sorted(str(relpath(f)) for f in includes)
desc = """# Native 16x8 SPMD amoadd/barrier: seven-iteration smoke and 176-iteration long case.
# Machine: bsg_manycore machines/pod_1x1; this is not the historical HBM AES profile.
# Regeneration and local validation: docs/source/hammerblade.rst.
origin:
  - repository: https://github.com/bespoke-silicon-group/bsg_manycore
    revision: %s
    licenses: [LICENSE-manycore]
  - repository: https://github.com/bespoke-silicon-group/basejump_stl
    revision: %s
    licenses: [LICENSE-basejump]
  - repository: https://github.com/bsg-external/HardFloat
    revision: %s
    licenses: [LICENSE-HardFloat]
  - repository: local
    revision: local
    licenses: [../../LICENSE]
compile:
  verilogSourceFiles:
""" % (pins["manycore"], pins["basejump"], pins["hardfloat"])
desc += "".join("    - " + f + "\n" for f in source_rels)
desc += "  verilogIncludeFiles:\n" + "".join("    - " + f + "\n" for f in inc_rels)
desc += "  verilogDefines:\n" + "".join(f"    {k}: {v}\n" for k, v in sorted(defines.items()))
desc += """  topModule: spmd_testbench
  mainClock: spmd_testbench.core_clk
execute:
  common:
    postHook: tests/check.py
  tests:
    amoadd:
      files: [tests/amoadd.nbf]
      args:
        - +nbf_file=amoadd.nbf
        - +num_finish=1
        - +max_cycle=2000000
    amoadd_long:
      files: [tests/amoadd_long.nbf]
      args:
        - +nbf_file=amoadd_long.nbf
        - +num_finish=1
        - +max_cycle=2000000
"""
write("descriptor.yaml", desc)
write(
    "tests/check.py",
    """#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import re
from pathlib import Path

log = Path("_execute/stdout.log").read_text()
if re.search(r"BSG_FAIL|BSG_TIMEOUT|%Error|Assertion failed", log):
    raise SystemExit("HammerBlade reported failure")
if log.count("RECEIVED BSG_FINISH PACKET from all pods") != 1:
    raise SystemExit("Missing or duplicate completion")
packets = re.findall(r"RECEIVED a finish packet from tile y,x=\\s*(\\d+),\\s*(\\d+)", log)
if packets != [("8", "16")]:
    raise SystemExit("Expected exactly one finish from physical tile (16,8)")
print("PASS: HammerBlade 16x8 amoadd (all device checks passed)")
""",
)
(dst / "tests/check.py").chmod(0o755)
print(f"Imported {len(source_rels)} sources and {len(inc_rels)} headers to {dst}")
