import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.safe_fs as safe_fs


def fake_posix_os(*, missing_flag: str = "", missing_capability: str = "") -> object:
    def forbidden_open(*args: object, **kwargs: object) -> int:
        raise RuntimeError("unsafe path open attempted")

    def placeholder(*args: object, **kwargs: object) -> None:
        del args, kwargs

    fake = SimpleNamespace(
        name="posix",
        O_RDONLY=0,
        O_CLOEXEC=0,
        O_WRONLY=1,
        O_CREAT=2,
        O_EXCL=4,
        open=forbidden_open,
        stat=placeholder,
        mkdir=placeholder,
        unlink=placeholder,
        rmdir=placeholder,
        rename=placeholder,
        link=placeholder,
        scandir=placeholder,
    )
    if missing_flag != "O_NOFOLLOW":
        fake.O_NOFOLLOW = 8
    if missing_flag != "O_DIRECTORY":
        fake.O_DIRECTORY = 16
    fake.supports_dir_fd = {
        fake.open,
        fake.stat,
        fake.mkdir,
        fake.unlink,
        fake.rmdir,
        fake.rename,
        fake.link,
    }
    fake.supports_fd = {fake.scandir}
    capability = getattr(fake, missing_capability, None)
    if capability is not None:
        if capability in fake.supports_dir_fd:
            fake.supports_dir_fd.remove(capability)
        if capability in fake.supports_fd:
            fake.supports_fd.remove(capability)
    return fake


class SafeFilesystemTests(unittest.TestCase):
    def test_posix_backend_fails_closed_when_any_required_capability_is_missing(
        self,
    ) -> None:
        cases = (
            ("O_NOFOLLOW", ""),
            ("O_DIRECTORY", ""),
            ("", "open"),
            ("", "rename"),
            ("", "scandir"),
        )
        for missing_flag, missing_capability in cases:
            with self.subTest(
                flag=missing_flag,
                capability=missing_capability,
            ), patch.object(
                safe_fs,
                "os",
                fake_posix_os(
                    missing_flag=missing_flag,
                    missing_capability=missing_capability,
                ),
            ), tempfile.TemporaryDirectory() as directory:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "safe POSIX handle-relative filesystem backend is unavailable",
                ):
                    safe_fs.DirectoryHandle.open_root(Path(directory))

    def test_handle_relative_child_names_reject_windows_ads_syntax(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with safe_fs.DirectoryHandle.open_root(Path(directory)) as root:
                for child_name in (
                    "file.txt:secret",
                    "directory:stream",
                    ":hidden",
                ):
                    with self.subTest(name=child_name):
                        with self.assertRaises(ValueError):
                            root.exists(child_name)


if __name__ == "__main__":
    unittest.main()
