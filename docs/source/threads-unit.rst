Thread-unit profiles
====================

Experimental Verilator configuration files live beside each design in
``designs/<design>/verilator/``. A profile is shared by the design's workloads.
Select one explicitly with ``--compileArgs``; profiles are not enabled by default.

These files currently require the experimental Verilator
`worker-assignment branch
<https://github.com/taylor-bsg/verilator/tree/codex/threads-unit-worker-assignment>`_
(validated at ``8c052270d87fe6edef528d1f23b176b52682b212``), based on PR #8804.
They are not configurations for a released Verilator version.

Layout
------

``threads-unit.vlt`` selects module types to group into units and leaves worker
assignment automatic. ``threads-unit-<machine>.vlt`` is a self-contained profile
for a host topology: it can change both the unit types and their assignment.
Load one profile per design, rather than combining the portable and machine files.

One machine file can hold several design sizes and worker counts using repeated
``-workers N->W: { ... }`` lists. ``N`` is the retained instance count of the
module type after any ``-instance`` filtering; ``W`` is the simulator worker
count. The list contains ``N`` logical worker indices in the range ``0`` through
``W-1``. Lists can wrap across lines and contain comments to show the design's
topology. Exactly one list must match both counts for each explicitly mapped
module type and instance pattern.

The optional ``-instance "prefix*"`` selects instances by their local RTL name,
without needing the enclosing hierarchy path. Omitting it selects all instances
of the module type. Different patterns for the same module type must not overlap.

Worker indices refer to simulator threads. Physical CPU affinity is configured
separately. Worker 0 is the thread calling ``eval()``; workers 1 through ``W-1``
belong to the worker pool.

Selecting a profile and inspecting indices
------------------------------------------

After normal RTLMeter setup, put the experimental Verilator on ``PATH``.
Use an absolute profile path because Verilator runs in a compilation directory::

    profile="$PWD/designs/OpenPiton/verilator/threads-unit.vlt"
    ./rtlmeter run --cases 'OpenPiton:4x4:dhry' \
        --compileArgs="--threads 8 --threads-unit-list '$profile'" \
        --nExecute 0 --workRoot work-openpiton-units

``--threads-unit-list`` writes ``obj_dir/Vsim__threads_units.txt`` in the case's
compilation directory. It lists the module type, instance index, explicit worker
index (or ``auto``), hierarchical instance name, and instance pattern. Indices
start at zero for each module type and pattern, in natural hierarchical-name
order, so index 2 sorts before index 10. Comment lines summarize local instance
names and their counts, which helps choose an instance filter. Generate this
listing with a grouping-only profile before writing new assignment lists, and
regenerate it when the RTL or Verilator changes. ``auto`` does not report the
scheduler's final automatic assignment.

HammerBlade on kk10
-------------------

``designs/HammerBlade/verilator/threads-unit-kk10.vlt`` contains the accepted
16x8, eight-worker placement: 128 compute tiles, 32 v-caches, and 16 I/O routers.
Each worker owns 16 compute tiles, four v-caches, and two I/O routers. It preserves
the placement from the prior tuning runs, including the final I/O assignment.
Only this design-size/worker-count combination is currently mapped.

With the experiment's CPU pinning, worker indices match CPU indices: workers
0 through 3 share the chiplet handling tile rows 0 through 3, and workers 4
through 7 share the chiplet handling rows 4 through 7. Each worker's tiles form
an 8x2 region, with even workers on the left and odd workers on the right.

The I/O routers use the original ``bsg_manycore_mesh_node`` module, selected by
their local instance names::

    threads_unit -module "bsg_manycore_mesh_node" -instance "io_rtr*" -workers 16->8: {
        4 4 0 0 6 6 2 2 5 5 1 1 3 3 7 7
    }

The 160 internal routers named ``rtr`` remain part of their enclosing compute
tile or v-cache unit and remain eligible for inlining. The selected I/O routers
keep their boundaries so they can be assigned independently. No RTL renaming or
copied router module is needed.

To compile and inspect the mapping::

    profile="$PWD/designs/HammerBlade/verilator/threads-unit-kk10.vlt"
    ./rtlmeter run --cases 'HammerBlade:16x8:amoadd' \
        --compileArgs="--threads 8 --threads-unit-list '$profile'" \
        --nExecute 0 --workRoot work-hammerblade-kk10

Use the same CPU pinning as the placement experiment when comparing performance.
The profile does not set affinity, compiler flags, synchronization-counter layout,
or initialization optimizations. Comparisons use Clang 21.1.8 and 15 workload
iterations. Set the 16x8 ``amoadd`` descriptor's existing ``+iterations`` value
to 15 before executing: appending a duplicate with ``--executeArgs`` does not
override the first value. The compile-only command above does not run a workload.

BlackParrot on kk10
-------------------

``designs/BlackParrot/verilator/threads-unit-kk10.vlt`` maps the 4x4 design to
eight workers. Let ``Cxy`` denote the core tile in column ``x``, row ``y``, with
row 0 at the north edge beside the four I/O nodes. For each column ``i`` from
0 through 3, worker ``i`` owns ``Ci0``, ``Ci1``, and ``IOi``; worker ``4+i`` owns
``Ci2`` and ``Ci3``. The worker map follows the physical layout::

    I/O:     0 1 2 3
    row 0:   0 1 2 3
    row 1:   0 1 2 3
    row 2:   4 5 6 7
    row 3:   4 5 6 7

The profile selects ``bp_core_tile_node`` with a ``16->8`` list and
``bp_io_tile_node`` with a ``4->8`` list. Each worker owns two vertically
adjacent core tiles; workers 0 through 3 also own the I/O node in their column.
With workers 0 through 3 pinned to one chiplet and 4 through 7 to another on
the same socket, the chiplets handle the top and bottom halves respectively.
Affinity is configured separately from the profile.

To compile and inspect the mapping::

    profile="$PWD/designs/BlackParrot/verilator/threads-unit-kk10.vlt"
    ./rtlmeter run --cases 'BlackParrot:4x4:dhry' \
        --compileArgs="--threads 8 --threads-unit-list '$profile'" \
        --nExecute 0 --workRoot work-blackparrot-kk10

Only this design-size/worker-count combination is currently mapped.

The following measurements used ``BlackParrot:4x4:dhry`` with 300 workload
iterations on kk10 on 2026-10-24, at RTLMeter revision
``cd176bf19f231c615054f1822aaaf13f0e124bec`` and the Verilator revision recorded
above. Verilator and all freshly built models used Clang 21.1.8. Worker ``i``
was pinned to CPU ``i``: CPUs 0 through 3 and 4 through 7 occupy two chiplets
on socket 0. Memory was bound to node 0; the one-worker reference used CPU 0.
Times are medians of three interleaved, isolated process runs, including
initialization and cleanup, with the default Verilator C++ optimization flags.

.. list-table:: BlackParrot 4x4 Dhrystone placement comparison
   :header-rows: 1
   :widths: 50 10 20 20

   * - Configuration
     - Workers
     - Median seconds
     - Speedup vs. 1 worker
   * - Serial reference
     - 1
     - 52.285
     - 1.00x
   * - Automatic core-tile placement (portable profile)
     - 8
     - 9.068
     - 5.77x
   * - Automatic core and I/O tile placement
     - 8
     - 7.907
     - 6.61x
   * - Explicit column-pair placement (kk10 profile)
     - 8
     - 7.598
     - 6.88x

The automatic core-and-I/O control selects the same two module types as the
kk10 profile, without ``-workers`` lists. The explicit placement reduces
runtime by 16.2% relative to the portable profile and by 3.9% relative to this
control. Its three measured runs span 7.581 through 7.632 seconds.
All four correctness screens and all twelve timed runs passed the workload's
post-hook and matched the reference output byte for byte, with 225,368
simulated cycles in every run. Other workloads remain unmeasured.

OpenPiton on kk10
-----------------

``designs/OpenPiton/verilator/threads-unit-kk10.vlt`` maps the 4x4 design to
eight workers. Coordinates are ``(y, x)``, and tile index ``4*y + x`` follows
the natural instance-name ordering. Physical CPU ownership is::

    row 0:   0 1 2 3
    row 1:   0 1 2 3
    row 2:   4 5 6 7
    row 3:   4 5 6 7

Each CPU owns two vertically adjacent tiles, including their caches and three
mesh routers. CPUs 0 through 3 share the chiplet handling the top half; CPUs
4 through 7 share the chiplet handling the bottom half on the same socket.
Both chipset I/O crossbars, ``io_xbar_noc2`` and ``io_xbar_noc3``, run on CPU 0.
``riscv_peripherals`` runs on CPU 1, and ``pc_cmp`` runs on CPU 4.

The calling thread runs the simulator scheduler on CPU 3 and also evaluates
the two tiles assigned to that CPU. Since the public interface always calls
this thread worker 0, this profile requires the following affinity::

    logical worker:   0 1 2 3 4 5 6 7
    physical CPU:     3 1 2 0 4 5 6 7

The VLT lists therefore use ``3 1 2 0`` for each of the top two tile rows,
and worker 3 for both I/O crossbars. The profile sets logical assignments;
the launcher must pin the caller and pool threads using the CPU list above.
With the experiment's affinity preload shim, set
``HB_CPUS=3,1,2,0,4,5,6,7`` and ``VERILATOR_NUMA_STRATEGY=none``. A process-wide
``taskset -c 0-7`` alone does not establish this per-thread mapping.

To compile and inspect the logical mapping::

    profile="$PWD/designs/OpenPiton/verilator/threads-unit-kk10.vlt"
    ./rtlmeter run --cases 'OpenPiton:4x4:dhry' \
        --compileArgs="--threads 8 --threads-unit-list '$profile'" \
        --nExecute 0 --workRoot work-openpiton-kk10

Only this design-size/worker-count combination is currently mapped.

The following measurements used ``OpenPiton:4x4:dhry`` on kk10 on 2026-10-24,
with the bundled RTL at RTLMeter revision
``f16e42a7b979bbcce37262b74b650f3213ba3744``, the default two workload iterations,
and 111,764 simulated cycles.
Verilator and all four freshly built models used Clang 21.1.8 and the compiler
revision recorded above, with the default Verilator C++ optimization flags.
All eight-worker configurations used the affinity above, including the caller
on CPU 3; the one-worker reference also used CPU 3. Memory was bound to node 0.
Times are medians of three interleaved, isolated process runs, including
initialization and cleanup.

.. list-table:: OpenPiton 4x4 Dhrystone placement comparison
   :header-rows: 1
   :widths: 50 10 20 20

   * - Configuration
     - Workers
     - Median seconds
     - Speedup vs. 1 worker
   * - Serial reference
     - 1
     - 40.117
     - 1.00x
   * - Automatic tile placement (portable profile)
     - 8
     - 14.962
     - 2.68x
   * - Automatic placement of the same 20 units
     - 8
     - 15.078
     - 2.66x
   * - Explicit tile and shared-block placement (kk10 profile)
     - 8
     - 14.191
     - 2.83x

The same-unit control selects tiles, both I/O crossbars, RISC-V peripherals,
and ``pc_cmp``, without ``-workers`` lists. The explicit placement reduces
runtime by 5.2% relative to the portable profile and by 5.9% relative to this
control. Its three measured runs span 14.181 through 14.233 seconds.
All four correctness screens and all twelve timed runs passed the workload's
post-hook and matched the reference output byte for byte, with the same cycle
count. Live affinity checks confirmed the caller on CPU 3 and one thread per
physical CPU 0 through 7 for every eight-worker run. Other workloads remain
unmeasured with this placement.

The same placement was measured again on 2026-10-25 with the combinational RTL
changes from `OpenPiton PR #180
<https://github.com/PrincetonUniversity/openpiton/pull/180>`_
(upstream source commit ``8d02edcab228054fa41daba294ddeb7649d305a9``).
Reproducing the following results requires applying those changes to the
vendored RTLMeter RTL. The profile selects units and workers; the RTL changes
replace explicit sensitivity lists and non-blocking combinational assignments
with ``always @(*)`` and blocking assignments in nine modules.

Both sides used the same compiler revision, Clang 21.1.8, workload, CPU affinity,
and memory placement described above. The original-RTL controls were retimed
alongside the changed-RTL models, using three interleaved, isolated runs per
configuration. These are flat-model results:

.. list-table:: OpenPiton 4x4 Dhrystone with the separate RTL fix
   :header-rows: 1
   :widths: 10 20 20 20 30

   * - Workers
     - Before (seconds)
     - After (seconds)
     - Improvement
     - Speedup vs. 1 worker (before / after)
   * - 1
     - 40.071
     - 27.559
     - 1.45x
     - 1.00x / 1.00x
   * - 8
     - 14.177
     - 2.800
     - 5.06x
     - 2.83x / 9.84x

The flat model's active-region trigger count falls from 6,732 to 175. All
requested unit assignments remain intact, and every run in the comparison
matched the reference output and 111,764 simulated cycles. The 9.84x ratio
includes differences in generated code and execution efficiency between the
one- and eight-worker models. These measurements apply to the experimental
compiler and this workload. The linked OpenPiton PR records the separate
paired VCS regressions and per-module logic-equivalence results for the RTL fix.

Coverage and validation
-----------------------

This is an initial inventory, not a claim of complete design coverage. Portable
profiles are starting points; grouping can hurt performance on some designs.
The representative correctness and performance results are in
`package 58
<https://github.com/taylor-bsg/ai-sync/blob/60747e2e8df9581cec8852ef818de9f6c02ef8ac/00000058/RESULTS.md>`_
and its
`LLVM matrix
<https://github.com/taylor-bsg/ai-sync/blob/60747e2e8df9581cec8852ef818de9f6c02ef8ac/00000058/LLVM-MATRIX.md>`_.
Those results used the source snapshots recorded there, not a new benchmark of
this profile-storage branch.

.. list-table:: Available profiles
   :header-rows: 1
   :widths: 18 24 58

   * - Design
     - Profile
     - Validation scope
   * - BlackParrot
     - ``threads-unit.vlt``
     - Existing ``bp_core_tile_node`` grouping; representative 4x4 runs in package 58.
   * - BlackParrot
     - ``threads-unit-kk10.vlt``
     - All 20 assignments audited through generated worker dispatch: sixteen
       core tiles and four I/O tile nodes across eight workers and 35 parallel
       NBA tasks. The 4x4 Dhrystone placement comparison above passed all
       correctness checks and measured 6.88x speedup versus one worker.
   * - HammerBlade
     - ``threads-unit.vlt``
     - Existing compute-tile grouping for 16x8; automatic assignment.
   * - HammerBlade
     - ``threads-unit-kk10.vlt``
     - All 176 assignments audited through generated worker dispatch on this
       branch's RTL (115 parallel NBA tasks). Owners, task order, and
       synchronization counts match the earlier router-alias profile.
       Numbering the caller as worker 0 also preserves the preceding profile's
       complete generated task schedule; only the reported worker indices change.
       Package 58 contains measurements of the accepted placement with its
       prototype implementation and the source snapshot recorded there.
       A runtime benchmark of the new syntax on this branch is still pending.
   * - OpenPiton
     - ``threads-unit.vlt``
     - Existing ``tile`` grouping; representative 4x4 runs in package 58.
   * - OpenPiton
     - ``threads-unit-kk10.vlt``
     - All 20 assignments audited through 28 generated parallel NBA tasks.
       The 4x4 Dhrystone comparison above passed all correctness and affinity
       checks and measured 2.83x speedup versus one worker, with the caller
       on CPU 3. With the separate PR #180 RTL changes, the same placement
       measured 9.84x versus its one-worker reference.

.. list-table:: Designs still needing profiles and validation
   :header-rows: 1

   * - Design
     - Status
   * - Caliptra
     - Pending
   * - Example
     - Pending
   * - HummingbirdV2-E203
     - Pending
   * - NVDLA
     - Pending
   * - OpenTitan
     - Pending
   * - Servant
     - Pending
   * - VeeR-EH1
     - Pending
   * - VeeR-EH2
     - Pending
   * - VeeR-EL2
     - Pending
   * - Vortex
     - Pending
   * - XiangShan
     - Pending
   * - XuanTie-C906
     - Pending
   * - XuanTie-C910
     - Pending
   * - XuanTie-E902
     - Pending
   * - XuanTie-E906
     - Pending

For each addition, record the RTL and Verilator revisions, design configuration,
worker count, compiler, CPU placement, workload, and correctness result before
performance measurements. Machine profiles also need an index listing and an
audit of the generated worker assignment. Keep untested sizes and worker counts
explicitly pending.
