# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/gaogaotiantian/dowhen/blob/master/NOTICE

from __future__ import annotations

import gc
import sys
from collections import defaultdict
import threading
import time
from types import CodeType, FrameType
from typing import TYPE_CHECKING
import weakref

if TYPE_CHECKING:  # pragma: no cover
    from .handler import EventHandler

E = sys.monitoring.events
DISABLE = sys.monitoring.DISABLE


class Instrumenter:
    _initialized: bool = False
    _pending_restart = False
    _restart_scheduled = False

    def __new__(cls, *args, **kwargs) -> Instrumenter:
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, tool_id: int = 4):
        if not self._initialized:
            self.tool_id = tool_id
            self.handlers: defaultdict[CodeType | None, dict] = defaultdict(
                lambda: defaultdict(lambda: defaultdict(weakref.WeakValueDictionary))
            )

            sys.monitoring.use_tool_id(self.tool_id, "dowhen instrumenter")
            sys.monitoring.register_callback(self.tool_id, E.LINE, self.line_callback)
            sys.monitoring.register_callback(
                self.tool_id, E.PY_RETURN, self.return_callback
            )
            sys.monitoring.register_callback(
                self.tool_id, E.PY_START, self.start_callback
            )

            self._cleanup_thread = threading.Thread(target=self._background_cleanup, daemon=True)
            self._cleanup_thread.start()

            self._initialized = True
    
    def _background_cleanup(self):
        while True:
            time.sleep(60)
            self._cleanup_invalid_references()
    
    def _cleanup_invalid_references(self):
        with threading.Lock():
            for code_key in list(self.handlers.keys()):
                code_dict = self.handlers[code_key]
                for event_type in list(code_dict.keys()):
                    event_dict = code_dict[event_type]
                    for line_number in list(event_dict.keys()):
                        handlers = event_dict[line_number]
                        
                        valid_handlers = [h for h in handlers.values() if h() is not None]
                        
                        if not valid_handlers:
                            del event_dict[line_number]
                            if not event_dict:
                                del code_dict[event_type]
                                if code_key is None:
                                    events = sys.monitoring.get_events(self.tool_id)
                                    removed_event = {"line": E.LINE, "start": E.PY_START, "return": E.PY_RETURN}[event_type]
                                    sys.monitoring.set_events(self.tool_id, events & ~removed_event)
                                else:
                                    events = sys.monitoring.get_local_events(self.tool_id, code_key)
                                    removed_event = {"line": E.LINE, "start": E.PY_START, "return": E.PY_RETURN}[event_type]
                                    sys.monitoring.set_local_events(self.tool_id, code_key, events & ~removed_event)
                        else:
                            event_dict[line_number] = weakref.WeakValueDictionary(
                                (i, h) for i, h in enumerate(valid_handlers) if h() is not None
                            )
            
            gc.collect()

    def clear_all(self) -> None:
        for code in self.handlers:
            if code is None:
                sys.monitoring.set_events(self.tool_id, E.NO_EVENTS)
            else:
                sys.monitoring.set_local_events(self.tool_id, code, E.NO_EVENTS)
        self.handlers.clear()

    def submit(self, event_handler: "EventHandler") -> None:
        trigger = event_handler.trigger
        for event in trigger.events:
            code = event.code
            if event.event_type == "line":
                assert (
                    isinstance(event.event_data, dict)
                    and "line_number" in event.event_data
                )
                ref = weakref.ref(event_handler)
                self.handlers[code]["line"][event.event_data["line_number"]][id(event_handler)] = ref
            elif event.event_type == "start":
                ref = weakref.ref(event_handler)
                self.handlers[code]["start"][None][id(event_handler)] = ref
            elif event.event_type == "return":
                ref = weakref.ref(event_handler)
                self.handlers[code]["return"][None][id(event_handler)] = ref
        
        self._schedule_restart_events()
    
    def _schedule_restart_events(self):
        if not self._restart_scheduled:
            self._restart_scheduled = True
            self._pending_restart = True
            
            try:
                import asyncio
                loop = asyncio.get_running_loop()
                loop.call_soon(self._restart_events_soon)
            except (RuntimeError, ImportError):
                self._restart_events_soon()
    
    def _restart_events_soon(self):
        if self._pending_restart:
            sys.monitoring.restart_events()
            self._pending_restart = False
        self._restart_scheduled = False

    def line_callback(self, code: CodeType, line_number: int):  # pragma: no cover
        handlers = []
        if None in self.handlers:
            handlers.extend(self.handlers[None].get("line", {}).get(line_number, {}).values())
            handlers.extend(self.handlers[None].get("line", {}).get(None, {}).values())
        if code in self.handlers:
            handlers.extend(self.handlers[code].get("line", {}).get(line_number, {}).values())
            handlers.extend(self.handlers[code].get("line", {}).get(None, {}).values())
        
        if handlers:
            return self._process_handlers([h() for h in handlers if h() is not None], sys._getframe(1))
        return sys.monitoring.DISABLE

    def register_start_event(
        self, code: CodeType | None, event_handler: "EventHandler"
    ) -> None:
        self.handlers[code].setdefault("start", []).append(event_handler)

        if code is None:
            events = sys.monitoring.get_events(self.tool_id)
            sys.monitoring.set_events(self.tool_id, events | E.PY_START)
        else:
            events = sys.monitoring.get_local_events(self.tool_id, code)
            sys.monitoring.set_local_events(self.tool_id, code, events | E.PY_START)
        self._schedule_restart_events()

    def start_callback(self, code: CodeType, offset: int):  # pragma: no cover
        handlers = []
        if None in self.handlers:
            handlers.extend(self.handlers[None].get("start", []).values())
        if code in self.handlers:
            handlers.extend(self.handlers[code].get("start", []).values())
        if handlers:
            return self._process_handlers([h() for h in handlers if h() is not None], sys._getframe(1))
        return sys.monitoring.DISABLE

    def register_return_event(
        self, code: CodeType | None, event_handler: "EventHandler"
    ) -> None:
        self.handlers[code].setdefault("return", []).append(event_handler)

        if code is None:
            events = sys.monitoring.get_events(self.tool_id)
            sys.monitoring.set_events(self.tool_id, events | E.PY_RETURN)
        else:
            events = sys.monitoring.get_local_events(self.tool_id, code)
            sys.monitoring.set_local_events(self.tool_id, code, events | E.PY_RETURN)
        self._schedule_restart_events()

    def return_callback(
        self, code: CodeType, offset: int, retval: object
    ):  # pragma: no cover
        handlers = []
        if None in self.handlers:
            handlers.extend(self.handlers[None].get("return", []).values())
        if code in self.handlers:
            handlers.extend(self.handlers[code].get("return", []).values())
        if handlers:
            return self._process_handlers([h() for h in handlers if h() is not None], sys._getframe(1), retval=retval)
        return sys.monitoring.DISABLE

    def _process_handlers(
        self, handlers: list["EventHandler"], frame: FrameType, **kwargs
    ):  # pragma: no cover
        active_handlers = []
        for handler_ref in handlers:
            handler = handler_ref()
            if handler is not None and not handler.removed:
                active_handlers.append(handler)
        
        for handler in active_handlers:
            result = handler(frame, **kwargs)
            if result is sys.monitoring.DISABLE:
                return sys.monitoring.DISABLE
        return None

    def restart_events(self) -> None:
        self._schedule_restart_events()

    def remove_handler(self, event_handler: "EventHandler") -> None:
        trigger = event_handler.trigger
        for event in trigger.events:
            code = event.code
            if code not in self.handlers or event.event_type not in self.handlers[code]:
                continue
            if event.event_type == "line":
                assert (
                    isinstance(event.event_data, dict)
                    and "line_number" in event.event_data
                )
                handlers = self.handlers[code]["line"].get(
                    event.event_data["line_number"], []
                )
            else:
                handlers = self.handlers[code][event.event_type]

            if event_handler in handlers:
                handlers.remove(event_handler)

                if event.event_type == "line" and not handlers:
                    assert (
                        isinstance(event.event_data, dict)
                        and "line_number" in event.event_data
                    )
                    del self.handlers[code]["line"][event.event_data["line_number"]]

                if not self.handlers[code][event.event_type]:
                    del self.handlers[code][event.event_type]
                    removed_event = {
                        "line": E.LINE,
                        "start": E.PY_START,
                        "return": E.PY_RETURN,
                    }[event.event_type]

                    if code is None:
                        events = sys.monitoring.get_events(self.tool_id)
                        sys.monitoring.set_events(self.tool_id, events & ~removed_event)
                    else:
                        events = sys.monitoring.get_local_events(self.tool_id, code)
                        sys.monitoring.set_local_events(
                            self.tool_id, code, events & ~removed_event
                        )
