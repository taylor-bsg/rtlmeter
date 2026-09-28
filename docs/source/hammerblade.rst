HammerBlade SPMD benchmarks
===========================

HammerBlade runs the upstream ``bsg_barrier_amoadd_test`` program on independent
RISC-V processors. Each iteration performs atomic increments, participant
barriers, and neighbor-value checks. The origin tile reports success after the
final collective barrier. The post-hook requires exactly one success from that
tile and rejects device failures and watchdog timeouts.

The autonomous SystemVerilog testbench uses RTLMeter's generated main and
``--timing``, with the existing ``e_vcache_test_mem`` backing-memory model.
Normal execution uses the included NBF program images and needs no HammerBlade
SDK, RISC-V compiler, Replicant runtime, DPI library, or DRAMSim3.

Configurations and cases
------------------------

``default`` instantiates 128 physical processors in a 16x8 arrangement, using
the upstream ``machines/pod_1x1`` configuration: a ruche network, iPoly hashing,
32 cache banks of 8 KiB, and 2 GiB of backing memory. ``2x1`` instantiates two
physical processors with a mesh network, iPoly disabled, four cache banks of
8 KiB, and 64 MiB of backing memory. Both have 4 KiB of data memory and 4 KiB of
instruction cache per processor. Simulator worker count is a separate setting.

.. list-table:: Fixed workloads and reference total simulated clocks
   :header-rows: 1

   * - Case
     - Device iterations
     - Clocks
   * - ``HammerBlade:default:amoadd``
     - 7
     - 49,975
   * - ``HammerBlade:default:amoadd_long``
     - 176
     - 475,850
   * - ``HammerBlade:2x1:amoadd``
     - 7
     - 1,921
   * - ``HammerBlade:2x1:amoadd_long``
     - 60,000
     - 7,801,013

The long images change only the device loop bound, retaining all atomic
operations, barriers, and per-iteration checks. Images reside under
``designs/HammerBlade/tests/16x8`` and ``tests/2x1`` and stay identical across
simulator worker counts. The small configuration provides inexpensive
integration checks; its traffic and timing differ from the 128-processor case.

Running
-------

After normal RTLMeter setup, with stock Verilator on ``PATH``::

    ./rtlmeter validate --cases 'HammerBlade:*:*'
    ./rtlmeter run --cases 'HammerBlade:2x1:*' \
        --compileArgs='--threads 1 --assert' --nExecute 2 --workRoot work-hb-2x1-t1
    ./rtlmeter run --cases 'HammerBlade:default:*' \
        --compileArgs='--threads 8 --assert' --nExecute 2 --workRoot work-hb-16x8-t8

Use separate work roots when changing compilation arguments or sources because
RTLMeter caches successful steps. Bound compilation parallelism to available
memory. The 2x1 long case has a 100-million-cycle watchdog; the other cases have
two million cycles. Do not use ``+max_cycles`` truncation for correctness runs.

Import and program provenance
-----------------------------

The descriptor records exact upstream revisions and licenses. Processor, cache,
network, BaseJump, and HardFloat RTL are imported unchanged. Harness adaptations
provide RTLMeter clock reporting, startup reset ordering, bounded image loading,
and nonzero termination on failure. Assertions are enabled after tag reset and
cover program loading and execution. Inactive DRAMSim3 and profiler branches and
host uptime reporting are omitted.

The backing-memory model derives its capacity from the selected configuration
and handles the singleton cache-selector field used by 2x1. The 2x1 image
generator also corrects south-cache destinations to Y=4, as required by the
singleton row's coordinate encoding, and checks the complete tile-release set.

Optional maintainer tools, the 2x1 machine profile, and exact regeneration
commands are preserved in the `maintenance recipe
<https://github.com/taylor-bsg/rtlmeter/blob/9f01d786c5aa18fabb1ecf934d2185367efefece/docs/source/hammerblade.rst#import-and-regenerate>`_
and its `2x1 recipe
<https://github.com/taylor-bsg/rtlmeter/blob/9f01d786c5aa18fabb1ecf934d2185367efefece/docs/source/hammerblade.rst#low-memory-2x1-configuration>`_.
These tools use pinned source checkouts and the HammerBlade GCC 9.2.0 SDK;
they are not dependencies of benchmark execution.

Linux validation
----------------

Both configurations passed smoke and long with 1, 2, 4, and 8 simulator workers,
twice each: 32 successful executions with assertions, passing post-hooks, and
the deterministic clock counts above. Qualification used stock Verilator 5.052
at ``ea338be98e1e838d3518809ce8899f85a009963c``, flat compilation, and Clang 21.1.8
on AlmaLinux 9.8 with Xeon Gold 6254 processors. Simulations ran serially without
overlapping compilation. No PGO or experimental Verilator changes were used.

Corrupted-input and watchdog checks failed correctly. Repeated import and
device-image regeneration were byte-identical. Peak simulation memory was about
73 MiB for 2x1 and 2.1 GiB for 16x8; Verilation used about 337 MiB and 7.4 GiB,
respectively. Imported RTL emits nonfatal width, timescale, and other warnings.
Detailed measurements and qualification scope are in the `maintenance report
<https://github.com/taylor-bsg/rtlmeter/blob/9f01d786c5aa18fabb1ecf934d2185367efefece/docs/source/hammerblade.rst#expanded-linux-validation-8409032>`_.
