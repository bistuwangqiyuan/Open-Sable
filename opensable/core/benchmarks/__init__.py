"""
Open-Sable Benchmark Framework.

Provides a standardized evaluation harness for measuring agent capabilities
across multiple benchmark suites (GAIA, SWE-bench, WebArena, custom tasks).

Usage:
    from opensable.core.benchmarks import BenchmarkRunner, GAIASuite, SWEBenchSuite

    runner = BenchmarkRunner(agent)
    results = await runner.run_suite(GAIASuite())
    print(results.summary())
"""

from .runner import BenchmarkRunner, BenchmarkResult, BenchmarkSuite, TaskResult
from .suites import GAIASuite, SWEBenchSuite, WebArenaSuite, ToolUseSuite, ReasoningSuite

__all__ = [
    "BenchmarkRunner",
    "BenchmarkResult",
    "BenchmarkSuite",
    "TaskResult",
    "GAIASuite",
    "SWEBenchSuite",
    "WebArenaSuite",
    "ToolUseSuite",
    "ReasoningSuite",
]
