Usage Guide
===========

This guide provides comprehensive information on how to use ``dowhen`` for instrumentation.

Basic Concepts
--------------

An instrumentation is basically a callback on a trigger. You can think of ``do`` as a callback, and ``when`` as a trigger.

Triggers
--------

``when``
~~~~~~~~

``when`` takes an ``entity``, optional positional ``identifiers`` and an optional keyword-only ``condition``.

* ``entity`` - a function, method, code object, class, module or ``None``
* ``identifiers`` - something to locate a specific line or a special event
* ``condition`` - an expression or a function to determine whether the trigger should fire

Entity
^^^^^^

You need to specify an entity to instrument. This can be a function, method, code object, class, module or ``None``.

If you pass a class or module, ``dowhen`` will instrument all functions and methods in that class or module.

If you pass ``None``, ``dowhen`` will instrument globally, which means every code object will be instrumented.
This will introduce an overhead at the beginning, but the unnecessary events will be disabled while the
program is running.

Identifiers
^^^^^^^^^^^

Line
""""

To locate a line, you can use the absolute line number, a string starting with ``+`` as
the relative line number, the prefix of the line or a regex pattern.

Notice that the indentation of the line is stripped before matching.

.. code-block:: python

   from dowhen import when

   def f(x):
       return x  # line 4

   # These will all locate line 4
   when(f, 4)  # absolute line number
   when(f, "+1")  # relative to function start
   when(f, "return x")  # exact match of the line content
   when(f, "ret")  # prefix of the line
   when(f, re.compile(r"return.*"))  # regex

If an identifier matches multiple lines, the callback will trigger on all of them.

.. code-block:: python

   def f(x):
       x += 0
       x += 0
       return x

   do("x += 1").when(f, "x +=")  # triggers on both lines
   assert f(0) == 2

Special Events
""""""""""""""

Besides locating lines, you can also use special events as identifiers:

* ``"<start>"`` - when the function is called
* ``"<return>"`` - when the function returns

.. code-block:: python

   when(f, "<start>")    # triggers when f is called
   when(f, "<return>")  # triggers when f returns

Combination of Identifiers
""""""""""""""""""""""""""

You can combine multiple identifiers to make the trigger more specific:

.. code-block:: python

   when(f, ("return x", "+1"))  # triggers on `return x` only when it's the +1 line

Multiple identifiers
""""""""""""""""""""

You can also specify multiple identifiers to trigger on:

.. code-block:: python

   def f(x):
       for i in range(100):
           x += i
       return x

   do("print(x)").when(f, "return x", "<start>")  # triggers on both `return x` and when f is called

Conditions
^^^^^^^^^^

You can add conditions to triggers to make them more specific:

.. code-block:: python

   from dowhen import when

   def f(x):
       return x
    
   when(f, "return x", condition="x == 0").do("x = 1")
   assert f(0) == 1  # x is set to 1 when x is 0
   assert f(2) == 2  # x is not modified when x is not 0

You can also use a function as a condition:

.. code-block:: python

   from dowhen import when

   def f(x):
       return x

   def check(x):
       return x == 0

   when(f, "return x", condition=check).do("x = 1")
   assert f(0) == 1  # x is set to 1 when x is 0
   assert f(2) == 2  # x is not modified when x is not 0

If the condition function returns ``dowhen.DISABLE``, the trigger will not fire anymore.

.. code-block:: python

   from dowhen import when, DISABLE

   def f(x):
       return x

   def check(x):
       if x == 0:
           return True
       return DISABLE

   when(f, "return x", condition=check).do("x = 1")
   assert f(0) == 1  # x is set to 1 when x is 0
   assert f(2) == 2  # x is not modified and the trigger is disabled
   assert f(0) == 0  # x is not modified anymore

Source Hash
^^^^^^^^^^^

If you need to confirm that the source code of the function has not changed,
you can use the ``source_hash`` argument.

.. code-block:: python

   from dowhen import when, get_source_hash

   def f(x):
       return x

   # Calculate this once and use the constant in your code
   source_hash = get_source_hash(f)
   # This will raise an error if the source code of f changes
   when(f, "return x", source_hash=source_hash).do("x = 1")

``source_hash`` is not a security feature. It is just a sanity check to ensure
that the source code of the function has not changed so your instrumentation
is still valid. It's just a piece of the md5 hash of the source code of the function.

Callbacks
---------

``do``
~~~~~~

``do`` executes code when the trigger fires, it can be a string or a function.

.. code-block:: python

   from dowhen import do

   def f(x):
       return x

   do("x = 1").when(f, "return x")
   assert f(0) == 1

If you are using a function for ``do``, the local variables that match the function arguments
will be automatically passed to the function.

Special arguments:

* ``_frame`` - when used, the current `frame object <https://docs.python.org/3/reference/datamodel.html#frame-objects>`_ is passed.
* ``_retval`` - when used, the return value of the function is passed. Only valid for ``<return>`` triggers.

If you want to change the value of the local variables, you need to return a dictionary
with the variable names as keys and the new values as values.

You can also return ``dowhen.DISABLE`` to disable the trigger.

.. code-block:: python

   from dowhen import do

   def f(x):
       return x

   def callback(x):
       return {"x": 1}

   do(callback).when(f, "return x")
   assert f(0) == 1

   def callback_special(_frame, _retval):
       assert _frame.f_locals["x"] == 1
       assert _retval == 1

   do(callback_special).when(f, "<return>")
   assert f(0) == 1

``bp``
~~~~~~

``bp`` enters pdb at the trigger.

.. code-block:: python

   from dowhen import bp

   def f(x):
       return x

   # Equivalent to setting a breakpoint at f
   bp().when(f, "<start>")

``goto``
~~~~~~~~

``goto`` can modify execution flow.

.. code-block:: python

   from dowhen import goto

   def f(x):
       x = 1
       return x

   # This skips the line `x = 1` and goes directly to `return x`
   goto("return x").when(f, "x = 1")
   assert f(0) == 0

You can pass an absolute line number or a source line to ``goto``, similar to ``identifier``
in ``when``. ``goto`` also takes a relative line number, but it is relative to the *executing line*.
Therefore, it can take both ``+<line_number>`` and ``-<line_number>``.

Handlers
--------

When you combine a trigger with a callback, you create a handler.

.. code-block:: python

   from dowhen import when, do

   def f(x):
       return x

   # This creates a handler
   handler = when(f, "return x").do("x = 1")
   assert f(0) == 1  # x is set to 1 when f is called

   # You can temporarily disable the handler
   handler.disable()
   assert f(0) == 0  # x is not modified anymore

   # You can re-enable the handler
   handler.enable()
   assert f(0) == 1  # x is set to 1 again

   # You can also remove the handler permanently
   handler.remove()
   assert f(0) == 0  # x is not modified anymore

You can use ``with`` statement to create a handler that is automatically removed after the block:

.. code-block:: python

   from dowhen import do

   def f(x):
       return x

   with do("x = 1").when(f, "return x"):
       assert f(0) == 1
   assert f(0) == 0

``Handler`` can use ``do``, ``bp``, and ``goto`` as well, which allows you to
chain multiple callbacks together:

.. code-block:: python

   from dowhen import when

   def f(x):
       x += 100
       return x

   when(f, "x += 100").goto("return x").do("x += 1")
   assert f(0) == 1

Utilities
--------

clear_all
~~~~~~~~~

You can clear all handlers set by ``dowhen`` using ``clear_all``.

.. code-block:: python

   from dowhen import clear_all

   clear_all()

InstrumentBuilder
----------------

``InstrumentBuilder`` provides a fluent interface for building complex instrumentation scenarios. It allows you to chain multiple actions and apply them as a single handler.

Creating an InstrumentBuilder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can create an ``InstrumentBuilder`` instance in two ways:

1. Using the ``instrument()`` factory function:

   .. code-block:: python

      from dowhen import instrument

      builder = instrument()

2. Using the ``InstrumentBuilder`` class directly:

   .. code-block:: python

      from dowhen import InstrumentBuilder

      builder = InstrumentBuilder()

Building Instrumentation
~~~~~~~~~~~~~~~~~~~~~~~~

``InstrumentBuilder`` provides a fluent interface to build instrumentation step by step.

at
^^

The ``at()`` method specifies the trigger location. It takes the same arguments as ``when()``:

.. code-block:: python

   from dowhen import instrument

   def f(x):
       return x

   builder = instrument().at(f, "return x")

Actions
^^^^^^^

You can chain actions to the builder. These actions correspond to the callback functions:

* ``do()`` - Execute arbitrary code
* ``bp()`` - Set a breakpoint
* ``goto()`` - Change execution flow

.. code-block:: python

   builder = instrument().at(f, "return x").do("x = 1")
   builder = instrument().at(f, "return x").bp()
   builder = instrument().at(f, "x = 1").goto("return x")

You can also chain multiple actions together:

.. code-block:: python

   builder = instrument().at(f, "x += 100").do("x += 1").goto("return x")

Applying the Instrumentation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once you've built the instrumentation, you can apply it using the ``apply()`` method, which returns a handler:

.. code-block:: python

   handler = instrument().at(f, "return x").do("x = 1").apply()
   assert f(0) == 1

   # You can disable, enable, or remove the handler as usual
   handler.remove()

Using with Context Manager
~~~~~~~~~~~~~~~~~~~~~~~~~~

``InstrumentBuilder`` can be used with a context manager, which automatically applies the instrumentation and removes it when exiting the context:

.. code-block:: python

   with instrument().at(f, "return x").do("x = 1"):
       assert f(0) == 1
   assert f(0) == 0

Performance Profiling
--------------------

``dowhen`` provides built-in performance profiling capabilities through the ``PerformanceProfiler`` class and related functions.

Overview
~~~~~~~~

The performance profiling feature allows you to:

* Measure the performance of functions with and without instrumentation
* Compare baseline performance with instrumented performance
* Generate detailed performance reports
* Export performance data to JSON

Quick Start
~~~~~~~~~~~

You can use the ``profile_instrumentation`` context manager to quickly profile a function:

.. code-block:: python

   from dowhen import profile_instrumentation, get_performance_stats

   def f(x):
       return x

   with profile_instrumentation(f, iterations=100):
       f(0)

   report = get_performance_stats(f)
   print(report.summary())

Creating a PerformanceProfiler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can create a ``PerformanceProfiler`` instance directly:

.. code-block:: python

   from dowhen import PerformanceProfiler

   profiler = PerformanceProfiler()

Profiling Functions
~~~~~~~~~~~~~~~~~~~

To profile a function, you can use the ``profile_instrumentation`` context manager or the profiler's methods directly:

Using the context manager:

.. code-block:: python

   with profile_instrumentation(f, iterations=100):
       f(0)

Using the profiler methods directly:

.. code-block:: python

   profiler.start_profiling()
   # Your code here
   profiler.stop_profiling()

Getting Performance Statistics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After profiling, you can get the performance statistics using ``get_performance_stats()``:

.. code-block:: python

   from dowhen import get_performance_stats

   report = get_performance_stats(f)

Performance Report
~~~~~~~~~~~~~~~~~~

The performance report provides summary and detailed information about the profiled functions.

summary()
^^^^^^^^^

The ``summary()`` method returns a summary of the performance data:

.. code-block:: python

   print(report.summary())

This will print a summary of the performance data, including the function name, baseline time, instrumented time, and overhead.

detailed()
^^^^^^^^^^

The ``detailed()`` method returns detailed performance data:

.. code-block:: python

   print(report.detailed())

This will print detailed performance data, including the function name, iterations, baseline time, instrumented time, overhead, and additional statistics.

to_dict()
^^^^^^^^^

The ``to_dict()`` method converts the performance report to a dictionary:

.. code-block:: python

   report_dict = report.to_dict()

This can be useful for further processing or serialization.

to_json()
^^^^^^^^^

The ``to_json()`` method converts the performance report to a JSON string:

.. code-block:: python

   report_json = report.to_json()

This is useful for exporting performance data to JSON format.

Configuring Default Iterations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can configure the default number of iterations for profiling:

.. code-block:: python

   from dowhen import PerformanceProfiler

   profiler = PerformanceProfiler()
   profiler.set_default_iterations(1000)

   # Get the current default iterations
   default_iterations = profiler.get_default_iterations()

Logging
~~~~~~~

The ``PerformanceProfiler`` uses Python's logging module to log information about the profiling process. You can configure the logging level to control the amount of information logged:

.. code-block:: python

   import logging

   logging.basicConfig(level=logging.DEBUG)
   # This will enable debug logging for the profiler

Profiling Multiple Functions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can profile multiple functions with the same profiler:

.. code-block:: python

   def f(x):
       return x

   def g(x):
       return x * 2

   with profile_instrumentation(f, iterations=100):
       f(0)

   with profile_instrumentation(g, iterations=100):
       g(0)

   report_f = get_performance_stats(f)
   report_g = get_performance_stats(g)

   print(report_f.summary())
   print(report_g.summary())

Profiler Handlers
~~~~~~~~~~~~~~~~~

The profiler automatically registers handlers for the profiled functions. You can register additional handlers if needed:

.. code-block:: python

   profiler = PerformanceProfiler()
   profiler.register_handler(handler)

Clearing Statistics
~~~~~~~~~~~~~~~~~~~

You can clear the performance statistics using the ``clear_stats()`` method:

.. code-block:: python

   from dowhen import clear_performance_stats

   clear_performance_stats(f)  # Clear stats for a specific function
   clear_performance_stats()   # Clear all stats
