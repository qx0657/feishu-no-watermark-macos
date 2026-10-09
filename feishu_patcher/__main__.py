from __future__ import annotations

import argparse
import json
from pathlib import Path

from .core import (
    app_info,
    approve_profile,
    architecture,
    framework_path,
    install,
    make_candidate,
    select_profile,
    sha256,
    verify,
)
from .desktop import archive_backup, configure_daily_mode, prepare_official_update


VISIBLE_SOURCE = Path("/Applications/Lark.app")
OFFICIAL_STORAGE = (
    Path.home() / "Library/Application Support/FeishuNoWatermark/Official/Source"
)
LEGACY_STORAGE = (
    Path.home() / "Library/Application Support/FeishuNoWatermark/Official/Lark.app"
)
LEGACY_STORAGE_V2 = (
    Path.home() / "Library/Application Support/FeishuNoWatermark/Official/Lark.app.source"
)
BACKUP_DIR = Path.home() / "Library/Application Support/FeishuNoWatermark/Backups"
DEFAULT_SOURCE = next(
    (
        path
        for path in (VISIBLE_SOURCE, OFFICIAL_STORAGE, LEGACY_STORAGE_V2, LEGACY_STORAGE)
        if path.exists()
    ),
    VISIBLE_SOURCE,
)
DEFAULT_DESTINATION = Path("/Applications/飞书.app")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python3 -m feishu_patcher")
    commands = root.add_subparsers(dest="command", required=True)

    inspect = commands.add_parser("inspect", help="show installed Feishu metadata")
    inspect.add_argument("--app", type=Path, default=DEFAULT_SOURCE)

    install_parser = commands.add_parser("install", help="copy, patch and ad-hoc sign Feishu")
    install_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    install_parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    install_parser.add_argument("--launch", action="store_true")
    install_parser.add_argument("--stop", action="store_true", help="stop a running destination app")

    verify_parser = commands.add_parser("verify", help="verify patched bytes and signature")
    verify_parser.add_argument("--app", type=Path, default=DEFAULT_DESTINATION)

    adapt = commands.add_parser("adapt", help="create an unreviewed profile for a new version")
    adapt.add_argument("--app", type=Path, default=DEFAULT_SOURCE)
    adapt.add_argument("--output", type=Path, required=True)

    approve = commands.add_parser("approve", help="mark a manually reviewed profile usable")
    approve.add_argument("profile", type=Path)
    approve.add_argument("--i-reviewed-disassembly", action="store_true")

    desktop = commands.add_parser(
        "desktop", help="use the patched app for login and hide the official update source"
    )
    desktop.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    desktop.add_argument("--storage", type=Path, default=OFFICIAL_STORAGE)
    desktop.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    desktop.add_argument("--no-dock-refresh", action="store_true")

    prepare_update = commands.add_parser(
        "prepare-update", help="show and optionally launch the official app for updating"
    )
    prepare_update.add_argument("--source", type=Path, default=VISIBLE_SOURCE)
    prepare_update.add_argument("--storage", type=Path, default=OFFICIAL_STORAGE)
    prepare_update.add_argument("--launch", action="store_true")

    refresh = commands.add_parser(
        "refresh", help="rebuild the patched app after an official update and restore desktop setup"
    )
    refresh.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    refresh.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    refresh.add_argument("--storage", type=Path, default=OFFICIAL_STORAGE)
    refresh.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    refresh.add_argument("--launch", action="store_true")
    refresh.add_argument("--stop", action="store_true", help="stop a running patched app")
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "inspect":
        binary = framework_path(args.app)
        payload = app_info(args.app) | {
            "app": str(args.app),
            "framework": str(binary),
            "arch": architecture(binary),
            "framework_sha256": sha256(binary),
        }
        try:
            payload["profile"] = select_profile(args.app)["_path"]
        except RuntimeError:
            payload["profile"] = None
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.command == "install":
        install(args.source, args.destination, args.launch, args.stop)
    elif args.command == "verify":
        verify(args.app)
    elif args.command == "adapt":
        candidate = make_candidate(args.app)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
        print(f"unreviewed candidate written to: {args.output}")
    elif args.command == "approve":
        approve_profile(args.profile, args.i_reviewed_disassembly)
    elif args.command == "desktop":
        configure_daily_mode(
            args.source, args.storage, args.destination, not args.no_dock_refresh
        )
    elif args.command == "prepare-update":
        prepare_official_update(args.source, args.storage, args.launch)
    elif args.command == "refresh":
        backup = install(args.source, args.destination, False, args.stop)
        verify(args.destination)
        archive_backup(backup, args.backup_dir)
        configure_daily_mode(args.source, args.storage, args.destination)
        if args.launch:
            from .core import run

            run("open", "-na", str(args.destination))


if __name__ == "__main__":
    main()
