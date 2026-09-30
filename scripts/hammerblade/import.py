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
start = loader.index("  string nbf_file;")
end = loader.index("\n  always @(posedge clk_i)", start)
loader = (
    loader[:start] + (root / "scripts/hammerblade/loader_initial.sv").read_text() + loader[end:]
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

# Size the backing array from the machine capacity. At the original 16x8
# setting this is exactly the upstream 2 GiB allocation.
tbrel = "src/manycore/bsg_nonsynth_manycore_testbench.sv"
tb = (dst / tbrel).read_text()
old = "(2**30)*num_pods_x_p/wh_ruche_factor_p/2"
assert tb.count(old) == 1
tb = tb.replace(old, "(64'(bsg_dram_size_p)*4)*num_pods_x_p/wh_ruche_factor_p/4")
write(tbrel, tb)

# A dedicated single-cache memory port has no cache-selector address bits.
# SAFE_CLOG2(1) is one, so the upstream concatenation otherwise selects a
# nonexistent bank and aliases the upper half of that port's memory.
memrel = "src/manycore/bsg_nonsynth_wormhole_test_mem.sv"
mem = (dst / memrel).read_text()
old = "  if (no_concentration_p) begin"
assert mem.count(old) == 1
mem = mem.replace(
    old,
    """  if (no_concentration_p && num_vcaches_p == 1) begin
    assign mem_addr = {
      addr_r[block_offset_width_lp+:mem_addr_width_lp-count_width_lp],
      count_lo
    };
  end
  else if (no_concentration_p) begin""",
)
write(memrel, mem)

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
# Use the pinned small-mesh profile, with a singleton row and 64 MiB.
# Keep the reserved two-row coordinate span: origin (2,2), south cache Y=4.
small_machine = (mc / "machines/pod_1x1_2X2Y/Makefile.machine.include").read_text()
small_values = {
    "BSG_MACHINE_GLOBAL_Y": "1",
    "BSG_MACHINE_DRAM_SIZE_WORDS": "16777216",
    "BSG_MACHINE_DRAM_BANK_SIZE_WORDS": "4194304",
}
for key, value in small_values.items():
    small_machine, count = re.subn(
        r"(?m)^(" + key + r"\s*=\s*)\S+", lambda m: m[1] + value, small_machine
    )
    assert count == 1, key
profile = root / "scripts/hammerblade/machines/2x1/Makefile.machine.include"
profile.parent.mkdir(parents=True, exist_ok=True)
profile.write_text(small_machine)
small_all = {}
for line in small_machine.splitlines():
    if m := re.match(r"(BSG_MACHINE_\w+)\s*=\s*(\S+)", line):
        if m[1] in defines:
            small_all[m[1]] = m[2]
small_all["HOST_MODULE_PATH"] = "spmd_testbench"
common_defines = {k: v for k, v in defines.items() if small_all[k] == v}
large_defines = {k: v for k, v in defines.items() if k not in common_defines}
small_defines = {k: v for k, v in small_all.items() if k not in common_defines}

sources = list(dict.fromkeys(sources))
source_rels = [str(relpath(f)) for f in sources] + ["src/generated/bsg_tag_boot_rom.v"]
inc_rels = sorted(str(relpath(f)) for f in includes)
# Trim only files outside the complete textual dependency closure of the top.
# Whole files and all conditional branches remain intact.
texts = {}
for rel in source_rels + inc_rels:
    texts[rel] = re.sub(r"/\*.*?\*/|//[^\n]*", "", (dst / rel).read_text(), flags=re.S)
symbols = {}
for rel, text in texts.items():
    for match in re.finditer(r"\b(?:module|package)\s+(\w+)", text):
        symbols[match[1]] = rel
by_name = {Path(rel).name: rel for rel in texts}
pending = ["src/manycore/spmd_testbench.sv"]
reachable = set()
while pending:
    rel = pending.pop()
    if rel in reachable:
        continue
    reachable.add(rel)
    pending.extend(
        symbols[word] for word in set(re.findall(r"\b\w+\b", texts[rel])) if word in symbols
    )
    pending.extend(
        by_name[name]
        for name in re.findall(r'\x60include\s+"([^"]+)"', texts[rel])
        if name in by_name
    )
removed = sorted(set(texts) - reachable)
for rel in removed:
    (dst / rel).unlink()
source_rels = [rel for rel in source_rels if rel in reachable]
inc_rels = [rel for rel in inc_rels if rel in reachable]
(scratch / "removed-sources.txt").write_text("\n".join(removed) + "\n")
recipe_revision = subprocess.check_output(
    ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
).strip()
desc = """# HammerBlade self-checking atomic-add/barrier SPMD benchmark.
# 16x8: 128 cores, ruche network, iPoly, 32 x 8 KiB caches, 2 GiB test memory.
# 2x1: two cores, mesh, no iPoly, 4 x 8 KiB caches, 64 MiB test memory.
# Both use 4 KiB DMEM and 4 KiB instruction cache per core.
# hello runs one iteration; amoadd uses the Linux-calibrated workload length.
# One NBF image per geometry: +iterations patches a linker-reserved DMEM word
# on every tile before unfreeze. Set counts in args; the first duplicate plusarg
# wins in Verilator. +max_cycle bounds execution independently of iterations.
# Native generated main/--timing; no SDK, DPI, host runtime, or DRAMSim3 at run time.
# Harness changes: reset ordering, clock reporting, bounded NBF loading/patching,
# fatal failures/timeouts, configured memory capacity, and singleton bank addressing.
# Hardware RTL is unchanged; unused sources and profiler/DRAMSim3 branches are omitted.
# Pinned import, device source/linker adaptation, SDK requirements, and regeneration:
# https://github.com/taylor-bsg/rtlmeter/blob/RECIPE_REVISION/docs/source/hammerblade.rst#runtime-iteration-maintenance
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
desc += "  verilogDefines:\n" + "".join(
    f"    {k}: {v}\n" for k, v in sorted(common_defines.items())
)
desc += """  topModule: spmd_testbench
  mainClock: spmd_testbench.core_clk
execute:
  common:
    postHook: tests/check.py
configurations:
  16x8:
    compile:
      verilogDefines:
"""
desc += "".join(f"        {k}: {v}\n" for k, v in sorted(large_defines.items()))
desc += """    execute:
      common:
        files: [tests/16x8/amoadd.nbf]
      tests:
        hello:
          args: [+nbf_file=amoadd.nbf, +num_finish=1, +iterations=1, +max_cycle=2000000]
          tags: [sanity]
        amoadd:
          args: [+nbf_file=amoadd.nbf, +num_finish=1, +iterations=176, +max_cycle=2000000]
          tags: [standard]
  2x1:
    compile:
      verilogDefines:
"""
desc += "".join(f"        {k}: {v}\n" for k, v in sorted(small_defines.items()))
desc += """    execute:
      common:
        files: [tests/2x1/amoadd.nbf]
      tests:
        hello:
          args: [+nbf_file=amoadd.nbf, +num_finish=1, +iterations=1, +max_cycle=2000000]
          tags: [sanity]
        amoadd:
          args: [+nbf_file=amoadd.nbf, +num_finish=1, +iterations=60000, +max_cycle=100000000]
          tags: [standard]
"""
desc = desc.replace("RECIPE_REVISION", recipe_revision)
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
geometry = []
for axis in ("X", "Y"):
    values = re.findall(r"BSG_MACHINE_GLOBAL_" + axis + r"\\s*=\\s*(\\d+)", log)
    if len(values) != 1:
        raise SystemExit("Missing or duplicate physical geometry")
    geometry.append(int(values[0]))
finish = {(16, 8): ("8", "16"), (2, 1): ("2", "2")}.get(tuple(geometry))
if finish is None or packets != [finish]:
    raise SystemExit("Expected exactly one finish from this machine's origin tile")
print(f"PASS: HammerBlade {geometry[0]}x{geometry[1]} amoadd (all device checks passed)")
""",
)
(dst / "tests/check.py").chmod(0o755)
for geometry in ("16x8", "2x1"):
    (dst / f"tests/{geometry}/amoadd_long.nbf").unlink(missing_ok=True)
print(f"Imported {len(source_rels)} sources and {len(inc_rels)} headers to {dst}")
