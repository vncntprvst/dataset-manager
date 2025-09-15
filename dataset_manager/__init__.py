from importlib import metadata as _metadata

try:  # pragma: no cover - simple dynamic version helper
    __version__ = _metadata.version("dataset-manager")
except Exception:  # noqa: BLE001
    __version__ = "0.0.0"

__all__ = [
    "schema",
    "export",
    "__version__",
]

