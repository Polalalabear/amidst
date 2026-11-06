"""Read-only Windows path open with held, non-replaceable directory handles.

This module never falls back to a path-based Python open on Windows.  The
caller still owns content length and SHA-256 validation after opening.
"""

from __future__ import annotations

import ntpath
import os
from pathlib import Path


REPARSE_POINT = 0x400
DIRECTORY = 0x10
FILE_TYPE_DISK = 1


class UnsafeWindowsPath(OSError):
    pass


def posix_read_flags(*, nonblock: bool = False, platform_os=os) -> int:
    """Do not turn missing POSIX no-follow flags into an ordinary path open."""
    if platform_os.name == 'nt' or not hasattr(platform_os, 'O_NOFOLLOW'):
        raise UnsafeWindowsPath('Atomic no-follow open unavailable')
    if nonblock and not hasattr(platform_os, 'O_NONBLOCK'):
        raise UnsafeWindowsPath('Nonblocking no-follow open unavailable')
    return (platform_os.O_RDONLY | platform_os.O_NOFOLLOW
            | (platform_os.O_NONBLOCK if nonblock else 0)
            | getattr(platform_os, 'O_BINARY', 0))


def posix_create_flags(*, platform_os=os) -> int:
    if platform_os.name == 'nt' or not hasattr(platform_os, 'O_NOFOLLOW'):
        raise UnsafeWindowsPath('Atomic no-follow create unavailable')
    return (platform_os.O_WRONLY | platform_os.O_CREAT | platform_os.O_EXCL
            | platform_os.O_NOFOLLOW | getattr(platform_os, 'O_BINARY', 0))


def _canonical(path: str) -> str:
    if path.startswith('\\\\?\\UNC\\'):
        path = '\\\\' + path[8:]
    elif path.startswith('\\\\?\\'):
        path = path[4:]
    return ntpath.normcase(ntpath.normpath(path))


def _components(path: str) -> list[str]:
    path = ntpath.abspath(path)
    drive, tail = ntpath.splitdrive(path)
    if not drive or not tail.startswith('\\') or drive.startswith('\\'):
        raise UnsafeWindowsPath('A local absolute Windows path is required')
    names = tail.strip('\\').split('\\') if tail.strip('\\') else []
    if any(name in ('', '.', '..') for name in names):
        raise UnsafeWindowsPath('Noncanonical Windows path')
    result = [drive + '\\']
    for name in names:
        result.append(ntpath.join(result[-1], name))
    return result


def _open_windows_regular(path: str, root: str, backend) -> int:
    """Validate every held component, then transfer the leaf handle to an fd.

    Each directory handle denies FILE_SHARE_WRITE and FILE_SHARE_DELETE.  A
    concurrent rename/junction substitution therefore cannot replace an
    already checked component before its child is opened.  Final paths are
    checked on handles before any file bytes are read.
    """
    paths = _components(path)
    root_parts = _components(root)
    if (len(paths) <= len(root_parts)
            or [_canonical(p) for p in paths[:len(root_parts)]]
            != [_canonical(p) for p in root_parts]):
        raise UnsafeWindowsPath('File outside declared root')
    handles = []
    leaf = None
    try:
        for index, component in enumerate(paths):
            is_dir = index != len(paths) - 1
            handle = backend.open(component, directory=is_dir)
            handles.append(handle)
            attrs = backend.attributes(handle)
            if attrs & REPARSE_POINT or bool(attrs & DIRECTORY) != is_dir:
                raise UnsafeWindowsPath('Reparse point or wrong file type')
            if _canonical(backend.final_path(handle)) != _canonical(component):
                raise UnsafeWindowsPath('Final path escaped declared component')
            if not is_dir:
                if backend.file_type(handle) != FILE_TYPE_DISK:
                    raise UnsafeWindowsPath('Non-disk file')
                leaf = handle
        fd = backend.to_fd(leaf)
        handles.pop()
        leaf = None
        return fd
    except (OSError, ValueError) as exc:
        raise UnsafeWindowsPath('Windows safe open rejected path') from exc
    finally:
        for handle in reversed(handles):
            backend.close(handle)


def _create_windows_regular(path: str, root: str, backend) -> int:
    """CREATE_NEW only, after locking and validating each ancestor directory."""
    paths = _components(path)
    root_parts = _components(root)
    if (len(paths) <= len(root_parts)
            or [_canonical(p) for p in paths[:len(root_parts)]]
            != [_canonical(p) for p in root_parts]):
        raise UnsafeWindowsPath('Created file outside declared root')
    handles = []
    try:
        for component in paths[:-1]:
            handle = backend.open(component, directory=True)
            handles.append(handle)
            attrs = backend.attributes(handle)
            if not attrs & DIRECTORY or attrs & REPARSE_POINT:
                raise UnsafeWindowsPath('Reparse point or non-directory ancestor')
            if _canonical(backend.final_path(handle)) != _canonical(component):
                raise UnsafeWindowsPath('Ancestor final path escaped')
        leaf = backend.create(paths[-1])
        handles.append(leaf)
        attrs = backend.attributes(leaf)
        if attrs & (DIRECTORY | REPARSE_POINT) or backend.file_type(leaf) != FILE_TYPE_DISK:
            raise UnsafeWindowsPath('Created leaf is not a regular disk file')
        if _canonical(backend.final_path(leaf)) != _canonical(paths[-1]):
            raise UnsafeWindowsPath('Created leaf final path escaped')
        fd = backend.to_write_fd(leaf)
        handles.pop()
        return fd
    except (OSError, ValueError) as exc:
        raise UnsafeWindowsPath('Windows safe create rejected path') from exc
    finally:
        for handle in reversed(handles):
            backend.close(handle)


class _WinAPI:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        import msvcrt

        self.ctypes = ctypes
        self.msvcrt = msvcrt
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
            wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
        self.kernel.GetFileAttributesW.restype = wintypes.DWORD
        self.kernel.GetFileInformationByHandle.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        self.kernel.GetFileInformationByHandle.restype = wintypes.BOOL
        self.kernel.GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR,
            wintypes.DWORD, wintypes.DWORD]
        self.kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
        self.kernel.GetFileType.argtypes = [wintypes.HANDLE]
        self.kernel.GetFileType.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.restype = wintypes.BOOL

        class FileInformation(ctypes.Structure):
            _fields_ = [('attributes', wintypes.DWORD), ('created_low', wintypes.DWORD),
                ('created_high', wintypes.DWORD), ('accessed_low', wintypes.DWORD),
                ('accessed_high', wintypes.DWORD), ('written_low', wintypes.DWORD),
                ('written_high', wintypes.DWORD), ('volume_serial', wintypes.DWORD),
                ('size_high', wintypes.DWORD), ('size_low', wintypes.DWORD),
                ('links', wintypes.DWORD), ('index_high', wintypes.DWORD),
                ('index_low', wintypes.DWORD)]
        self.FileInformation = FileInformation

    def open(self, path: str, *, directory: bool):
        # FILE_READ_ATTRIBUTES | GENERIC_READ for files; no data access for directories.
        access = 0x80 if directory else 0x80000000 | 0x80
        # FILE_SHARE_READ only; OPEN_EXISTING; OPEN_REPARSE_POINT | BACKUP_SEMANTICS.
        handle = self.kernel.CreateFileW(path, access, 1, None, 3, 0x00200000 | 0x02000000, None)
        if handle in (None, 0, self.ctypes.c_void_p(-1).value):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return handle

    def create(self, path: str):
        # GENERIC_WRITE | FILE_READ_ATTRIBUTES, FILE_SHARE_READ, CREATE_NEW.
        handle = self.kernel.CreateFileW(path, 0x40000000 | 0x80, 1, None, 1,
                                         0x00200000 | 0x02000000, None)
        if handle in (None, 0, self.ctypes.c_void_p(-1).value):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return handle

    def attributes(self, handle):
        info = self.FileInformation()
        if not self.kernel.GetFileInformationByHandle(handle, self.ctypes.byref(info)):
            raise self.ctypes.WinError(self.ctypes.get_last_error())
        return info.attributes

    def final_path(self, handle):
        size = self.kernel.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not size or size > 32767:
            raise UnsafeWindowsPath('Final path unavailable')
        buffer = self.ctypes.create_unicode_buffer(size + 1)
        got = self.kernel.GetFinalPathNameByHandleW(handle, buffer, size + 1, 0)
        if not got or got > size:
            raise UnsafeWindowsPath('Final path changed')
        return buffer.value

    def file_type(self, handle):
        return self.kernel.GetFileType(handle)

    def to_fd(self, handle):
        return self.msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)

    def to_write_fd(self, handle):
        return self.msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)

    def close(self, handle):
        self.kernel.CloseHandle(handle)


def open_regular(path: Path, *, root: Path | None = None) -> int:
    """Return a read-only fd or fail closed; caller must close the fd."""
    if os.name != 'nt':
        raise UnsafeWindowsPath('Windows safe open called on another platform')
    path = Path(path)
    root = Path(root) if root is not None else Path(path.anchor)
    if not path.is_absolute() or not root.is_absolute():
        raise UnsafeWindowsPath('Absolute path and root required')
    return _open_windows_regular(str(path), str(root), _WinAPI())


def create_regular(path: Path, *, root: Path) -> int:
    """Return write-only fd for a new Windows file, or fail closed."""
    if os.name != 'nt':
        raise UnsafeWindowsPath('Windows safe create called on another platform')
    path, root = Path(path), Path(root)
    if not path.is_absolute() or not root.is_absolute():
        raise UnsafeWindowsPath('Absolute path and root required')
    return _create_windows_regular(str(path), str(root), _WinAPI())
