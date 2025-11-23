# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/gaogaotiantian/dowhen/blob/master/NOTICE


from __future__ import annotations

import functools
import inspect
import re
from collections.abc import Callable
from types import CodeType, FrameType, FunctionType, MethodType, ModuleType
from typing import Any

from .types import IdentifierType


def getrealsourcelines(obj) -> tuple[list[str], int]:
    try:
        lines, start_line = inspect.getsourcelines(obj)
        # We need to find the actual definition of the function/class
        # when it is decorated
        while lines[0].strip().startswith("@"):
            # If the first line is a decorator, we need to skip it
            # and move to the next line
            lines.pop(0)
            start_line += 1
    except OSError:
        lines, start_line = [], obj.co_firstlineno

    return lines, start_line


def get_all_code_objects(code: CodeType) -> list[CodeType]:
    """
    Recursively get all code objects from the given code object.
    """
    all_code_objects = []
    stack = [code]
    while stack:
        current_code = stack.pop()
        assert isinstance(current_code, CodeType)

        all_code_objects.append(current_code)
        for const in current_code.co_consts:
            if isinstance(const, CodeType):
                stack.append(const)

    return all_code_objects


def get_line_numbers(
    code: CodeType, identifier: IdentifierType | tuple[IdentifierType, ...]
) -> dict[CodeType, list[int]]:
    if not isinstance(identifier, tuple):
        identifier = (identifier,)

    line_numbers_ret: dict[CodeType, list[int]] = {}
    line_numbers_sets = []

    lines, start_line = getrealsourcelines(code)

    for ident in identifier:
        if isinstance(ident, int):
            line_numbers_set = {ident}
        else:
            if isinstance(ident, str) or isinstance(ident, re.Pattern):
                line_numbers_set = set()
                for i, line in enumerate(lines):
                    line = line.strip()
                    if (isinstance(ident, str) and line.startswith(ident)) or (
                        isinstance(ident, re.Pattern) and ident.match(line)
                    ):
                        line_number = start_line + i
                        line_numbers_set.add(line_number)
            else:
                raise TypeError(f"Unknown identifier type: {type(ident)}")

        if not line_numbers_set:
            return {}
        line_numbers_sets.append(line_numbers_set)

    agreed_line_numbers = set.intersection(*line_numbers_sets)
    
    line_to_code = {}
    for sub_code in get_all_code_objects(code):
        for start, end, line_no in sub_code.co_lines():
            if line_no is not None:
                existing = line_to_code.get(line_no)
                if existing is None or len(inspect.getsource(existing).splitlines()) < len(inspect.getsource(sub_code).splitlines()):
                    line_to_code[line_no] = sub_code
    
    for line_number in agreed_line_numbers:
        if line_number in line_to_code:
            sub_code = line_to_code[line_number]
            line_numbers_ret.setdefault(sub_code, []).append(line_number)

    for line_numbers in line_numbers_ret.values():
        line_numbers.sort()

    return line_numbers_ret


def get_func_args(func: Callable) -> list[str]:
    args = inspect.getfullargspec(inspect.unwrap(func)).args
    # For bound methods, skip the first argument since it's already bound
    if inspect.ismethod(func):
        return args[1:]
    else:
        return args


class AdaptiveCache:
    def __init__(self, initial_size=256, growth_factor=1.2, shrink_factor=0.8, 
                 hit_ratio_threshold=0.7, check_interval=100):
        self.cache = {}
        self.maxsize = initial_size
        self.hits = 0
        self.misses = 0
        self.access_count = 0
        self.growth_factor = growth_factor
        self.shrink_factor = shrink_factor
        self.hit_ratio_threshold = hit_ratio_threshold
        self.check_interval = check_interval
        
    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            
            self.access_count += 1
            if self.access_count >= self.check_interval:
                self._adjust_cache_size()
                self.access_count = 0
            
            if key in self.cache:
                self.hits += 1
                return self.cache[key]
            
            self.misses += 1
            
            result = func(*args, **kwargs)
            
            if len(self.cache) >= self.maxsize:
                self._cleanup_cache()
            
            self.cache[key] = result
            return result
            
        return wrapper
    
    def _adjust_cache_size(self):
        if self.hits + self.misses == 0:
            return
            
        hit_ratio = self.hits / (self.hits + self.misses)
        
        if hit_ratio > self.hit_ratio_threshold and self.maxsize < 10000:
            new_size = int(self.maxsize * self.growth_factor)
            self.maxsize = min(new_size, 10000)
        elif hit_ratio < self.hit_ratio_threshold * 0.5 and self.maxsize > 64:
            new_size = int(self.maxsize * self.shrink_factor)
            self.maxsize = max(new_size, 64)
        
        self.hits = 0
        self.misses = 0
    
    def _cleanup_cache(self):
        to_remove = max(1, int(len(self.cache) * 0.1))
        keys = list(self.cache.keys())[:to_remove]
        for key in keys:
            del self.cache[key]

get_all_code_objects = AdaptiveCache(initial_size=128)(get_all_code_objects)
get_line_numbers = AdaptiveCache(initial_size=256)(get_line_numbers)
get_func_args = AdaptiveCache(initial_size=64)(get_func_args)


def call_in_frame(func: Callable, frame: FrameType, **kwargs) -> Any:
    f_locals = frame.f_locals
    args = []
    for arg in get_func_args(func):
        if arg == "_frame":
            argval = frame
        elif arg == "_retval":
            if "retval" not in kwargs:
                raise TypeError("You can only use '_retval' in <return> callbacks.")
            argval = kwargs["retval"]
        elif arg in f_locals:
            argval = f_locals[arg]
        else:
            raise TypeError(f"Argument '{arg}' not found in frame locals.")
        args.append(argval)
    return func(*args)


def get_source_hash(entity: CodeType | FunctionType | MethodType | ModuleType | type):
    import hashlib

    source = inspect.getsource(entity)
    return hashlib.md5(source.encode("utf-8")).hexdigest()[-8:]


def clear_all() -> None:
    from .instrumenter import Instrumenter

    Instrumenter().clear_all()
    get_all_code_objects.cache_clear()
    get_line_numbers.cache_clear()
    get_func_args.cache_clear()
