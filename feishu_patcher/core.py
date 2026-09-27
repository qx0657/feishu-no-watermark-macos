from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from .arm64 import RET, find_string_xrefs, nearest_function_start


ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = ROOT / "profiles"

ANCHORS = (
    (b" can_create_watermark is false!", "WatermarkController::UpdateWatermarkView"),
    (b" close watermark_view", "WebViewWorkspace watermark state update"),
    (b"CheckWatermark", "WebViewWorkspace::CheckWatermark"),
)


@dataclass(frozen=True)
class Section:
    address: int
    size: int
    offset: int


def run(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def app_info(app: Path) -> dict[str, str]:
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    return {
        "version": str(info.get("CFBundleShortVersionString", "")),
        "build": str(info.get("CFBundleVersion", "")),
        "bundle_id": str(info.get("CFBundleIdentifier", "")),
    }


def framework_path(app: Path) -> Path:
    base = app / "Contents/Frameworks/Lark Framework.framework/Versions"
    current = base / "Current/Lark Framework"
    if current.is_file():
        return current.resolve()
    candidates = sorted(base.glob("*/Lark Framework"))
    if not candidates:
        raise RuntimeError(f"cannot find Lark Framework below {base}")
    return candidates[-1].resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_sections(binary: Path) -> dict[str, Section]:
    output = run("otool", "-l", str(binary), capture=True).stdout
    sections: dict[str, Section] = {}
    current: str | None = None
    values: dict[str, int] = {}
    for raw_line in output.splitlines():
        parts = raw_line.strip().split()
        if len(parts) == 2 and parts[0] == "sectname":
            if current and {"addr", "size", "offset"} <= values.keys():
                sections[current] = Section(values["addr"], values["size"], values["offset"])
            current = parts[1]
            values = {}
        elif current and len(parts) == 2 and parts[0] in {"addr", "size", "offset"}:
            values[parts[0]] = int(parts[1], 0)
    if current and {"addr", "size", "offset"} <= values.keys():
        sections[current] = Section(values["addr"], values["size"], values["offset"])
    for required in ("__text", "__cstring"):
        if required not in sections:
            raise RuntimeError(f"Mach-O section {required} not found")
    return sections


def architecture(binary: Path) -> str:
    output = run("file", str(binary), capture=True).stdout
    if "arm64" in output:
        return "arm64"
    raise RuntimeError(f"unsupported architecture: {output.strip()}")


def load_profiles() -> list[dict]:
    profiles = []
    for path in sorted(PROFILE_DIR.glob("*.json")):
        profile = json.loads(path.read_text())
        profile["_path"] = str(path)
        profiles.append(profile)
    return profiles


def select_profile(app: Path, allow_unreviewed: bool = False) -> dict:
    info = app_info(app)
    binary = framework_path(app)
    digest = sha256(binary)
    arch = architecture(binary)
    for profile in load_profiles():
        if profile["version"] != info["version"] or profile["arch"] != arch:
            continue
        if profile.get("original_sha256") != digest:
            continue
        if not profile.get("reviewed") and not allow_unreviewed:
            raise RuntimeError(f"profile is not reviewed: {profile['_path']}")
        return profile
    raise RuntimeError(
        f"no exact profile for Feishu {info['version']} ({arch}), framework sha256={digest}\n"
        "Run the adapt command, review its disassembly, then approve the candidate profile."
    )


def apply_profile(app: Path, profile: dict) -> None:
    binary = framework_path(app)
    with binary.open("r+b") as stream:
        for patch in profile["patches"]:
            offset = int(patch["offset"], 0)
            expected = bytes.fromhex(patch["expected"])
            replacement = bytes.fromhex(patch.get("replacement", RET.hex()))
            stream.seek(offset)
            current = stream.read(len(expected))
            if current == replacement:
                print(f"already patched: {patch['label']} @ 0x{offset:x}")
                continue
            if current != expected:
                raise RuntimeError(
                    f"unexpected bytes for {patch['label']} at 0x{offset:x}: "
                    f"{current.hex()} (expected {expected.hex()})"
                )
            stream.seek(offset)
            stream.write(replacement)
            print(f"patched: {patch['label']} @ 0x{offset:x}")


def sign_app(app: Path) -> None:
    run("codesign", "--force", "--deep", "--sign", "-", str(app))
    run("codesign", "--verify", "--deep", "--strict", str(app))


def process_ids_for(app: Path) -> list[int]:
    executable = str(app.resolve() / "Contents/MacOS/Feishu")
    result = run("pgrep", "-f", f"^{re.escape(executable)}$", check=False, capture=True)
    return [int(line) for line in result.stdout.splitlines() if line.strip().isdigit()]


def stop_app(app: Path) -> None:
    pids = process_ids_for(app)
    for pid in pids:
        os.kill(pid, signal.SIGTERM)
    deadline = time.time() + 10
    while process_ids_for(app) and time.time() < deadline:
        time.sleep(0.2)
    if process_ids_for(app):
        raise RuntimeError(f"Feishu is still running from {app}; quit it manually")


def install(source: Path, destination: Path, launch: bool, stop: bool) -> Path | None:
    if process_ids_for(destination):
        if not stop:
            raise RuntimeError("destination app is running; quit it or pass --stop")
        stop_app(destination)
    profile = select_profile(source)
    backup: Path | None = None
    if destination.exists():
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup = destination.with_name(f"{destination.stem}.backup-{timestamp}.app")
        destination.rename(backup)
        print(f"previous patched app moved to: {backup}")
    try:
        run("ditto", str(source), str(destination))
        apply_profile(destination, profile)
        sign_app(destination)
    except Exception:
        if not destination.exists() and backup:
            backup.rename(destination)
        raise
    if launch:
        run("open", "-na", str(destination))
    return backup


def verify(app: Path, profile: dict | None = None) -> None:
    binary = framework_path(app)
    if profile is None:
        info = app_info(app)
        candidates = [p for p in load_profiles() if p["version"] == info["version"]]
        if not candidates:
            raise RuntimeError(f"no profile for installed version {info['version']}")
        profile = candidates[0]
    data = binary.read_bytes()
    for patch in profile["patches"]:
        offset = int(patch["offset"], 0)
        replacement = bytes.fromhex(patch.get("replacement", RET.hex()))
        if data[offset : offset + len(replacement)] != replacement:
            raise RuntimeError(f"patch missing: {patch['label']} @ 0x{offset:x}")
    run("codesign", "--verify", "--deep", "--strict", str(app))
    print(f"verified {len(profile['patches'])} patches and code signature: {app}")


def make_candidate(app: Path) -> dict:
    binary = framework_path(app)
    data = binary.read_bytes()
    sections = read_sections(binary)
    text = sections["__text"]
    cstring = sections["__cstring"]
    patches: list[dict[str, str]] = []
    for anchor, label in ANCHORS:
        hits: list[int] = []
        start = cstring.offset
        end = cstring.offset + cstring.size
        cursor = start
        while True:
            cursor = data.find(anchor, cursor, end)
            if cursor < 0:
                break
            hits.append(cstring.address + cursor - cstring.offset)
            cursor += 1
        if len(hits) != 1:
            raise RuntimeError(f"anchor {anchor!r} expected once, found {len(hits)} times")
        xrefs = find_string_xrefs(data, hits[0], text.address, text.offset, text.size)
        starts = {
            start
            for xref in xrefs
            if (start := nearest_function_start(data, xref, text.address, text.offset)) is not None
        }
        if len(starts) != 1:
            raise RuntimeError(
                f"anchor {anchor!r} resolved to ambiguous function starts: "
                + ", ".join(hex(value) for value in sorted(starts))
            )
        address = starts.pop()
        file_offset = text.offset + address - text.address
        patches.append(
            {
                "label": label,
                "anchor": anchor.decode(),
                "offset": hex(file_offset),
                "expected": data[file_offset : file_offset + 4].hex(),
                "replacement": RET.hex(),
            }
        )
    info = app_info(app)
    return {
        "schema": 1,
        "version": info["version"],
        "build": info["build"],
        "arch": architecture(binary),
        "original_sha256": sha256(binary),
        "reviewed": False,
        "patches": patches,
    }


def approve_profile(path: Path, acknowledgement: bool) -> None:
    if not acknowledgement:
        raise RuntimeError("approval requires --i-reviewed-disassembly")
    profile = json.loads(path.read_text())
    profile["reviewed"] = True
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n")
    print(f"approved profile: {path}")
