"""Execution identity shared by replay jobs, successors and candidate retests.

Historical packets without this contract remain readable. New opt-in profiles
must carry their runtime and isolated oracle-config identities, not shell state.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

from scripts.phase95_bridge import digest, isolate_n64_bindings, runtime_digest


PROFILES = ("cooperative", "original-os-probe")
FIELDS = {"profile", "native_runtime_sha256", "oracle_runtime_sha256",
          "oracle_source_config_sha256", "oracle_config_sha256"}


def validate(packet):
    if "execution" not in packet:
        return
    contract = packet["execution"]
    if (not isinstance(contract, dict) or set(contract) != FIELDS or
            contract["profile"] not in PROFILES or
            any(not isinstance(contract[key], str) or
                re.fullmatch(r"[0-9a-f]{64}", contract[key]) is None
                for key in FIELDS - {"profile"})):
        raise ValueError("invalid replay execution contract")


def capture(pin_files, profile):
    if profile not in PROFILES:
        raise ValueError("unknown replay execution profile")
    native = Path(pin_files["native"])
    emulator = Path(pin_files["emulator"])
    config = emulator.parent / "config.ini"
    settings = json.loads(config.read_text(encoding="utf-8-sig"))
    if (profile == "original-os-probe" and
            settings.get("PreferredCores", {}).get("N64") != "Mupen64Plus"):
        raise ValueError("original OS profile requires the qualified Mupen reference")
    isolated = json.dumps(isolate_n64_bindings(settings), indent=2) + "\n"
    return {"profile": profile,
            "native_runtime_sha256": runtime_digest(native.parent),
            "oracle_runtime_sha256": runtime_digest(emulator.parent),
            "oracle_source_config_sha256": digest(config),
            "oracle_config_sha256": hashlib.sha256(
                isolated.replace("\n", os.linesep).encode()).hexdigest()}


def current(packet):
    validate(packet)
    return ("execution" not in packet or packet["execution"] ==
            capture(packet["pin_files"], packet["execution"]["profile"]))


def require_current(packet):
    if not current(packet):
        raise ValueError("replay execution runtime or oracle config changed")


def cli(packet):
    validate(packet)
    # Legacy supervisor jobs used the default cooperative runtime. Never let a
    # restarting supervisor's ambient diagnostic variables silently opt them in.
    return ["--execution-profile", packet.get("execution", {}).get(
        "profile", "cooperative")]


def check_native(packet, result, *, candidate_runtime=None):
    validate(packet)
    contract = packet.get("execution")
    if contract is None:
        if result.get("guest_os_probe") is True:
            raise ValueError("original OS result lacks a pinned execution contract")
        return
    original = contract["profile"] == "original-os-probe"
    expected = {"execution_profile": contract["profile"],
                "native_runtime_sha256": candidate_runtime or
                    contract["native_runtime_sha256"],
                "guest_os_probe": original, "guest_leaf_probe": original,
                "renderer_writeback_probe": original,
                "si_count_probe": False, "controller_guest_init_probe": False}
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError("native result changed execution profile or runtime")


def check_oracle(packet, result):
    validate(packet)
    if "execution" not in packet:
        return
    contract = packet["execution"]
    if (result.get("runtime_sha256") != contract["oracle_runtime_sha256"] or
            result.get("config_sha256") != contract["oracle_config_sha256"] or
            result.get("preferred_n64_core_override") is not None or
            result.get("mupen_cpu_core_override") is not None):
        raise ValueError("oracle result changed execution runtime or config")
