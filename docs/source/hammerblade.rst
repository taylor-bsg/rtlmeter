HammerBlade SPMD benchmarks
================================

Runtime iteration maintenance
-----------------------------

This section describes the review revision of upstream PR #48. The sections
below retain the earlier fixed-image validation, including the Linux adjustment
of the 2x1 benchmark from 180,000 to 60,000 iterations. Their case names and cycle
counts describe those preserved revisions, not the runtime-adjustable images.

The configurations are now ``16x8`` and ``2x1``. Each has ``hello`` (one iteration)
and ``amoadd`` (176 or 60,000 iterations, respectively). Both tests in a geometry
share one NBF image. Change the descriptor's ``+iterations=N`` argument to select
another count without rebuilding the device image or simulator. Valid counts
are 1 through 1,000,000. The simulator uses the first matching plusarg, so an
extra duplicate passed with ``--executeArgs`` does not replace the descriptor
value. ``+max_cycle`` is an independent watchdog and must allow the chosen work.

The device source replaces the constant loop bound with a single volatile load
before the loop. The linker reserves byte address 8, immediately after the two
interrupt words, in each tile's local memory. Linker assertions and the ELF symbol
table verify that placement. The checked-in image holds marker 0x48424954 there.
The loader checks every tile's marker, patches the count in its NBF buffer, and
requires a credit fence before the complete tile-release sequence. The existing
network loader delivers the patched words; no processor or memory-model RTL is
changed by this revision. Startup also rejects an unpatched or out-of-range
device count.

The importer follows module/package references and includes from spmd_testbench,
retaining whole files and all parameter-controlled branches. It removes 29
unreachable files from the pinned source closure, leaving 165 source units and
10 headers. It records the removed list in work/hammerblade-import/.
The SDK remains a maintainer-only dependency.

To reproduce from clean pinned manycore/BaseJump checkouts and an existing
HammerBlade GCC 9.2.0 SDK (GNU Make is called gmake on the reference Mac)::

    python3 scripts/hammerblade/import.py --manycore "$MC" --basejump "$BJ"
    python3 scripts/hammerblade/regenerate.py \
        --manycore "$MC" --basejump "$BJ" --riscv-bin "$RISCV_BIN" --make gmake \
        --configuration 2x1 --build-dir work-runtime-device-2x1 \
        --output-file designs/HammerBlade/tests/2x1/amoadd.nbf
    python3 scripts/hammerblade/regenerate.py \
        --manycore "$MC" --basejump "$BJ" --riscv-bin "$RISCV_BIN" --make gmake \
        --configuration 16x8 --build-dir work-runtime-device-16x8 \
        --output-file designs/HammerBlade/tests/16x8/amoadd.nbf

Each build directory must be new. It retains the adapted C and linker script,
ELF and symbol table, NBF image, compiler identity, command lines, link map, and
hash manifest. Import records the maintenance revision in the descriptor's recipe
link. Run the failure checks against a matching compiled model::

    python3 scripts/hammerblade/check_failures.py --configuration 2x1 \
        --simulator "$SMALL_SIMULATOR" --out work-runtime-negative-2x1

Historical fixed-image measurements below remain available for comparison.

Runtime validation (2026-09-30)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The reviewed source closure and runtime images passed eight fresh stock
Verilator 5.052 builds and 32 executions on the reference Apple M5 Max:
both configurations, hello/amoadd, 1/2/4/8 workers, twice per case. Every build
used --assert, flat compilation, and the default generated-C++ flags, with no
PGO or experimental patch. Compilation and simulations ran serially.
The release checkout was clean at ea338be98e1e838d3518809ce8899f85a009963c.

The unchanged Linux-selected counts remain 176 for 16x8 and 60,000 for 2x1.
They were not recalibrated on the Mac. All repeats and worker counts agreed:
hello/amoadd completed in 36,402/477,402 clocks for 16x8 and
1,182/7,801,052 clocks for 2x1. These include reset and loading. Earlier clock
counts below describe different device images and are not equivalence targets.

.. list-table:: Local simulation wall times, including initialization (seconds)
   :header-rows: 1

   * - Geometry
     - Workers
     - hello range
     - amoadd range
   * - 2x1
     - 1
     - 0.26-0.36
     - 20.62-20.75
   * - 2x1
     - 2
     - 0.25-0.35
     - 28.79-29.25
   * - 2x1
     - 4
     - 0.24-0.33
     - 46.97-47.27
   * - 2x1
     - 8
     - 0.27-0.36
     - 125.81-126.22
   * - 16x8
     - 1
     - 7.31-7.38
     - 66.70-68.42
   * - 16x8
     - 2
     - 7.67-7.78
     - 75.19-76.05
   * - 16x8
     - 4
     - 5.06-5.18
     - 42.64-43.60
   * - 16x8
     - 8
     - 6.56-6.57
     - 59.42-60.64

A seven-iteration 2x1 run used the identical image/model and passed at 1,962
clocks. A native CLI duplicate-argument check confirmed that the descriptor's
first +iterations value wins, as documented above.

Thirteen negative checks passed for each geometry: device failure, watchdog,
missing/zero/negative/oversized/overflowing/malformed counts, missing or duplicate
iteration words, a wrong marker, a missing fence, and a missing terminator.
Each returned nonzero and was rejected by the post-hook.

Two fresh regenerations per geometry produced identical adapted C, normalized
linker scripts, ELF files, and NBF images. The images also match those used in
all 32 matrix executions. Import reproduced all 182 design files byte-for-byte.
Physical defines are unchanged from the Linux-tested PR revision cccbdd93;
all 174 retained source/header files except the loader are byte-identical to it.

New-revision Linux coverage is provided by the upstream PR CI after publication;
the historical Linux matrix below remains separately identified.

Historical fixed-image integration
----------------------------------

HammerBlade:default:amoadd runs the upstream software/spmd/bsg_barrier_amoadd_test
without changing its device source. All 128 tiles perform seven iterations
of atomic increments, participant barriers, and neighbor-value checks.
Tile (0,0) reports success only after the final collective barrier;
its physical coordinates are (16,8).

The original amoadd case is an integration/sanity workload.
HammerBlade:default:amoadd_long changes only the device loop bound to 176,
retaining all 128 participants, atomic updates, barriers, and per-iteration
neighbor checks. The reference Apple M5 Max runs took roughly one minute
with eight simulator workers. Wall time depends on the host and worker
count; the iteration count is fixed so worker comparisons run identical work.
AES remains a separate application-workload follow-up.

Device images are grouped by physical geometry under
designs/HammerBlade/tests/16x8 and designs/HammerBlade/tests/2x1.
The shared checker remains at designs/HammerBlade/tests/check.py, and
HammerBlade:default:* continues to select the 16x8 configuration.

Low-memory 2x1 configuration
----------------------------

HammerBlade:2x1:amoadd and HammerBlade:2x1:amoadd_long instantiate two
physical cores, with matching two-participant device programs. The default
configuration remains the 16x8 benchmark. The small configuration is useful
for inexpensive integration checks; its traffic and timing are different
from the physical 128-core configuration.

The machine profile in scripts/hammerblade/machines/2x1 is derived from the
pinned manycore machines/pod_1x1_2X2Y profile. It selects one compute row and
64 MiB of backing memory (four 16 MiB banks), with a mesh network, iPoly off,
and four 8 KiB cache banks. DMEM and instruction-cache sizes remain 4 KiB
per core. Physical core coordinates are (2,2) and (3,2). Singleton rows
reserve a Y coordinate bit, so the south cache row is Y=4, not Y=3.

Example commands after normal RTLmeter setup::

    ./rtlmeter run --cases 'HammerBlade:2x1:*' \
        --compileArgs='--threads 1 --assert' --nExecute 2 --workRoot work-hb-2x1
    ./rtlmeter run --cases 'HammerBlade:2x1:*' \
        --compileArgs='--threads 2 --assert' --nExecute 2 --workRoot work-hb-2x1-t2

The smoke resource retains seven iterations and completes in 1,921 clocks.
The 2x1 amoadd_long resource uses 60,000 iterations and completes in
7,801,013 clocks. It was reduced from 180,000 after Linux qualification
to shorten validation runs; all worker counts use the same image.
Only the two loop-bound immediate instructions changed; atomic operations,
barriers and per-iteration checks are unchanged.

The earlier 180,000-iteration image was calibrated on macOS after a
176-iteration trial took less than half a second. With stock Verilator
5.052 and assertions, both worker settings passed twice (a native RTLmeter
execution and a host-counter replay), each at
23,401,013 clocks. On the local Apple M5 Max, one-worker runs took
61.42 and 61.72 seconds; two-worker runs took 83.47 and 84.17 seconds.
The counter replays used about 74-75 MB peak RSS and retired 1.322 trillion
and 2.337 trillion host instructions, respectively, measured using macOS
/usr/bin/time -l. These are host CPU instructions, not device instructions.
These timings and counters describe the earlier 180,000-iteration image.
Its one-minute calibration was specific to that host, not a portable target.
Verilation took 2.39 seconds and about 574 MB peak RSS; C++ compilation took
1.79 seconds.
The original 16x8 simulations used about 2.1 GB peak RSS and Verilation
about 10.8 GB.

The testbench now derives its backing allocation from the configured
capacity; the default setting still allocates exactly 2 GiB. The existing
memory model also omits the cache-selector bit for a dedicated single-cache
port. SAFE_CLOG2(1) otherwise reserves a nonexistent bank and aliases half
of the address space. A separate eviction probe verified distinct low/high
addresses across all four banks, including near the end of the 64 MiB range.
No processor, cache, or network RTL was changed.

The pinned NBF generator places south-cache writes at origin_y + tile_count.
For this singleton row, regeneration explicitly remaps those cache writes
from Y=3 to Y=4 and checks every destination and the exact two unfreeze
writes. It preserves both the raw and corrected NBF in the build directory.

To regenerate with the existing SDK::

    python3 scripts/hammerblade/regenerate.py \
        --manycore "$MC" --basejump "$BJ" --riscv-bin "$RISCV_BIN" \
        --configuration 2x1 --build-dir work-hb-device-2x1 --make gmake \
        --output-file designs/HammerBlade/tests/2x1/amoadd.nbf
    python3 scripts/hammerblade/regenerate.py \
        --manycore "$MC" --basejump "$BJ" --riscv-bin "$RISCV_BIN" \
        --configuration 2x1 --iterations 60000 \
        --build-dir work-hb-device-2x1-long --make gmake \
        --output-file designs/HammerBlade/tests/2x1/amoadd_long.nbf

Use --configuration 2x1 with scripts/hammerblade/check_failures.py when
checking the small simulator. Corrupted-input and watchdog checks passed.
A fresh one-worker rebuild of both default cases retained their original
49,975 and 475,850 clock counts after the shared harness changes.
Both configurations also passed the expanded Linux matrix below, including
long tests at one, two, four and eight simulator workers.

Machine and execution
---------------------

The source of the machine parameters is manycore machines/pod_1x1:
one 16x8 pod, 4 KiB DMEM and 4 KiB instruction cache per core,
32 blocking cache banks of 8 KiB, iPoly enabled, and the existing
e_vcache_test_mem SystemVerilog memory model (2 GiB total backing storage).
The core clock period is 1000 ps. This configuration is different from the
preserved HammerBench AES/HBM setup and has no historical cycle-equivalence claim.

RTLmeter supplies the main program and --timing. The autonomous
spmd_testbench supplies clocks, initial reset, tag programming, NBF
packet loading, and result monitoring. There is no custom C++ main,
Replicant shared library, host plugin, DPI code, or DRAMSim3 dependency.

No simulator-worker count, hierarchy choice, or optimization setting is
fixed in the descriptor. Example validation commands, after normal RTLmeter
setup and selecting stock Verilator on PATH::

    ./rtlmeter validate --cases 'HammerBlade:*:*'
    ./rtlmeter run --cases HammerBlade:default:amoadd \
        --compileArgs='--threads 1 --assert' --nExecute 2 --workRoot work-hb-1
    ./rtlmeter run --cases HammerBlade:default:amoadd \
        --compileArgs='--threads 2 --assert' --nExecute 2 --workRoot work-hb-2

Use a fresh compile directory after changing sources: RTLmeter caches
successful graph steps. Repeated executions start independent processes
and reload the image. The 2x1 long case has a 100-million-cycle watchdog;
the other cases retain two million cycles. Every case has a post-hook
requiring exactly one success from the selected machine's origin tile.
Do not use RTLmeter's +max_cycles truncation for correctness validation.
The optional CLI --timeout requires GNU timeout; macOS also requires
GNU gtime, as does RTLmeter itself.

Imported-source adaptations
---------------------------

Processor, cache, network, BaseJump, and HardFloat RTL are imported
unchanged. The backing-memory capacity and single-cache address selection
are adapted as described for the 2x1 configuration above. Other
simulation-harness adaptations are:

* Add RTLmeter's top include and report spmd_testbench.core_clk.
* Retain the existing test-memory branch; omit the inactive DRAMSim3 branch
  and optional profiler binds.
* Assert peripheral/loader reset immediately while tag programming is
  incomplete, retaining the original three-cycle delayed reset release.
  Otherwise the zero-initialized delay chain briefly releases reset at
  startup in two-state simulation.
* Enable assertions after serial tag reset completes; the tagged hardware
  has no initialized state before that reset sequence. Checks cover all
  program loading and execution.
* Disable Linux /proc/uptime reporting.
* Bound the NBF array to 262144 records (this image contains 30462).
  Reject missing boot-file arguments and loader-capacity exhaustion.
  Each 2x1 image contains 672 records.
* Require a positive finish count and make device failure and watchdog
  timeout terminate with a nonzero status.

Import and regenerate
---------------------

Normal benchmark users need only the checked-in NBF resource, RTLmeter's
usual dependencies, and stock Verilator. Maintainers need existing pinned
source checkouts and the HammerBlade GCC 9.2.0 SDK to regenerate resources.
Nothing below installs a compiler or modifies a source checkout.

Pins:

* bsg_manycore: 0052ce8594864befae2b85d55193706c88b14584
* basejump_stl: fa07b1f180d0d313e15dc828249eea07b341852b
* bsg-external/HardFloat: 5b7d5fe2df7e297b5ba095b3eb8a9517dc2e9d88

With HardFloat populated under $MC/imports/HardFloat::

    python3 scripts/hammerblade/import.py --manycore "$MC" --basejump "$BJ"
    python3 scripts/hammerblade/regenerate.py \
        --manycore "$MC" --basejump "$BJ" --riscv-bin "$RISCV_BIN" \
        --build-dir work-hb-device --make gmake

To regenerate the longer resource, supply these additional arguments in a
fresh build directory::

    --iterations 176 --output-file designs/HammerBlade/tests/16x8/amoadd_long.nbf

The iteration count is selected when generating the device image, not by a
simulator plusarg. It does not require recompiling the Verilator model.
The default remains seven; other counts require an explicit output file to
protect the smoke resource. The manifest records the original source hash
and the selected count. Only the upstream line #define N 7 is changed.

Use GNU Make (make on most Linux installations). The build directory
must be new. It retains the exact command, compiler version, source/ELF/NBF
hashes, link map, and build log. The program is linked with the original
SPMD startup and library rules. Only the necessary manycore archive members
are linked; confirm the retained map when changing the device build.

The seven-iteration boot-image SHA-256 is
18666971925ac91a5ece63c5951e2c52ceb56b22436ec2fbcd506b4d8edaa9b9.
The 176-iteration image SHA-256 is
854b0f0df21ac1309a218c04f7acf7b1c8a6a4e7e6103a7517213cb888079966.
The generation script checks the terminator, capacity, and complete set
of unfreeze writes for the selected physical tile group. Generated reset-ROM comments omit local paths.
The import script uses the upstream architectural file list and recursively
resolves includes, then adds only the SPMD simulation dependencies.

Licensing
---------

The descriptor records source origins and includes manycore/BaseJump
Solderpad licenses and the HardFloat BSD license. The device image contains
the manycore test, startup, barrier, coordinate setup, and configuration
variables. The retained link map identifies extracted archive members;
the initial image extracts no libc/libm/libgcc members despite the original
link command naming those archives. New integration scripts use Apache-2.0.

Validation evidence
-------------------

The initial macOS validation is recorded separately under work/.
One-, two-, four-, and eight-worker
smoke configurations each passed twice at 49,975 total clock cycles, including
reset and loading. Re-importing the design files was byte-identical,
and two fresh device builds produced identical ELF and NBF hashes.
Deliberately corrupting data[0]
produced BSG_FAIL, and a ten-cycle watchdog produced BSG_TIMEOUT; both
returned failure and were rejected by the result checker. Stock Verilator
5.052, release commit ea338be98e1e838d3518809ce8899f85a009963c, is the
initial baseline. No progress-protocol patch or PGO is used.
The 176-iteration case passed with four and eight workers, twice each
(one native RTLmeter execution and one host-counter replay), at exactly
475,850 clocks. On the local Apple M5 Max, eight-worker runs took 60.15 and
59.89 seconds; four-worker runs took 41.75 and 41.48 seconds.
Host-counter replays used macOS /usr/bin/time -l. Detailed measurements are
preserved separately under work/LONG-RUNS.md and work/verification-long.json.
The Linux validation below is a separate host qualification; upstream review
remains pending.

To run the longer case, substitute HammerBlade:default:amoadd_long in the
run commands above. Changing the NBF resource does not require recompiling
the model. Keep the same resource when comparing worker counts.

To repeat the failure-path checks after compiling::

    python3 scripts/hammerblade/check_failures.py \
        --simulator work-hb-1/HammerBlade/default/compile-0/obj_dir/Vsim \
        --out work-hb-negative

Initial 16x8 Linux validation
------------------------------

On 2026-09-27, the integration at
23b61cccd973265b429f7d3ac6899dfa8f8fe2b2 (RTLmeter base
abba286aae8baa6d1e95a0d8bb8faa4d0489a27f) passed the complete native matrix
on AlmaLinux 9.8, kernel 5.14.0-687.48.1.el9_8.x86_64. The host had four
Xeon Gold 6254 sockets, 72 physical cores / 144 logical CPUs and 754 GiB RAM.
The verified stock Verilator 5.052 revision above and Clang 21.1.8 were used
with flat compilation, --assert and the default generated-C++ flags.
There was no PGO or experimental Verilator patch.

Each entry below represents two independent executions, both passing the
post-hook. Every smoke execution had exactly 49,975 total simulated clocks;
every long execution had exactly 475,850. These match the macOS reference.
Times include initialization and loading, and exclude compilation.

.. list-table:: Linux simulation wall times (seconds)
   :header-rows: 1

   * - Simulator workers
     - amoadd (7 iterations)
     - amoadd_long (176 iterations)
   * - 1
     - 37.94, 37.60
     - Not in the requested matrix
   * - 2
     - 39.16, 39.68
     - Not in the requested matrix
   * - 4
     - 23.01, 23.20
     - 208.47, 207.72
   * - 8
     - 16.12, 15.93
     - 140.56, 143.52

The launch affinity was CPUs 0-15, sixteen physical cores on one socket.
This also bounded RTLmeter's C++ compilation to make -j16. Simulations were
serial and did not overlap compilation. Distinct work roots were used for
each worker count; the four- and eight-worker models each served both NBFs.
The image hashes above were unchanged, and the descriptor's two-million-cycle
watchdog was retained without +max_cycles truncation.

Verilation took 205.48, 223.08, 227.96 and 232.75 seconds for 1, 2, 4 and 8
workers respectively; C++ compilation took 35.94, 41.56, 42.20 and 42.55 seconds.
GNU time reported about 7.35 GiB peak RSS for Verilation and 278-343 MiB
for C++ compilation. The latter is the largest individual compiler process,
not aggregate memory across parallel jobs. Simulator peak RSS was 2.05-2.10 GiB.

Source import was byte-identical on two repetitions. An optional maintainer
check using an existing HammerBlade GCC 9.2.0 SDK regenerated each image twice:
ELF and NBF hashes were identical across repetitions, and both NBFs matched
the checked-in resources. Normal execution used only the supplied images.
Descriptor validation and check_failures.py also passed: corrupted input
produced BSG_FAIL and the watchdog produced BSG_TIMEOUT, with nonzero simulator
and checker statuses in both cases.

Six additional serial perf stat replays (one per case/worker entry) also
passed the post-hook and matched the reference clocks. The instructions:u
and cycles:u events inherited across all simulator threads and reported
100% running time, with no multiplexing reported. The long case retired
1,341,662,465,967 host instructions at four workers and 1,423,944,932,240 at
eight; host CPU cycles were 3,175,621,666,322 and 4,227,832,321,113 respectively.
These are user-mode host counters, not simulated RISC-V instruction counts;
kernel-mode activity was excluded under the existing perf permissions.
No system permissions were changed. Raw commands, counters, timing records
and build/run logs were retained separately from Git.

No Linux portability code changes were needed. Processor RTL, the harness,
the descriptor, the integration scripts and RTLmeter core remained unchanged.
This qualifies the recorded host/compiler combination, not a portable wall-time
target. Imported RTL still emits nonfatal width, timescale and other warnings;
upstream review remains pending.

Expanded Linux validation (8409032)
------------------------------------

On 2026-09-28 (UTC), parent revision 840903276e961206b834c270f60daa05104d2662
and the 60,000-iteration 2x1 long-image update were validated in isolated
checkouts on the same AlmaLinux/Xeon host and
stock Verilator 5.052 / Clang 21.1.8 toolchain recorded above. Both physical
configurations passed smoke and long at 1, 2, 4 and 8 simulator workers,
twice each: 32 successful executions, all with --assert, flat compilation
and passing post-hooks. Each pair comprises a native RTLmeter execution
and an independent perf stat replay checked by the same post-hook.

All eight executions of each case had deterministic cycle counts. The
unchanged cases matched macOS; the shortened 2x1 long image establishes
a new Linux reference:

* 2x1 smoke: 1,921; 2x1 long: 7,801,013.
* 16x8 smoke: 49,975; 16x8 long: 475,850.

The long images remained fixed at 60,000 iterations for 2x1 and 176 for
16x8, with identical hashes across worker counts. Descriptor watchdogs
were retained without +max_cycles truncation. Simulations ran serially
without overlapping compilation; CPUs 0-15 bounded compilation to -j16.

.. list-table:: Expanded Linux wall times, native / counter replay (seconds)
   :header-rows: 1

   * - Physical configuration
     - Workers
     - Smoke
     - Long
   * - 2x1
     - 1
     - 0.09 / 0.12
     - 59.71 / 59.56
   * - 2x1
     - 2
     - 0.11 / 0.13
     - 128.04 / 125.18
   * - 2x1
     - 4
     - 0.12 / 0.14
     - 189.16 / 188.81
   * - 2x1
     - 8
     - 0.13 / 0.15
     - 227.43 / 224.72
   * - 16x8
     - 1
     - 37.43 / 37.63
     - 369.25 / 379.06
   * - 16x8
     - 2
     - 38.52 / 37.66
     - 374.77 / 356.61
   * - 16x8
     - 4
     - 23.07 / 22.90
     - 202.37 / 201.83
   * - 16x8
     - 8
     - 16.13 / 16.08
     - 138.66 / 140.72

Times include initialization and loading, and exclude compilation. Native
timing wraps the simulator directly; replay timing also includes perf's
small launcher overhead. Host counters attach to the simulator and inherit
across all its threads. All sixteen replays recorded instructions:u and
cycles:u with 100% event running time and no reported multiplexing under
the existing permissions. These are user-mode host counters, not simulated
RISC-V instruction counts. Raw wall/CPU time, peak RSS, counters, exact
commands and source/tool hashes were preserved outside Git.

For 2x1, Verilation took 7.82-8.04 seconds (336-337 MiB peak RSS);
C++ compilation took 3.71-3.75 seconds (about 232 MiB peak RSS).
Simulation used about 73 MiB peak RSS.

For 16x8, Verilation took 252.35-300.88 seconds (about 7531 MiB peak RSS);
C++ compilation took 36.17-42.75 seconds (279-343 MiB peak RSS).
Simulation used 2100-2154 MiB peak RSS.

Compiler RSS is the largest individual process, not summed parallel-job
memory. Descriptor validation and both geometries' corrupted-input and
watchdog checks passed. Source import was byte-identical twice. Using an
existing GCC 9.2.0 SDK for an optional maintainer check, all four device
images regenerated twice with identical ELF/NBF hashes; every NBF matched
the checked-in resource, including the singleton south-cache remapping.

No Linux portability code changes were needed. The 2x1 long loop bound
was reduced from 180,000 to 60,000 at the user's request; the original
180,000-iteration matrix also passed and its evidence was preserved.
The shared harness passed the full 16x8 regression. Nonfatal imported-RTL
warnings and upstream review remain as noted above; Linux wall times are
observations, not calibration targets.

The 60,000-iteration NBF SHA-256 is
e10ba75a02ff10a1a6215a2d97ae7c85dbf9d57271d7555c0dd5ea63462380e5.
