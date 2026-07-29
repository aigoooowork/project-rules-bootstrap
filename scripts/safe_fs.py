"""Handle-relative, no-follow filesystem operations used by validators and writers."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple


FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400


@dataclass(frozen=True)
class FileSnapshot:
    content: bytes
    identity: tuple


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    is_directory: bool
    is_regular_file: bool
    is_reparse: bool


@dataclass(frozen=True)
class MoveOutcome:
    identity: tuple
    source_absent: bool
    destination_present: bool


class NamespaceMutationError(OSError):
    """A namespace call failed after a partial mutation with a known outcome."""

    def __init__(self, message: str, outcome: MoveOutcome):
        super().__init__(message)
        self.outcome = outcome


def _validate_child_name(name: str) -> str:
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or ":" in name
        or "\x00" in name
    ):
        raise ValueError("handle-relative child name is invalid")
    return name


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


if os.name == "nt":
    from ctypes import wintypes

    FILE_READ_DATA = 0x00000001
    FILE_LIST_DIRECTORY = 0x00000001
    FILE_WRITE_DATA = 0x00000002
    FILE_READ_ATTRIBUTES = 0x00000080
    DELETE = 0x00010000
    SYNCHRONIZE = 0x00100000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    FILE_OPEN = 0x00000001
    FILE_CREATE = 0x00000002
    FILE_DIRECTORY_FILE = 0x00000001
    FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
    FILE_NON_DIRECTORY_FILE = 0x00000040
    FILE_OPEN_REPARSE_POINT = 0x00200000
    OBJ_CASE_INSENSITIVE = 0x00000040
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    FILE_FULL_DIRECTORY_INFO = 0x0E
    FILE_FULL_DIRECTORY_RESTART_INFO = 0x0F
    FILE_RENAME_INFORMATION = 10
    FILE_DISPOSITION_INFORMATION = 13
    ERROR_NO_MORE_FILES = 18
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

    class _UnicodeString(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class _ObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(_UnicodeString)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", wintypes.LPVOID),
            ("SecurityQualityOfService", wintypes.LPVOID),
        ]

    class _IoStatusUnion(ctypes.Union):
        _fields_ = [("Status", ctypes.c_long), ("Pointer", wintypes.LPVOID)]

    class _IoStatusBlock(ctypes.Structure):
        _fields_ = [
            ("value", _IoStatusUnion),
            ("Information", ctypes.c_size_t),
        ]

    class _ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("CreationTimeLow", wintypes.DWORD),
            ("CreationTimeHigh", wintypes.DWORD),
            ("LastAccessTimeLow", wintypes.DWORD),
            ("LastAccessTimeHigh", wintypes.DWORD),
            ("LastWriteTimeLow", wintypes.DWORD),
            ("LastWriteTimeHigh", wintypes.DWORD),
            ("VolumeSerialNumber", wintypes.DWORD),
            ("FileSizeHigh", wintypes.DWORD),
            ("FileSizeLow", wintypes.DWORD),
            ("NumberOfLinks", wintypes.DWORD),
            ("FileIndexHigh", wintypes.DWORD),
            ("FileIndexLow", wintypes.DWORD),
        ]

    class _FileRenameInformation(ctypes.Structure):
        _fields_ = [
            ("ReplaceIfExists", wintypes.BOOLEAN),
            ("RootDirectory", wintypes.HANDLE),
            ("FileNameLength", wintypes.ULONG),
            ("FileName", wintypes.WCHAR * 1),
        ]

    class _FileDispositionInformation(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOLEAN)]

    try:
        _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        _ntdll = ctypes.WinDLL("ntdll")

        _CreateFileW = _kernel32.CreateFileW
        _CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        _CreateFileW.restype = wintypes.HANDLE

        _CloseHandle = _kernel32.CloseHandle
        _CloseHandle.argtypes = [wintypes.HANDLE]
        _CloseHandle.restype = wintypes.BOOL

        _ReadFile = _kernel32.ReadFile
        _ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        _ReadFile.restype = wintypes.BOOL

        _WriteFile = _kernel32.WriteFile
        _WriteFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        _WriteFile.restype = wintypes.BOOL

        _FlushFileBuffers = _kernel32.FlushFileBuffers
        _FlushFileBuffers.argtypes = [wintypes.HANDLE]
        _FlushFileBuffers.restype = wintypes.BOOL

        _SetFilePointerEx = _kernel32.SetFilePointerEx
        _SetFilePointerEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong),
            wintypes.DWORD,
        ]
        _SetFilePointerEx.restype = wintypes.BOOL

        _GetFileInformationByHandle = _kernel32.GetFileInformationByHandle
        _GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_ByHandleFileInformation),
        ]
        _GetFileInformationByHandle.restype = wintypes.BOOL

        _GetFileInformationByHandleEx = _kernel32.GetFileInformationByHandleEx
        _GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        _GetFileInformationByHandleEx.restype = wintypes.BOOL

        _NtCreateFile = _ntdll.NtCreateFile
        _NtCreateFile.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            ctypes.POINTER(_ObjectAttributes),
            ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            ctypes.c_void_p,
            wintypes.ULONG,
        ]
        _NtCreateFile.restype = ctypes.c_long

        _NtSetInformationFile = _ntdll.NtSetInformationFile
        _NtSetInformationFile.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p,
            wintypes.ULONG,
            ctypes.c_int,
        ]
        _NtSetInformationFile.restype = ctypes.c_long

        _RtlNtStatusToDosError = _ntdll.RtlNtStatusToDosError
        _RtlNtStatusToDosError.argtypes = [ctypes.c_long]
        _RtlNtStatusToDosError.restype = wintypes.ULONG
    except (AttributeError, OSError) as _windows_backend_error:
        _WINDOWS_BACKEND_AVAILABLE = False
    else:
        _WINDOWS_BACKEND_AVAILABLE = True
        _windows_backend_error = None


def platform_support_statement() -> str:
    if os.name != "nt":
        try:
            _posix_required()
        except RuntimeError:
            return "unavailable; filesystem operation fails closed"
        return "POSIX dir_fd with O_NOFOLLOW"
    if globals().get("_WINDOWS_BACKEND_AVAILABLE", False):
        return "Windows native RootDirectory handle-relative NT operations"
    return "unavailable; filesystem operation fails closed"


def _windows_required() -> None:
    if not globals().get("_WINDOWS_BACKEND_AVAILABLE", False):
        raise RuntimeError(
            "safe Windows handle-relative filesystem backend is unavailable"
        ) from globals().get("_windows_backend_error")


def _posix_required(platform_os: object = None) -> None:
    candidate = os if platform_os is None else platform_os
    missing = []
    for flag in ("O_NOFOLLOW", "O_DIRECTORY"):
        if not hasattr(candidate, flag):
            missing.append(flag)
    supports_dir_fd = getattr(candidate, "supports_dir_fd", set())
    for operation in (
        "open",
        "stat",
        "mkdir",
        "unlink",
        "rmdir",
        "rename",
        "link",
    ):
        function = getattr(candidate, operation, None)
        if function is None or function not in supports_dir_fd:
            missing.append("{}(dir_fd)".format(operation))
    scandir = getattr(candidate, "scandir", None)
    if (
        scandir is None
        or scandir not in getattr(candidate, "supports_fd", set())
    ):
        missing.append("scandir(fd)")
    if missing:
        raise RuntimeError(
            "safe POSIX handle-relative filesystem backend is unavailable: "
            + ", ".join(missing)
        )


def _cloexec_flag() -> int:
    return int(getattr(os, "O_CLOEXEC", 0))


def _win_error(error: int, label: str) -> OSError:
    if error in (2, 3):
        return FileNotFoundError(error, label)
    if error in (80, 183):
        return FileExistsError(error, label)
    return OSError(error, label)


def _raise_ntstatus(status: int, label: str) -> None:
    if status >= 0:
        return
    error = int(_RtlNtStatusToDosError(status))
    raise _win_error(error, label)


def _win_open_relative(
    directory_handle: int,
    name: str,
    *,
    access: int,
    disposition: int,
    options: int,
    attributes: int = 0,
) -> int:
    _windows_required()
    child_name = _validate_child_name(name)
    raw_name = child_name.encode("utf-16-le")
    name_buffer = ctypes.create_unicode_buffer(child_name)
    unicode_name = _UnicodeString(
        len(raw_name),
        len(raw_name) + 2,
        ctypes.cast(name_buffer, wintypes.LPWSTR),
    )
    object_attributes = _ObjectAttributes(
        ctypes.sizeof(_ObjectAttributes),
        directory_handle,
        ctypes.pointer(unicode_name),
        OBJ_CASE_INSENSITIVE,
        None,
        None,
    )
    io_status = _IoStatusBlock()
    handle = wintypes.HANDLE()
    status = int(
        _NtCreateFile(
            ctypes.byref(handle),
            access,
            ctypes.byref(object_attributes),
            ctypes.byref(io_status),
            None,
            attributes,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            disposition,
            options,
            None,
            0,
        )
    )
    _raise_ntstatus(status, child_name)
    if not handle.value:
        raise OSError("Windows returned an invalid child handle")
    return int(handle.value)


def _win_close(handle: int) -> None:
    if handle:
        _CloseHandle(handle)


def _win_information(handle: int) -> Tuple[int, tuple]:
    information = _ByHandleFileInformation()
    if not _GetFileInformationByHandle(handle, ctypes.byref(information)):
        raise ctypes.WinError(ctypes.get_last_error())
    identity = (
        int(information.VolumeSerialNumber),
        (int(information.FileIndexHigh) << 32) | int(information.FileIndexLow),
        bool(information.FileAttributes & FILE_ATTRIBUTE_DIRECTORY),
    )
    return int(information.FileAttributes), identity


def _win_read(handle: int) -> bytes:
    chunks: List[bytes] = []
    while True:
        buffer = ctypes.create_string_buffer(64 * 1024)
        read = wintypes.DWORD()
        if not _ReadFile(handle, buffer, len(buffer), ctypes.byref(read), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if read.value == 0:
            break
        chunks.append(buffer.raw[: read.value])
    return b"".join(chunks)


def _win_rewind(handle: int) -> None:
    if not _SetFilePointerEx(handle, 0, None, 0):
        raise ctypes.WinError(ctypes.get_last_error())


def _win_write(handle: int, content: bytes) -> None:
    offset = 0
    while offset < len(content):
        chunk = content[offset : offset + 64 * 1024]
        buffer = ctypes.create_string_buffer(chunk)
        written = wintypes.DWORD()
        if not _WriteFile(
            handle,
            buffer,
            len(chunk),
            ctypes.byref(written),
            None,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if written.value <= 0:
            raise OSError("Windows write made no progress")
        offset += int(written.value)
    if not _FlushFileBuffers(handle):
        raise ctypes.WinError(ctypes.get_last_error())


def _win_rename(
    source_handle: int,
    directory_handle: int,
    destination: str,
    *,
    replace: bool,
) -> None:
    child_name = _validate_child_name(destination)
    raw_name = child_name.encode("utf-16-le")
    size = max(
        ctypes.sizeof(_FileRenameInformation),
        _FileRenameInformation.FileName.offset + len(raw_name),
    )
    buffer = ctypes.create_string_buffer(size)
    information = _FileRenameInformation.from_buffer(buffer)
    information.ReplaceIfExists = 1 if replace else 0
    information.RootDirectory = directory_handle
    information.FileNameLength = len(raw_name)
    ctypes.memmove(
        ctypes.addressof(buffer) + _FileRenameInformation.FileName.offset,
        raw_name,
        len(raw_name),
    )
    io_status = _IoStatusBlock()
    status = int(
        _NtSetInformationFile(
            source_handle,
            ctypes.byref(io_status),
            buffer,
            size,
            FILE_RENAME_INFORMATION,
        )
    )
    _raise_ntstatus(status, child_name)


def _win_delete(handle: int) -> None:
    information = _FileDispositionInformation(1)
    io_status = _IoStatusBlock()
    status = int(
        _NtSetInformationFile(
            handle,
            ctypes.byref(io_status),
            ctypes.byref(information),
            ctypes.sizeof(information),
            FILE_DISPOSITION_INFORMATION,
        )
    )
    _raise_ntstatus(status, "handle-relative delete")


class PinnedFile:
    """A retained no-follow regular-file handle with stable object identity."""

    def __init__(self, handle: int, identity: tuple):
        self._handle = handle
        self.identity = identity
        self._closed = False

    def snapshot(self) -> FileSnapshot:
        if self._closed:
            raise ValueError("file handle is closed")
        if os.name == "nt":
            attributes, identity = _win_information(self._handle)
            if (
                attributes & FILE_ATTRIBUTE_DIRECTORY
                or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                or identity != self.identity
            ):
                raise ValueError("pinned file identity changed")
            _win_rewind(self._handle)
            return FileSnapshot(_win_read(self._handle), identity)

        file_stat = os.fstat(self._handle)
        identity = (
            file_stat.st_dev,
            file_stat.st_ino,
            stat.S_IFMT(file_stat.st_mode),
        )
        if not stat.S_ISREG(file_stat.st_mode) or identity != self.identity:
            raise ValueError("pinned file identity changed")
        os.lseek(self._handle, 0, os.SEEK_SET)
        chunks: List[bytes] = []
        while True:
            chunk = os.read(self._handle, 64 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return FileSnapshot(b"".join(chunks), identity)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if os.name == "nt":
            _win_close(self._handle)
        else:
            os.close(self._handle)

    def __enter__(self) -> "PinnedFile":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


class DirectoryHandle:
    """A verified directory object used for all child operations."""

    def __init__(self, handle: int, display_path: Path, identity: tuple):
        self._handle = handle
        self.display_path = display_path
        self.identity = identity
        self._closed = False

    @classmethod
    def open_root(cls, path: Path) -> "DirectoryHandle":
        path = Path(path)
        if os.name == "nt":
            _windows_required()
            handle = int(
                _CreateFileW(
                    str(path),
                    FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                    None,
                    OPEN_EXISTING,
                    FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
                    None,
                )
            )
            if handle in (0, INVALID_HANDLE_VALUE):
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                attributes, identity = _win_information(handle)
                if (
                    not attributes & FILE_ATTRIBUTE_DIRECTORY
                    or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise ValueError("directory root must not be a reparse point")
            except BaseException:
                _win_close(handle)
                raise
            return cls(handle, path, identity)

        _posix_required()
        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | _cloexec_flag()
        )
        descriptor = os.open(path, flags)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISDIR(file_stat.st_mode):
                raise ValueError("directory root must be a real directory")
            identity = (file_stat.st_dev, file_stat.st_ino, stat.S_IFMT(file_stat.st_mode))
        except BaseException:
            os.close(descriptor)
            raise
        return cls(descriptor, path, identity)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if os.name == "nt":
            _win_close(self._handle)
        else:
            os.close(self._handle)

    def __enter__(self) -> "DirectoryHandle":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def assert_valid(self) -> None:
        if self._closed:
            raise ValueError("directory handle is closed")
        if os.name == "nt":
            attributes, identity = _win_information(self._handle)
            if (
                not attributes & FILE_ATTRIBUTE_DIRECTORY
                or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                or identity != self.identity
            ):
                raise ValueError("directory handle identity changed")
            return
        file_stat = os.fstat(self._handle)
        identity = (file_stat.st_dev, file_stat.st_ino, stat.S_IFMT(file_stat.st_mode))
        if not stat.S_ISDIR(file_stat.st_mode) or identity != self.identity:
            raise ValueError("directory handle identity changed")

    def assert_namespace(self) -> None:
        """Fail when the original display path no longer names this directory."""
        try:
            current = DirectoryHandle.open_root(self.display_path)
        except (OSError, ValueError, RuntimeError) as error:
            raise ValueError("directory namespace no longer names the opened handle") from error
        try:
            if current.identity != self.identity:
                raise ValueError("directory namespace identity changed")
        finally:
            current.close()

    def open_directory(
        self,
        name: str,
        *,
        create: bool = False,
    ) -> Tuple["DirectoryHandle", bool]:
        child_name = _validate_child_name(name)
        created = False
        if os.name == "nt":
            try:
                handle = _win_open_relative(
                    self._handle,
                    child_name,
                    access=FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    disposition=FILE_OPEN,
                    options=(
                        FILE_DIRECTORY_FILE
                        | FILE_SYNCHRONOUS_IO_NONALERT
                        | FILE_OPEN_REPARSE_POINT
                    ),
                )
            except FileNotFoundError:
                if not create:
                    raise
                handle = _win_open_relative(
                    self._handle,
                    child_name,
                    access=FILE_LIST_DIRECTORY | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    disposition=FILE_CREATE,
                    attributes=FILE_ATTRIBUTE_DIRECTORY,
                    options=(
                        FILE_DIRECTORY_FILE
                        | FILE_SYNCHRONOUS_IO_NONALERT
                        | FILE_OPEN_REPARSE_POINT
                    ),
                )
                created = True
            try:
                attributes, identity = _win_information(handle)
                if (
                    not attributes & FILE_ATTRIBUTE_DIRECTORY
                    or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise ValueError("child directory must not be a reparse point")
            except BaseException:
                _win_close(handle)
                raise
            return (
                DirectoryHandle(handle, self.display_path / child_name, identity),
                created,
            )

        flags = (
            os.O_RDONLY
            | os.O_DIRECTORY
            | os.O_NOFOLLOW
            | _cloexec_flag()
        )
        try:
            descriptor = os.open(child_name, flags, dir_fd=self._handle)
        except FileNotFoundError:
            if not create:
                raise
            os.mkdir(child_name, dir_fd=self._handle)
            created = True
            descriptor = os.open(child_name, flags, dir_fd=self._handle)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISDIR(file_stat.st_mode):
                raise ValueError("child directory must be a real directory")
            identity = (file_stat.st_dev, file_stat.st_ino, stat.S_IFMT(file_stat.st_mode))
        except BaseException:
            os.close(descriptor)
            raise
        return (
            DirectoryHandle(descriptor, self.display_path / child_name, identity),
            created,
        )

    def snapshot(self, name: str) -> FileSnapshot:
        child_name = _validate_child_name(name)
        if os.name == "nt":
            handle = _win_open_relative(
                self._handle,
                child_name,
                access=FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                disposition=FILE_OPEN,
                options=(
                    FILE_NON_DIRECTORY_FILE
                    | FILE_SYNCHRONOUS_IO_NONALERT
                    | FILE_OPEN_REPARSE_POINT
                ),
            )
            try:
                attributes, identity = _win_information(handle)
                if (
                    attributes & FILE_ATTRIBUTE_DIRECTORY
                    or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise ValueError("child must be a regular non-reparse file")
                return FileSnapshot(_win_read(handle), identity)
            finally:
                _win_close(handle)

        flags = os.O_RDONLY | os.O_NOFOLLOW | _cloexec_flag()
        descriptor = os.open(child_name, flags, dir_fd=self._handle)
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError("child must be a regular file")
            chunks: List[bytes] = []
            while True:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            identity = (file_stat.st_dev, file_stat.st_ino, stat.S_IFMT(file_stat.st_mode))
            return FileSnapshot(b"".join(chunks), identity)
        finally:
            os.close(descriptor)

    def pin_file(self, name: str) -> PinnedFile:
        child_name = _validate_child_name(name)
        if os.name == "nt":
            handle = _win_open_relative(
                self._handle,
                child_name,
                access=FILE_READ_DATA | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                disposition=FILE_OPEN,
                options=(
                    FILE_NON_DIRECTORY_FILE
                    | FILE_SYNCHRONOUS_IO_NONALERT
                    | FILE_OPEN_REPARSE_POINT
                ),
            )
            try:
                attributes, identity = _win_information(handle)
                if (
                    attributes & FILE_ATTRIBUTE_DIRECTORY
                    or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise ValueError("pinned child must be a regular non-reparse file")
            except BaseException:
                _win_close(handle)
                raise
            return PinnedFile(handle, identity)

        descriptor = os.open(
            child_name,
            os.O_RDONLY | os.O_NOFOLLOW | _cloexec_flag(),
            dir_fd=self._handle,
        )
        try:
            file_stat = os.fstat(descriptor)
            if not stat.S_ISREG(file_stat.st_mode):
                raise ValueError("pinned child must be a regular file")
            identity = (
                file_stat.st_dev,
                file_stat.st_ino,
                stat.S_IFMT(file_stat.st_mode),
            )
        except BaseException:
            os.close(descriptor)
            raise
        return PinnedFile(descriptor, identity)

    def exists(self, name: str) -> bool:
        child_name = _validate_child_name(name)
        if os.name == "nt":
            try:
                handle = _win_open_relative(
                    self._handle,
                    child_name,
                    access=FILE_READ_ATTRIBUTES | SYNCHRONIZE,
                    disposition=FILE_OPEN,
                    options=FILE_SYNCHRONOUS_IO_NONALERT | FILE_OPEN_REPARSE_POINT,
                )
            except FileNotFoundError:
                return False
            else:
                _win_close(handle)
                return True
        try:
            os.stat(child_name, dir_fd=self._handle, follow_symlinks=False)
        except FileNotFoundError:
            return False
        return True

    def create_bytes(self, name: str, content: bytes) -> tuple:
        child_name = _validate_child_name(name)
        if os.name == "nt":
            handle = _win_open_relative(
                self._handle,
                child_name,
                access=FILE_WRITE_DATA | FILE_READ_ATTRIBUTES | DELETE | SYNCHRONIZE,
                disposition=FILE_CREATE,
                options=(
                    FILE_NON_DIRECTORY_FILE
                    | FILE_SYNCHRONOUS_IO_NONALERT
                    | FILE_OPEN_REPARSE_POINT
                ),
            )
            try:
                try:
                    _win_write(handle, content)
                    attributes, identity = _win_information(handle)
                    if (
                        attributes & FILE_ATTRIBUTE_DIRECTORY
                        or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                    ):
                        raise ValueError("created child is not a regular file")
                    return identity
                except BaseException:
                    try:
                        _win_delete(handle)
                    except OSError:
                        pass
                    raise
            finally:
                _win_close(handle)

        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | _cloexec_flag()
        )
        descriptor = os.open(child_name, flags, 0o600, dir_fd=self._handle)
        try:
            offset = 0
            while offset < len(content):
                written = os.write(descriptor, content[offset:])
                if written <= 0:
                    raise OSError("POSIX write made no progress")
                offset += written
            os.fsync(descriptor)
            file_stat = os.fstat(descriptor)
            return (file_stat.st_dev, file_stat.st_ino, stat.S_IFMT(file_stat.st_mode))
        except BaseException:
            try:
                os.unlink(child_name, dir_fd=self._handle)
            except OSError:
                pass
            raise
        finally:
            os.close(descriptor)

    def create_temporary(self, target_name: str, kind: str, content: bytes) -> Tuple[str, tuple]:
        for _ in range(128):
            name = ".{}.project-rules-bootstrap-{}-{}.tmp".format(
                target_name,
                kind,
                secrets.token_hex(12),
            )
            try:
                identity = self.create_bytes(name, content)
            except FileExistsError:
                continue
            return name, identity
        raise FileExistsError("could not allocate a unique staged file")

    def move(
        self,
        source: str,
        destination: str,
        *,
        replace: bool,
        expected_identity: Optional[tuple] = None,
        expected_sha256: Optional[str] = None,
    ) -> MoveOutcome:
        source_name = _validate_child_name(source)
        destination_name = _validate_child_name(destination)
        if os.name == "nt":
            handle = _win_open_relative(
                self._handle,
                source_name,
                access=FILE_READ_DATA | FILE_READ_ATTRIBUTES | DELETE | SYNCHRONIZE,
                disposition=FILE_OPEN,
                options=(
                    FILE_NON_DIRECTORY_FILE
                    | FILE_SYNCHRONOUS_IO_NONALERT
                    | FILE_OPEN_REPARSE_POINT
                ),
            )
            try:
                attributes, identity = _win_information(handle)
                if (
                    attributes & FILE_ATTRIBUTE_DIRECTORY
                    or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise ValueError("move source is not a regular file")
                content = _win_read(handle)
                if expected_identity is not None and identity != expected_identity:
                    raise ValueError("move source identity changed")
                if expected_sha256 is not None and _sha256(content) != expected_sha256:
                    raise ValueError("move source SHA-256 changed")
                _win_rename(
                    handle,
                    self._handle,
                    destination_name,
                    replace=replace,
                )
                return MoveOutcome(identity, True, True)
            finally:
                _win_close(handle)

        snapshot = self.snapshot(source_name)
        if expected_identity is not None and snapshot.identity != expected_identity:
            raise ValueError("move source identity changed")
        if expected_sha256 is not None and _sha256(snapshot.content) != expected_sha256:
            raise ValueError("move source SHA-256 changed")
        if replace:
            os.rename(
                source_name,
                destination_name,
                src_dir_fd=self._handle,
                dst_dir_fd=self._handle,
            )
            return MoveOutcome(snapshot.identity, True, True)
        else:
            os.link(
                source_name,
                destination_name,
                src_dir_fd=self._handle,
                dst_dir_fd=self._handle,
                follow_symlinks=False,
            )
            try:
                os.unlink(source_name, dir_fd=self._handle)
            except BaseException as error:
                raise NamespaceMutationError(
                    "move linked the destination but could not remove the source",
                    MoveOutcome(snapshot.identity, False, True),
                ) from error
            return MoveOutcome(snapshot.identity, True, True)

    def remove_file(
        self,
        name: str,
        *,
        expected_identity: Optional[tuple] = None,
        missing_ok: bool = True,
    ) -> None:
        child_name = _validate_child_name(name)
        if os.name == "nt":
            try:
                handle = _win_open_relative(
                    self._handle,
                    child_name,
                    access=FILE_READ_ATTRIBUTES | DELETE | SYNCHRONIZE,
                    disposition=FILE_OPEN,
                    options=(
                        FILE_NON_DIRECTORY_FILE
                        | FILE_SYNCHRONOUS_IO_NONALERT
                        | FILE_OPEN_REPARSE_POINT
                    ),
                )
            except FileNotFoundError:
                if missing_ok:
                    return
                raise
            try:
                attributes, identity = _win_information(handle)
                if (
                    attributes & FILE_ATTRIBUTE_DIRECTORY
                    or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise ValueError("delete target is not a regular file")
                if expected_identity is not None and identity != expected_identity:
                    raise ValueError("delete target identity changed")
                _win_delete(handle)
            finally:
                _win_close(handle)
            return

        try:
            file_stat = os.stat(
                child_name,
                dir_fd=self._handle,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            if missing_ok:
                return
            raise
        identity = (file_stat.st_dev, file_stat.st_ino, stat.S_IFMT(file_stat.st_mode))
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("delete target is not a regular file")
        if expected_identity is not None and identity != expected_identity:
            raise ValueError("delete target identity changed")
        os.unlink(child_name, dir_fd=self._handle)

    def remove_directory(self, name: str) -> None:
        child_name = _validate_child_name(name)
        if os.name == "nt":
            handle = _win_open_relative(
                self._handle,
                child_name,
                access=FILE_READ_ATTRIBUTES | DELETE | SYNCHRONIZE,
                disposition=FILE_OPEN,
                options=(
                    FILE_DIRECTORY_FILE
                    | FILE_SYNCHRONOUS_IO_NONALERT
                    | FILE_OPEN_REPARSE_POINT
                ),
            )
            try:
                attributes, _ = _win_information(handle)
                if (
                    not attributes & FILE_ATTRIBUTE_DIRECTORY
                    or attributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise ValueError("directory delete target is unsafe")
                _win_delete(handle)
            finally:
                _win_close(handle)
            return
        os.rmdir(child_name, dir_fd=self._handle)

    def list_entries(self) -> List[DirectoryEntry]:
        if os.name == "nt":
            entries: List[DirectoryEntry] = []
            first = True
            while True:
                buffer = ctypes.create_string_buffer(64 * 1024)
                ctypes.set_last_error(0)
                success = _GetFileInformationByHandleEx(
                    self._handle,
                    FILE_FULL_DIRECTORY_RESTART_INFO
                    if first
                    else FILE_FULL_DIRECTORY_INFO,
                    buffer,
                    len(buffer),
                )
                first = False
                if not success:
                    error = ctypes.get_last_error()
                    if error == ERROR_NO_MORE_FILES:
                        break
                    raise ctypes.WinError(error)
                offset = 0
                while True:
                    next_offset = ctypes.c_uint32.from_buffer(buffer, offset).value
                    attributes = ctypes.c_uint32.from_buffer(buffer, offset + 56).value
                    name_length = ctypes.c_uint32.from_buffer(buffer, offset + 60).value
                    name = ctypes.wstring_at(
                        ctypes.addressof(buffer) + offset + 68,
                        name_length // 2,
                    )
                    if name not in {".", ".."}:
                        is_directory = bool(attributes & FILE_ATTRIBUTE_DIRECTORY)
                        is_reparse = bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)
                        entries.append(
                            DirectoryEntry(
                                name,
                                is_directory,
                                not is_directory,
                                is_reparse,
                            )
                        )
                    if next_offset == 0:
                        break
                    offset += int(next_offset)
            return sorted(entries, key=lambda item: item.name)

        entries = []
        with os.scandir(self._handle) as iterator:
            for entry in iterator:
                file_stat = entry.stat(follow_symlinks=False)
                entries.append(
                    DirectoryEntry(
                        entry.name,
                        stat.S_ISDIR(file_stat.st_mode),
                        stat.S_ISREG(file_stat.st_mode),
                        stat.S_ISLNK(file_stat.st_mode),
                    )
                )
        return sorted(entries, key=lambda item: item.name)


class DirectoryChain:
    """Retains every verified directory handle from a root to one parent."""

    def __init__(
        self,
        handles: Sequence[DirectoryHandle],
        created: Sequence[Tuple[int, str]],
    ):
        self.handles = list(handles)
        self.created = list(created)
        self._closed = False

    @property
    def parent(self) -> DirectoryHandle:
        if self._closed:
            raise ValueError("directory chain is closed")
        return self.handles[-1]

    def cleanup_created(self) -> None:
        for parent_index, name in reversed(self.created):
            child_index = parent_index + 1
            if child_index < len(self.handles):
                self.handles[child_index].close()
            try:
                self.handles[parent_index].remove_directory(name)
            except (FileNotFoundError, OSError):
                pass
        self.created.clear()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for handle in reversed(self.handles):
            handle.close()


def open_directory_chain(
    root: Path,
    directory_parts: Sequence[str],
    *,
    create: bool = False,
) -> DirectoryChain:
    handles = [DirectoryHandle.open_root(root)]
    created: List[Tuple[int, str]] = []
    try:
        for part in directory_parts:
            child, was_created = handles[-1].open_directory(part, create=create)
            if was_created:
                created.append((len(handles) - 1, part))
            handles.append(child)
    except BaseException:
        for handle in reversed(handles):
            handle.close()
        raise
    return DirectoryChain(handles, created)


def snapshot_relative(root: Path, relative_path: str) -> FileSnapshot:
    parts = relative_path.split("/")
    chain = open_directory_chain(root, parts[:-1])
    try:
        return chain.parent.snapshot(parts[-1])
    finally:
        chain.close()


def relative_exists(root: Path, relative_path: str) -> bool:
    parts = relative_path.split("/")
    try:
        chain = open_directory_chain(root, parts[:-1])
    except FileNotFoundError:
        return False
    try:
        return chain.parent.exists(parts[-1])
    finally:
        chain.close()
