dowhen documentation
====================

``dowhen`` is an instrumentation tool for Python that allows you execute
certain code at specific triggers in a clean and maintainable way.

Installation
------------

.. code-block:: bash

   pip install dowhen

Quick Start
-----------

.. code-block:: python

   from dowhen import bp, do, goto, when, instrument, profile_instrumentation, get_performance_stats

   def f(x):
       x += 100
       # Let's change the value of x before return
       return x

   # do("x = 1") is the callback
   # when(f, "return x") is the trigger
   # This is equivalent to:
   # handler = when(f, "return x").do("x = 1")
   handler = do("x = 1").when(f, "return x")
   # x = 1 is executed before "return x"
   assert f(0) == 1

   # You can remove the handler
   handler.remove()
   assert f(0) == 100

   # bp() is another callback that brings up pdb
   handler = bp().when(f, "return x")
   # This will enter pdb
   f(0)
   # You can temporarily disable the handler
   # handler.enable() will enable it again
   handler.disable()

   # goto() is a callback too
   # This will skip the line of `x += 100`
   # The handler will be removed after the context
   with goto("return x").when(f, "x += 100"):
       assert f(0) == 0

   # You can chain callbacks and they'll run in order
   # You don't need to store the handler if you don't use it
   when(f, "x += 100").goto("return x").do("x = 42")
   assert f(0) == 42

   # Using InstrumentBuilder for a fluent interface
   handler = instrument().at(f, "return x").do("x = 1").apply()
   assert f(0) == 1
   handler.remove()

   # Performance profiling
   with profile_instrumentation(f, iterations=100):
       f(0)

   report = get_performance_stats(f)
   print(report.summary())  # Summary performance report
   print(report.detailed())  # Detailed performance report

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   usage
   api
   faq

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
