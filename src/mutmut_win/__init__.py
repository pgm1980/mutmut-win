"""mutmut-win: Windows-native mutation testing for Python."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mutmut-win")
except PackageNotFoundError:  # pragma: no cover - editable / unpacked source install
    __version__ = "unknown"
