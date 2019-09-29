Benchmarking, profiling and performance
---------------------------------------

When benchmarking code it is important to reduce other load on the system
(music player, web browser for example).  One can use the python ``timeit``
module or a command line utility like `hyperfine`_:

.. code-block:: shell

   python -m timeit -s 'from khard.khard import main' 'main(["list"])'
   hyperfine 'python -m khard list'

For profiling the ``cProfile`` python module works well.  With the help of
`gprof2dot`_ one can generate quite useful graphs:

.. code-block:: shell

   python -m cProfile -o output.file -m khard list
   gprof2dot -f pstats --show-samples output.file | dot -T png > graph.png
   xdg-open graph.png

.. _hyperfine: https://github.com/sharkdp/hyperfine
.. _gprof2dot: https://github.com/jrfonseca/gprof2dot
