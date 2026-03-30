"""SIPring - SIP phone ringing service."""

from pathlib import Path
import tomllib

def _get_version() -> str:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        return tomllib.load(f)["project"]["version"]

__version__ = _get_version()
