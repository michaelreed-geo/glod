"""
Package-level configuration for optional dependencies.

Example usage:
    import glod.config as config
    config.set_use_pyproj(True)
"""

USE_PYPROJ = False


def set_use_pyproj(flag: bool) -> None:
    """Enable or disable pyproj as an optional dependency.

    Must be set to True before calling Geometry.transform() or any other
    pyproj-dependent method. Raises ImportError if flag=True but pyproj is not
    installed.
    """
    global USE_PYPROJ
    if flag:
        try:
            import pyproj  # noqa: F401
        except ImportError:
            raise ImportError(
                "pyproj is not installed. Install it with: pip install pyproj"
            )
    USE_PYPROJ = flag
