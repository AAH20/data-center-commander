"""Performance suite package marker.

Present for the same reason ``tests/unit/__init__.py`` is: pytest's default prepend
import mode derives module names from the file basename, and two directories sharing
a basename abort collection. Being a package also keeps ``perf_budgets`` importable
as ``tests.performance.perf_budgets`` from conftest and plugins.
"""
