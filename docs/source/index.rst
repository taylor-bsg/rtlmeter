RTLMeter reference
##################

Welcome to the RTLMeter reference. Documentation is organized into two parts.

The **User guide** explains how to use RTLMeter to evaluate Verilator.

The **Developer** guide explains RTLMeter internals, most importantly, how to
import new designs to the benchmark suite.

The canonical reference for the **command line interface** is the built-in help
produced by either of:

.. code:: shell

   rtlmeter --help

.. code:: shell

   rtlmeter <SUBCOMMAND> --help

.. toctree::
   :maxdepth: 1
   :caption: User guide

   gettingstarted.rst
   cases.rst
   running.rst
   report.rst
   compare.rst
   collate.rst
   advanced.rst

.. toctree::
   :maxdepth: 1
   :caption: Developer guide

   import.rst
   descriptor.rst

