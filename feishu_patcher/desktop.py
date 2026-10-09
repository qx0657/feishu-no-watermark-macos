from __future__ import annotations

import subprocess
import shutil
from pathlib import Path


LSREGISTER = Path(
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
    "LaunchServices.framework/Support/lsregister"
)


def deactivate_stored_app(app: Path) -> None:
    plist = app / "Contents/Info.plist"
    stored_plist = app / "Contents/Info.plist.source"
    if plist.exists():
        plist.rename(stored_plist)
    run("mdimport", "-i", str(app), check=False)


def activate_stored_app(app: Path) -> None:
    plist = app / "Contents/Info.plist"
    stored_plist = app / "Contents/Info.plist.source"
    if stored_plist.exists():
        stored_plist.rename(plist)


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True)


def replace_login_item(source: Path, storage: Path, destination: Path) -> None:
    script = r'''
on run argv
    set sourcePath to item 1 of argv
    set storagePath to item 2 of argv
    set destinationPath to item 3 of argv
    tell application "System Events"
        repeat with indexValue from (count of login items) to 1 by -1
            set loginItem to login item indexValue
            try
                set itemPath to path of loginItem
                if itemPath is sourcePath or itemPath is storagePath or itemPath is destinationPath then
                    delete loginItem
                end if
            end try
        end repeat
        make login item at end with properties {path:destinationPath, hidden:false}
    end tell
end run
'''
    run("osascript", "-e", script, str(source), str(storage), str(destination))


def configure_daily_mode(
    source: Path, storage: Path, destination: Path, refresh_dock: bool = True
) -> None:
    if not source.is_dir() and not storage.is_dir():
        raise RuntimeError(f"official Feishu app not found: {source} or {storage}")
    if not destination.is_dir():
        raise RuntimeError(f"patched Feishu app not found: {destination}")
    storage.parent.mkdir(parents=True, exist_ok=True)
    (storage.parent.parent / ".metadata_never_index").touch(exist_ok=True)
    replace_login_item(source, storage, destination)
    run(str(LSREGISTER), "-u", str(source), check=False)
    run(str(LSREGISTER), "-u", str(storage), check=False)
    if source.is_dir() and source != storage:
        if storage.exists():
            raise RuntimeError(f"official update storage already exists: {storage}")
        run("ditto", str(source), str(storage))
        if not storage.is_dir():
            raise RuntimeError(f"failed to copy official update source to: {storage}")
        shutil.rmtree(source)
    deactivate_stored_app(storage)
    run(str(LSREGISTER), "-u", str(source), check=False)
    run(str(LSREGISTER), "-gc", check=False)
    run("chflags", "hidden", str(storage))
    run(str(LSREGISTER), "-f", str(destination))
    if refresh_dock:
        run("killall", "Dock", check=False)
    print(f"login item now points to: {destination}")
    print(f"official update source is retained at: {storage}")


def prepare_official_update(source: Path, storage: Path, launch: bool = False) -> None:
    if not source.is_dir():
        if not storage.is_dir():
            raise RuntimeError(f"official Feishu app not found: {source} or {storage}")
        source.parent.mkdir(parents=True, exist_ok=True)
        run("chflags", "nohidden", str(storage))
        run(str(LSREGISTER), "-u", str(storage), check=False)
        activate_stored_app(storage)
        shutil.move(str(storage), str(source))
    run("chflags", "nohidden", str(source))
    run(str(LSREGISTER), "-f", str(source))
    if launch:
        run("open", "-na", str(source))
    print(f"official update source is visible and registered: {source}")


def archive_backup(backup: Path | None, backup_dir: Path) -> None:
    if backup is None:
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{backup.name}.source"
    if target.exists():
        raise RuntimeError(f"backup target already exists: {target}")
    shutil.move(str(backup), str(target))
    run("chflags", "hidden", str(target))
    print(f"previous patched app archived at: {target}")
