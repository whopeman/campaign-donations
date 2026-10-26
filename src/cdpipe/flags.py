"""
src/cdpipe/flags.py
Project : Campaign Donations
Date    : 2026-10-26
Purpose : Load feature flags from config/flags.toml, with CD_<NAME>
          environment variables taking precedence.
Usage   : flags = load_flags(Path("config/flags.toml"))
Change log:
  2026-10-26  0.1.0  Initial version.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "flags.toml"


@dataclass(frozen=True)
class Flags:
    use_gpu: bool
    cycles: tuple[int, ...]
    donor_page_threshold_usd: int
    offices: tuple[str, ...]
    county_view: bool


def _bool(name: str, raw: str) -> bool:
    v = raw.strip().lower()
    if v in {"1", "true", "yes", "on"}:
        return True
    if v in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"CD_{name.upper()} must be true or false, got {raw!r}")


def _cycles(values) -> tuple[int, ...]:
    out = tuple(int(v) for v in values)
    for c in out:
        if c % 2 or c < 1976:
            raise ValueError(f"cycle {c} must be an even year from 1976 on")
    return out


def load_flags(path: Path = DEFAULT_PATH, env: Mapping[str, str] | None = None) -> Flags:
    env = os.environ if env is None else env
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    def get(name: str):
        key = f"CD_{name.upper()}"
        if key not in env:
            return data[name], False
        return env[key], True

    raw, from_env = get("use_gpu")
    use_gpu = _bool("use_gpu", raw) if from_env else bool(raw)
    raw, from_env = get("county_view")
    county_view = _bool("county_view", raw) if from_env else bool(raw)
    raw, from_env = get("cycles")
    cycles = _cycles(raw.split(",") if from_env else raw)
    raw, from_env = get("offices")
    offices = tuple(o.strip().upper() for o in (raw.split(",") if from_env else raw))
    raw, _ = get("donor_page_threshold_usd")
    threshold = int(raw)
    if threshold < 0:
        raise ValueError("donor_page_threshold_usd must not be negative")

    return Flags(use_gpu, cycles, threshold, offices, county_view)
