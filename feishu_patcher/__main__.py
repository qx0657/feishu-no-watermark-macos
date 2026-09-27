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


DEFAULT_SOURCE = Path("/Applications/Lark.app")
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


if __name__ == "__main__":
    main()
