import pytest
from agent_runtime.safety.engine import SafetyEngine

@pytest.fixture
def engine():
    return SafetyEngine("t1", {"allowed_domains": ["google.com", "wikipedia.org"]})

@pytest.fixture
def strict():
    return SafetyEngine("t2", {"allowed_domains": ["example.com"], "require_human_approval": True})

def test_allowed_url(engine):
    assert engine.validate_action({"type": "type", "text": "https://google.com/search"}).allowed

def test_blocked_url(engine):
    assert not engine.validate_action({"type": "type", "text": "https://evil.com"}).allowed

def test_risky_text_strict(strict):
    assert not strict.validate_action({"type": "type", "text": "confirm purchase"}).allowed

def test_safe_text(engine):
    assert engine.validate_action({"type": "type", "text": "hello"}).allowed

def test_alt_f4_blocked(engine):
    assert not engine.validate_action({"type": "keypress", "keys": ["alt", "F4"]}).allowed

def test_normal_key(engine):
    assert engine.validate_action({"type": "keypress", "keys": ["Return"]}).allowed

def test_batch_too_large(engine):
    assert not engine.validate_batch([{"type": "click", "x": 0, "y": 0}] * 20).allowed

def test_safe_actions_pass(engine):
    assert engine.validate_action({"type": "screenshot"}).allowed
    assert engine.validate_action({"type": "wait"}).allowed
    assert engine.validate_action({"type": "move", "x": 0, "y": 0}).allowed
