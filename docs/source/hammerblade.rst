HammerBlade SPMD smoke benchmark
================================

HammerBlade:default:amoadd runs the upstream software/spmd/bsg_barrier_amoadd_test
without changing its device source. All 128 tiles perform seven iterations
of atomic increments, participant barriers, and neighbor-value checks.
Tile (0,0) reports success only after the final collective barrier;
its physical coordinates are (16,8).

The original amoadd case is an integration/sanity workload.
HammerBlade:default:amoadd_long changes only the device loop bound to 176,
retaining all 128 participants, atomic updates, barriers, and per-iteration
neighbor checks. It targets roughly one minute on this Mac with eight
simulator workers. Wall time depends on the host and worker count; the
iteration count is fixed so worker comparisons run identical work.
AES remains a separate application-workload follow-up.

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
and reload the image. The case has a two-million-cycle watchdog and a
post-hook requiring exactly one success from physical tile (16,8).
Do not use RTLmeter's +max_cycles truncation for correctness validation.
The optional CLI --timeout requires GNU timeout; macOS also requires
GNU gtime, as does RTLmeter itself.

Imported-source adaptations
---------------------------

Processor, cache, network, BaseJump, HardFloat, and backing-memory behavior
are imported unchanged. Simulation-harness adaptations are:

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

    --iterations 176 --output-file designs/HammerBlade/tests/amoadd_long.nbf

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
of 128 unfreeze writes. Generated reset-ROM comments omit local paths.
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

Local validation is recorded separately under work/. One-, two-, four-, and eight-worker
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
preserved separately under work/LONG-RUNS.md and work/verification-long.json. Linux execution
and upstream review remain separate gates from this macOS bring-up.

To run the longer case, substitute HammerBlade:default:amoadd_long in the
run commands above. Changing the NBF resource does not require recompiling
the model. Keep the same resource when comparing worker counts.

To repeat the failure-path checks after compiling::

    python3 scripts/hammerblade/check_failures.py \
        --simulator work-hb-1/HammerBlade/default/compile-0/obj_dir/Vsim \
        --out work-hb-negative
