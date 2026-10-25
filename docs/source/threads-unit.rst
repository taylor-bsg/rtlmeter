Thread-unit profiles
====================

Experimental Verilator configuration files live beside each design in
``designs/<design>/verilator/``. A profile is shared by the design's workloads.
Select one explicitly with ``--compileArgs``; profiles are not enabled by default.

These files currently require the experimental Verilator
`worker-assignment branch
<https://github.com/taylor-bsg/verilator/tree/codex/threads-unit-worker-assignment>`_
(validated at ``91c6d81a3a94436be4f5d697acdd2232872b8021``), based on PR #8804.
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
separately. Worker ``W-1`` is the thread calling ``eval()``; the other workers
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

The I/O routers use the original ``bsg_manycore_mesh_node`` module, selected by
their local instance names::

    threads_unit -module "bsg_manycore_mesh_node" -instance "io_rtr*" -workers 16->8: {
        3 3 7 7 5 5 1 1 4 4 0 0 2 2 6 6
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
   * - HammerBlade
     - ``threads-unit.vlt``
     - Existing compute-tile grouping for 16x8; automatic assignment.
   * - HammerBlade
     - ``threads-unit-kk10.vlt``
     - All 176 assignments audited through generated worker dispatch on this
       branch's RTL (115 parallel NBA tasks). Owners, task order, and
       synchronization counts match the earlier router-alias profile.
       Package 58 contains measurements of the accepted placement with its
       prototype implementation and the source snapshot recorded there.
       A runtime benchmark of the new syntax on this branch is still pending.
   * - OpenPiton
     - ``threads-unit.vlt``
     - Existing ``tile`` grouping; representative 4x4 runs in package 58.

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
