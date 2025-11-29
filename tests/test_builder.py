# Licensed under the Apache License: http://www.apache.org/licenses/LICENSE-2.0
# For details: https://github.com/gaogaotiantian/dowhen/blob/master/NOTICE

import pytest
from dowhen.builder import instrument


def test_builder_initialization():
    """Test basic initialization of InstrumentBuilder."""
    
    def f(x):
        return x + 1
    
    # Test with entity
    builder = instrument(f)
    assert builder.entity == f
    
    # Test without entity
    builder = instrument()
    assert builder.entity is None
    assert builder.identifiers == []
    assert builder.actions == []
    assert builder.condition is None
    assert builder.source_hash is None


def test_builder_entity_setting():
    """Test setting entity for InstrumentBuilder."""
    
    def f(x):
        return x + 1
    
    def g(x):
        return x * 2
    
    builder = instrument()
    builder = builder.on(f)
    assert builder.entity == f
    
    # Test changing entity
    builder = builder.on(g)
    assert builder.entity == g


def test_builder_identifiers():
    """Test setting identifiers for InstrumentBuilder."""
    
    def f(x):
        return x + 1
    
    builder = instrument(f)
    
    # Test when_called
    builder = builder.when_called()
    assert len(builder.identifiers) == 1
    assert builder.identifiers[0] == "<start>"
    
    # Test when_returned
    builder = instrument(f).when_returned()
    assert len(builder.identifiers) == 1
    assert builder.identifiers[0] == "<return>"


def test_builder_actions():
    """Test setting actions for InstrumentBuilder."""
    
    def f(x):
        return x + 1
    
    builder = instrument(f)
    
    # Test execute action
    builder = builder.execute("print('test')")
    assert len(builder.actions) == 1
    
    # Test breakpoint action
    builder = instrument(f).breakpoint()
    assert len(builder.actions) == 1
    
    # Test multiple actions
    builder = instrument(f)
    builder = builder.execute("print('action1')")
    builder = builder.execute("print('action2')")
    builder = builder.breakpoint()
    assert len(builder.actions) == 3


def test_builder_condition():
    """Test setting condition for InstrumentBuilder."""
    
    def f(x):
        return x + 1
    
    builder = instrument(f)
    builder = builder.if_condition("x > 5")
    assert builder.condition == "x > 5"
    
    # Test changing condition
    builder = builder.if_condition("x < 0")
    assert builder.condition == "x < 0"


def test_builder_source_hash():
    """Test setting source hash for InstrumentBuilder."""
    
    def f(x):
        return x + 1
    
    builder = instrument(f)
    builder = builder.verify_source("some_hash")
    assert builder.source_hash == "some_hash"


def test_builder_apply():
    """Test apply method of InstrumentBuilder."""
    
    # Test apply without entity
    builder = instrument()
    with pytest.raises(ValueError):
        builder.apply()
    
    # Test apply without actions
    def f(x):
        return x + 1
    
    builder = instrument(f).when_called()
    with pytest.raises(ValueError):
        builder.apply()
    
    # Test successful apply
    def f(x):
        return x + 1
    
    builder = instrument(f).when_called().execute("print('test')")
    handler = builder.apply()
    assert handler is not None
    
    # Test handler functionality
    handler.remove()


def test_builder_context_manager():
    """Test InstrumentBuilder as context manager."""
    
    def f(x):
        return x + 1
    
    builder = instrument(f).when_called().execute("print('test')")
    
    with builder as handler:
        assert handler is not None
    
    # After context exit, handler should still be valid
    assert handler is not None


def test_instrument_factory():
    """Test instrument factory function."""
    
    def f(x):
        return x + 1
    
    # Test with entity
    builder = instrument(f)
    assert builder.entity == f
    
    # Test without entity
    builder = instrument()
    assert builder.entity is None


def test_builder_chaining():
    """Test method chaining for InstrumentBuilder."""
    
    def f(x):
        result = x + 1
        return result
    
    builder = instrument(f)
    builder = builder.when_called()
    builder = builder.when_returned()
    builder = builder.if_condition("x > 0")
    builder = builder.execute("print('action1')")
    builder = builder.execute("print('action2')")
    builder = builder.breakpoint()
    
    assert len(builder.identifiers) == 2
    assert builder.condition == "x > 0"
    assert len(builder.actions) == 3


def test_builder_error_messages():
    """Test error messages from InstrumentBuilder."""
    
    # Test apply without entity
    builder = instrument()
    try:
        builder.apply()
        assert False, "Expected ValueError but none was raised"
    except ValueError as e:
        assert "entity" in str(e).lower()
    
    # Test apply without actions
    def f(x):
        return x + 1
    
    builder = instrument(f).when_called()
    try:
        builder.apply()
        assert False, "Expected ValueError but none was raised"
    except ValueError as e:
        assert "action" in str(e).lower()
