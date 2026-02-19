import importlib

import pytest

import glod.config as config


@pytest.fixture(autouse=True)
def reset_module():
    """
    Ensure each test starts with a clean module state.
    """
    importlib.reload(config)
    yield
    importlib.reload(config)


def test_default_use_pyproj_is_false():
    assert config.USE_PYPROJ is False


def test_set_use_pyproj_true():
    config.set_use_pyproj(True)
    assert config.USE_PYPROJ is True


def test_set_use_pyproj_false():
    config.set_use_pyproj(True)
    config.set_use_pyproj(False)
    assert config.USE_PYPROJ is False


def test_flag_is_module_global():
    config.set_use_pyproj(False)

    # Re-import should reference same module object
    import glod.config as config_again

    assert config_again.USE_PYPROJ is False
