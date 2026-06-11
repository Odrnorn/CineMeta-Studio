import pytest
from cinemeta.plugin_interface import CineMetaPlugin
from cinemeta.plugin_registry import PluginRegistry


class _DummyPlugin(CineMetaPlugin):
    def __init__(self, name: str) -> None:
        self._name = name
        self._version = "0.1"
        self.initialized = False
        self.torn_down = False

    @property
    def name(self) -> str: return self._name

    @property
    def version(self) -> str: return self._version

    def initialize(self) -> None: self.initialized = True
    def teardown(self) -> None: self.torn_down = True


def test_register_and_retrieve():
    reg = PluginRegistry()
    p = _DummyPlugin("foo")
    reg.register(p)
    assert reg.get("foo") is p


def test_duplicate_registration_raises():
    reg = PluginRegistry()
    reg.register(_DummyPlugin("foo"))
    with pytest.raises(ValueError):
        reg.register(_DummyPlugin("foo"))


def test_activate_calls_initialize():
    reg = PluginRegistry()
    p = _DummyPlugin("bar")
    reg.register(p)
    reg.activate("bar")
    assert p.initialized


def test_deactivate_calls_teardown():
    reg = PluginRegistry()
    p = _DummyPlugin("baz")
    reg.register(p)
    reg.activate("baz")
    reg.deactivate("baz")
    assert p.torn_down
    assert p not in reg.active_plugins


def test_activate_unknown_raises():
    reg = PluginRegistry()
    with pytest.raises(KeyError):
        reg.activate("unknown")


def test_active_plugins_returns_only_activated():
    reg = PluginRegistry()
    p1 = _DummyPlugin("alpha")
    p2 = _DummyPlugin("beta")
    reg.register(p1)
    reg.register(p2)
    reg.activate("alpha")
    # beta is registered but NOT activated
    assert p1 in reg.active_plugins
    assert p2 not in reg.active_plugins


def test_active_plugins_preserves_order():
    reg = PluginRegistry()
    names = ["z_plugin", "a_plugin", "m_plugin"]
    for n in names:
        p = _DummyPlugin(n)
        reg.register(p)
        reg.activate(n)
    result_names = [p.name for p in reg.active_plugins]
    assert result_names == names  # activation order preserved, not alphabetic


def test_activate_passes_kwargs_to_initialize():
    """activate() must forward kwargs to plugin.initialize()."""
    received: list[dict] = []

    class _KwPlugin(_DummyPlugin):
        def initialize(self, db=None, flag=False) -> None:
            received.append({"db": db, "flag": flag})

    reg = PluginRegistry()
    p = _KwPlugin("kw")
    reg.register(p)
    reg.activate("kw", db="mock_db", flag=True)
    assert received == [{"db": "mock_db", "flag": True}]
