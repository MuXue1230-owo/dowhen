# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/gaogaotiantian/dowhen/blob/master/NOTICE

from __future__ import annotations

from types import CodeType, FunctionType, MethodType, ModuleType
from typing import Any, Callable, Union, Optional, List, Tuple, TYPE_CHECKING

from .callback import Callback
from .handler import EventHandler
from .types import IdentifierType
from .trigger import Trigger

if TYPE_CHECKING:  # pragma: no cover
    from types import TracebackType

class InstrumentBuilder:
    def __init__(self, entity: Union[CodeType, FunctionType, MethodType, 
                                   ModuleType, type, None] = None):
        self.entity = entity
        self.identifiers: List[IdentifierType | Tuple[IdentifierType, ...]] = []
        self.condition: Optional[Union[str, Callable[..., bool]]] = None
        self.source_hash: Optional[str] = None
        self.actions: List[Callback] = []
        
    def on(self, entity: Union[CodeType, FunctionType, MethodType, 
                             ModuleType, type, None]) -> "InstrumentBuilder":
        self.entity = entity
        return self
        
    def at_line(self, identifier: IdentifierType) -> "InstrumentBuilder":
        self.identifiers.append(identifier)
        return self
        
    def at_lines(self, *identifiers: IdentifierType) -> "InstrumentBuilder":
        self.identifiers.extend(identifiers)
        return self
        
    def when_called(self) -> "InstrumentBuilder":
        self.identifiers.append("<start>")
        return self
        
    def when_returned(self) -> "InstrumentBuilder":
        self.identifiers.append("<return>")
        return self
        
    def if_condition(self, condition: Union[str, Callable[..., bool]]) -> "InstrumentBuilder":
        self.condition = condition
        return self
        
    def verify_source(self, source_hash: str) -> "InstrumentBuilder":
        self.source_hash = source_hash
        return self
        
    def execute(self, code: Union[str, Callable[..., Any]]) -> "InstrumentBuilder":
        self.actions.append(Callback.do(code))
        return self
        
    def breakpoint(self) -> "InstrumentBuilder":
        self.actions.append(Callback.bp())
        return self
        
    def jump_to(self, target: Union[int, str]) -> "InstrumentBuilder":
        self.actions.append(Callback.goto(target))
        return self
        
    def apply(self) -> EventHandler:
        if self.entity is None:
            raise ValueError("You must first specify an entity using the on() method.")
            
        trigger = Trigger.when(
            self.entity,
            *self.identifiers,
            condition=self.condition,
            source_hash=self.source_hash
        )
        
        if not self.actions:
            raise ValueError("At least one action must be specified (execute, breakpoint, or jump_to).")
            
        handler = EventHandler(trigger, self.actions[0])
        for action in self.actions[1:]:
            if hasattr(action, 'func') and isinstance(action.func, str) and action.func == "goto":
                handler.goto(action.kwargs["target"])
            elif hasattr(action, 'func') and action.func == Callback.bp().func:
                handler.bp()
            else:
                handler.do(action.func)
                
        handler.submit()
        return handler
        
    def __enter__(self) -> EventHandler:
        return self.apply()
        
    def __exit__(
        self, 
        exc_type: Optional[type[BaseException]], 
        exc_val: Optional[BaseException], 
        exc_tb: Optional[TracebackType]
    ) -> None:
        pass


def instrument(entity: Union[CodeType, FunctionType, MethodType, 
                          ModuleType, type, None] = None) -> InstrumentBuilder:
    return InstrumentBuilder(entity)