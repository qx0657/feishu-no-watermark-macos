from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import call, patch

from feishu_patcher.desktop import LSREGISTER, configure_daily_mode, prepare_official_update


class DesktopTests(TestCase):
    @patch("feishu_patcher.desktop.replace_login_item")
    @patch("feishu_patcher.desktop.run")
    def test_daily_mode_keeps_source_and_hides_it(self, run, replace_login_item):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Applications/Lark.app"
            storage = root / "Support/Official/Lark.app"
            destination = root / "Applications/飞书.app"
            source.mkdir(parents=True)
            destination.mkdir()
            run.side_effect = lambda *args, **kwargs: storage.mkdir() if args[0] == "ditto" else None
            with patch("feishu_patcher.desktop.shutil.rmtree") as rmtree:
                configure_daily_mode(source, storage, destination)

            replace_login_item.assert_called_once_with(source, storage, destination)
            rmtree.assert_called_once_with(source)
        self.assertEqual(
            run.call_args_list,
            [
                call(str(LSREGISTER), "-u", str(source), check=False),
                call(str(LSREGISTER), "-u", str(storage), check=False),
                call("ditto", str(source), str(storage)),
                call("mdimport", "-i", str(storage), check=False),
                call(str(LSREGISTER), "-u", str(source), check=False),
                call(str(LSREGISTER), "-gc", check=False),
                call("chflags", "hidden", str(storage)),
                call(str(LSREGISTER), "-f", str(destination)),
                call("killall", "Dock", check=False),
            ],
        )

    @patch("feishu_patcher.desktop.run")
    def test_prepare_update_unhides_registers_and_launches_official(self, run):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Applications/Lark.app"
            storage = root / "Support/Official/Lark.app"
            storage.mkdir(parents=True)
            with patch("feishu_patcher.desktop.shutil.move") as move:
                prepare_official_update(source, storage, launch=True)

            move.assert_called_once_with(str(storage), str(source))
        self.assertEqual(
            run.call_args_list,
            [
                call("chflags", "nohidden", str(storage)),
                call(str(LSREGISTER), "-u", str(storage), check=False),
                call("chflags", "nohidden", str(source)),
                call(str(LSREGISTER), "-f", str(source)),
                call("open", "-na", str(source)),
            ],
        )
