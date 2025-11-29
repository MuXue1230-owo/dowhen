# profiler.py
# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/gaogaotiantian/dowhen/blob/master/NOTICE

from __future__ import annotations

import time
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from types import FunctionType, MethodType, CodeType
from typing import Generator, Optional, Union, Dict, List, Any, IO
import threading
import json
import logging
from pathlib import Path

from .instrumenter import Instrumenter

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PerformanceStats = namedtuple('PerformanceStats', [
    'total_time', 'call_count', 'avg_time', 'min_time', 'max_time',
    'overhead_percent', 'baseline_time'
])

class PerformanceProfiler:
    """A performance profiler for measuring the overhead of dowhen instrumentation.
    
    This class uses a singleton pattern to maintain global performance statistics.
    It measures the baseline performance of functions and compares it with the
    performance when dowhen instrumentation is applied.
    
    Attributes:
        _instance: The singleton instance of the profiler.
        _lock: A lock to ensure thread-safe singleton initialization.
        _active: Whether the profiler is currently active.
        _baseline_data: Dictionary storing baseline performance data.
        _instrumented_data: Dictionary storing instrumented performance data.
        _call_counts: Dictionary storing call counts for each code object.
        _handlers: Dictionary storing handlers for each code object.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Create a new instance of PerformanceProfiler if it doesn't exist.
        
        Returns:
            PerformanceProfiler: The singleton instance.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self) -> None:
        """Initialize the profiler with default settings."""
        self._active = False
        self._baseline_data: Dict[CodeType, List[float]] = defaultdict(list)
        self._instrumented_data: Dict[CodeType, List[float]] = defaultdict(list)
        self._call_counts: Dict[CodeType, int] = defaultdict(int)
        self._handlers: Dict[CodeType, List[Any]] = defaultdict(list)
        self._original_callbacks = {}
        self._default_iterations = 100
    
    @contextmanager
    def profile_scope(self, entity: Union[FunctionType, MethodType, CodeType], 
                     iterations: Optional[int] = None) -> Generator[None, None, None]:
        """Context manager for profiling a specific entity.
        
        Args:
            entity: The entity to profile (function, method, or code object).
            iterations: Number of iterations to run for baseline and instrumentation measurements.
                If None, uses the default value.
        
        Yields:
            None
        """
        if not self._active:
            yield
            return
            
        iterations = iterations or self._default_iterations
        code_obj = self._get_code_object(entity)
        try:
            self._collect_baseline(entity, iterations)
            yield
            self._collect_instrumented(entity, iterations)
        finally:
            self._generate_report_for_entity(code_obj)
    
    def start_profiling(self) -> None:
        """Start profiling.
        
        Enables performance data collection.
        """
        self._active = True
        logger.info("Performance profiling started")
    
    def stop_profiling(self) -> None:
        """Stop profiling.
        
        Disables performance data collection.
        """
        self._active = False
        logger.info("Performance profiling stopped")
    
    def register_handler(self, handler: Any) -> None:
        """Register a handler for profiling.
        
        Args:
            handler: The handler to register.
        """
        if not self._active:
            return
            
        try:
            for event in handler.trigger.events:
                if event.code:
                    self._handlers[event.code].append(handler)
                    logger.debug(f"Registered handler for code object: {event.code.co_name}")
        except Exception as e:
            logger.error(f"Failed to register handler: {e}")
    
    def get_stats(self, entity: Optional[Union[FunctionType, MethodType, CodeType]] = None) -> Dict:
        """Get performance statistics.
        
        Args:
            entity: Optional entity to get stats for. If None, returns global stats.
        
        Returns:
            Dict: Performance statistics.
        """
        if not self._active:
            return {}
            
        if entity is None:
            return self._generate_global_report()
            
        code_obj = self._get_code_object(entity)
        return self._generate_entity_report(code_obj)
    
    def clear_stats(self) -> None:
        """Clear all performance statistics."""
        self._baseline_data.clear()
        self._instrumented_data.clear()
        self._call_counts.clear()
        self._handlers.clear()
        logger.info("Performance statistics cleared")
    
    def set_default_iterations(self, iterations: int) -> None:
        """Set the default number of iterations for performance measurements.
        
        Args:
            iterations: Default number of iterations.
        """
        if iterations > 0:
            self._default_iterations = iterations
            logger.info(f"Default iterations set to: {iterations}")
    
    def get_default_iterations(self) -> int:
        """Get the default number of iterations for performance measurements.
        
        Returns:
            int: Default number of iterations.
        """
        return self._default_iterations
    
    def _get_code_object(self, entity: Union[FunctionType, MethodType, CodeType]) -> CodeType:
        """Get the code object from an entity.
        
        Args:
            entity: The entity to get the code object from.
        
        Returns:
            CodeType: The code object.
        
        Raises:
            ValueError: If the entity is not a valid type.
        """
        if isinstance(entity, CodeType):
            return entity
        elif hasattr(entity, '__code__'):
            return entity.__code__
        raise ValueError(f"Unable to obtain code object from {type(entity)}")
    
    def _collect_baseline(self, entity: Union[FunctionType, MethodType, CodeType], 
                         iterations: int) -> None:
        """Collect baseline performance data.
        
        Args:
            entity: The entity to measure.
            iterations: Number of iterations to run.
        """
        code_obj = self._get_code_object(entity)
        func = entity if callable(entity) else None
        
        if not func:
            return
            
        original_handlers = []
        instrumenter = Instrumenter()
        try:
            if code_obj in instrumenter.handlers:
                original_handlers = instrumenter.handlers[code_obj].get('line', {}).get(None, []).copy()
                for handler in original_handlers:
                    handler.disable()
            
            times = []
            for _ in range(iterations):
                start = time.perf_counter()
                func(0)  # Assume 0 is a valid argument, this could be improved
                end = time.perf_counter()
                times.append(end - start)
            
            self._baseline_data[code_obj] = times
            logger.debug(f"Collected baseline data for {code_obj.co_name}: {len(times)} samples")
        except Exception as e:
            logger.error(f"Failed to collect baseline data for {code_obj.co_name}: {e}")
        finally:
            for handler in original_handlers:
                handler.enable()
    
    def _collect_instrumented(self, entity: Union[FunctionType, MethodType, CodeType], 
                             iterations: int) -> None:
        """Collect instrumented performance data.
        
        Args:
            entity: The entity to measure.
            iterations: Number of iterations to run.
        """
        code_obj = self._get_code_object(entity)
        func = entity if callable(entity) else None
        
        if not func:
            return
            
        times = []
        try:
            for _ in range(iterations):
                start = time.perf_counter()
                func(0)  # Assume 0 is a valid argument, this could be improved
                end = time.perf_counter()
                times.append(end - start)
                self._call_counts[code_obj] += 1
            
            self._instrumented_data[code_obj] = times
            logger.debug(f"Collected instrumented data for {code_obj.co_name}: {len(times)} samples")
        except Exception as e:
            logger.error(f"Failed to collect instrumented data for {code_obj.co_name}: {e}")
    
    def _generate_entity_report(self, code_obj: CodeType) -> PerformanceStats:
        """Generate a performance report for a single entity.
        
        Args:
            code_obj: The code object to generate the report for.
        
        Returns:
            PerformanceStats: The performance statistics for the entity.
        """
        if not self._baseline_data.get(code_obj) or not self._instrumented_data.get(code_obj):
            return PerformanceStats(0, 0, 0, 0, 0, 0, 0)
            
        baseline_times = self._baseline_data[code_obj]
        instrumented_times = self._instrumented_data[code_obj]
        
        total_baseline = sum(baseline_times)
        total_instrumented = sum(instrumented_times)
        
        avg_baseline = total_baseline / len(baseline_times)
        avg_instrumented = total_instrumented / len(instrumented_times)
        
        overhead = ((avg_instrumented - avg_baseline) / avg_baseline) * 100 if avg_baseline > 0 else 0
        
        return PerformanceStats(
            total_time=total_instrumented,
            call_count=self._call_counts[code_obj],
            avg_time=avg_instrumented,
            min_time=min(instrumented_times),
            max_time=max(instrumented_times),
            overhead_percent=overhead,
            baseline_time=avg_baseline
        )
    
    def _generate_global_report(self) -> Dict[CodeType, PerformanceStats]:
        """Generate a global performance report.
        
        Returns:
            Dict[CodeType, PerformanceStats]: Performance statistics for all entities.
        """
        report = {}
        for code_obj in set(list(self._baseline_data.keys()) + list(self._instrumented_data.keys())):
            report[code_obj] = self._generate_entity_report(code_obj)
        return report
    
    def _generate_report_for_entity(self, code_obj: CodeType) -> None:
        """Generate and log a performance report for a single entity.
        
        Args:
            code_obj: The code object to generate the report for.
        """
        stats = self._generate_entity_report(code_obj)
        if stats.call_count == 0:
            return
            
        logger.info(f"\n{'='*60}")
        logger.info(f"Performance Analysis Report - Code Object: {code_obj.co_name}")
        logger.info(f"{'='*60}")
        logger.info(f"Number of calls: {stats.call_count:,}")
        logger.info(f"Average execution time: {stats.avg_time:.6f} seconds")
        logger.info(f"Baseline average time: {stats.baseline_time:.6f} seconds")
        logger.info(f"Performance overhead: {stats.overhead_percent:.2f}%")
        logger.info(f"Total execution time: {stats.total_time:.6f} seconds")
        logger.info(f"Minimum/Maximum Time: {stats.min_time:.6f} / {stats.max_time:.6f} seconds")
        logger.info(f"\nNumber of processors: {len(self._handlers.get(code_obj, []))}")
        logger.info("-"*60)

class PerformanceReport:
    """Performance report generator.
    
    Attributes:
        stats: Dictionary of performance statistics.
    """
    def __init__(self, stats: Dict[CodeType, PerformanceStats]):
        """Initialize the performance report.
        
        Args:
            stats: Dictionary of performance statistics.
        """
        self.stats = stats
        
    def summary(self) -> str:
        """Generate a summary report.
        
        Returns:
            str: Summary report.
        """
        if not self.stats:
            return "No performance data available"
            
        total_overhead = 0
        total_calls = 0
        worst_entity = None
        worst_overhead = -1
        
        for code_obj, stat in self.stats.items():
            total_overhead += stat.overhead_percent * stat.call_count
            total_calls += stat.call_count
            
            if stat.overhead_percent > worst_overhead:
                worst_overhead = stat.overhead_percent
                worst_entity = code_obj
                
        avg_overhead = total_overhead / total_calls if total_calls > 0 else 0
        
        report = []
        report.append("=" * 60)
        report.append("DOWHEN Performance Impact Analysis Report")
        report.append("=" * 60)
        report.append(f"Number of code objects analyzed: {len(self.stats)}")
        report.append(f"Total number of calls: {total_calls:,}")
        report.append(f"Average performance overhead: {avg_overhead:.2f}%")
        
        if worst_entity:
            worst_stat = self.stats[worst_entity]
            report.append(f"\nThe function with the highest overhead: {worst_entity.co_name}")
            report.append(f"  - Overhead: {worst_stat.overhead_percent:.2f}%")
            report.append(f"  - Number of calls: {worst_stat.call_count:,}")
            report.append(f"  - Average execution time: {worst_stat.avg_time:.6f} seconds")
        
        report.append("\nRecommendation:")
        if avg_overhead > 10:
            report.append("  - Performance overhead is significant; consider reducing the number of instrumentation points or optimizing conditional expressions.")
        elif avg_overhead > 5:
            report.append("  - Moderate performance overhead, monitoring the performance impact on the critical path.")
        else:
            report.append("  - Performance overhead is low and acceptable for the current configuration.")
            
        report.append("\nTip: Use clear_all() to clear unnecessary processors for improved performance.")
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def detailed(self) -> str:
        """Generate a detailed report.
        
        Returns:
            str: Detailed report.
        """
        if not self.stats:
            return "No performance data available"
            
        report = []
        report.append("=" * 80)
        report.append("DOWHEN Detailed Performance Analysis Report")
        report.append("=" * 80)
        
        for i, (code_obj, stat) in enumerate(self.stats.items(), 1):
            report.append(f"\n{i}. Function: {code_obj.co_name} (File: {code_obj.co_filename}, Line: {code_obj.co_firstlineno})")
            report.append("-" * 80)
            report.append(f"  Number of calls: {stat.call_count:,}")
            report.append(f"  Baseline average time: {stat.baseline_time:.8f} seconds")
            report.append(f"  Average time after instrumentation: {stat.avg_time:.8f} seconds")
            report.append(f"  Performance overhead: {stat.overhead_percent:.2f}%")
            report.append(f"  Total time spent: {(stat.avg_time - stat.baseline_time) * stat.call_count:.8f} seconds")
            report.append(f"  Execution timeframe: [{stat.min_time:.8f}, {stat.max_time:.8f}] seconds")
        
        report.append("\n" + "=" * 80)
        return "\n".join(report)
    
    def to_dict(self) -> Dict:
        """Convert the report to a dictionary format.
        
        Returns:
            Dict: Report data in dictionary format.
        """
        report_dict = {
            "summary": {
                "total_objects": len(self.stats),
                "total_calls": sum(stat.call_count for stat in self.stats.values()),
            },
            "details": {}
        }
        
        for code_obj, stat in self.stats.items():
            report_dict["details"][f"{code_obj.co_name} ({code_obj.co_filename}:{code_obj.co_firstlineno})"] = {
                "call_count": stat.call_count,
                "avg_time": stat.avg_time,
                "baseline_time": stat.baseline_time,
                "overhead_percent": stat.overhead_percent,
                "total_time": stat.total_time,
                "min_time": stat.min_time,
                "max_time": stat.max_time
            }
        
        return report_dict
    
    def to_json(self, file_path: Optional[Union[str, Path]] = None, indent: int = 2) -> Optional[str]:
        """Export the report to JSON format.
        
        Args:
            file_path: Optional file path to save the JSON report. If None, returns the JSON string.
            indent: Number of spaces to use for indentation.
        
        Returns:
            Optional[str]: JSON string if file_path is None, otherwise None.
        """
        report_dict = self.to_dict()
        
        if file_path:
            with open(file_path, 'w') as f:
                json.dump(report_dict, f, indent=indent)
            return None
        else:
            return json.dumps(report_dict, indent=indent)

@contextmanager
def profile_instrumentation(entity: Optional[Union[FunctionType, MethodType, CodeType]] = None,
                          iterations: int = 100) -> Generator[None, None, None]:
    """Context manager for profiling instrumentation.
    
    Args:
        entity: Optional entity to profile. If None, profiles all entities.
        iterations: Number of iterations to run for baseline and instrumentation measurements.
    
    Yields:
        None
    """
    profiler = PerformanceProfiler()
    profiler.start_profiling()
    
    try:
        if entity is not None:
            with profiler.profile_scope(entity, iterations):
                yield
        else:
            yield
    finally:
        profiler.stop_profiling()


def get_performance_stats(entity: Optional[Union[FunctionType, MethodType, CodeType]] = None) -> PerformanceReport:
    """Get performance statistics as a report.
    
    Args:
        entity: Optional entity to get stats for. If None, returns stats for all entities.
    
    Returns:
        PerformanceReport: Performance report object.
    """
    profiler = PerformanceProfiler()
    stats = profiler.get_stats(entity)
    return PerformanceReport(stats)
