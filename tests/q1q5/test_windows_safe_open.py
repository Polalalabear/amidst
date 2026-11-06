"""Synthetic WinAPI handle checks; no Windows host or original data required."""

import ntpath
import ctypes
from types import SimpleNamespace

import pytest

from amidst.q1q5.windows_safe_open import (
    DIRECTORY, FILE_TYPE_DISK, REPARSE_POINT, UnsafeWindowsPath,
    _open_windows_regular,
    _WinAPI,
    posix_read_flags,
)


class Backend:
    def __init__(self, *, changed=None, attrs=None, file_type=FILE_TYPE_DISK,
                 fail_at=None):
        self.changed = changed or {}
        self.attrs = attrs or {}
        self.kind = file_type
        self.fail_at = fail_at
        self.opened = []
        self.closed = []
        self.transferred = []

    def open(self, path, *, directory):
        if path == self.fail_at:
            raise OSError('synthetic open failure')
        self.opened.append((path, directory))
        return path

    def attributes(self, handle):
        return self.attrs.get(handle, DIRECTORY if handle != r'C:\safe\file.json' else 0)

    def final_path(self, handle):
        return self.changed.get(handle, '\\\\?\\' + handle)

    def file_type(self, handle):
        return self.kind

    def to_fd(self, handle):
        self.transferred.append(handle)
        return 42

    def close(self, handle):
        self.closed.append(handle)


PATH = r'C:\safe\file.json'
ROOT = r'C:\safe'


def test_holds_all_ancestors_until_leaf_transferred():
    backend = Backend()
    assert _open_windows_regular(PATH, ROOT, backend) == 42
    assert backend.opened == [('C:\\', True), (ROOT, True), (PATH, False)]
    assert backend.transferred == [PATH]
    assert backend.closed == [ROOT, 'C:\\']


@pytest.mark.parametrize('changed,attrs,kind', [
    ({ROOT: r'\\?\C:\outside'}, None, FILE_TYPE_DISK),
    ({PATH: r'\\?\C:\outside\file.json'}, None, FILE_TYPE_DISK),
    (None, {ROOT: DIRECTORY | REPARSE_POINT}, FILE_TYPE_DISK),
    (None, {PATH: REPARSE_POINT}, FILE_TYPE_DISK),
    (None, None, 2),
])
def test_reparse_swap_escape_and_nonregular_fail_before_transfer(changed, attrs, kind):
    backend = Backend(changed=changed, attrs=attrs, file_type=kind)
    with pytest.raises(UnsafeWindowsPath):
        _open_windows_regular(PATH, ROOT, backend)
    assert backend.transferred == []
    assert backend.closed == [path for path, _ in reversed(backend.opened)]


def test_open_failure_closes_held_ancestors():
    backend = Backend(fail_at=PATH)
    with pytest.raises(UnsafeWindowsPath):
        _open_windows_regular(PATH, ROOT, backend)
    assert backend.closed == [ROOT, 'C:\\']


def test_fd_transfer_failure_closes_leaf_and_all_ancestors():
    backend = Backend()
    def fail_transfer(_):
        raise OSError('synthetic transfer failure')
    backend.to_fd = fail_transfer
    with pytest.raises(UnsafeWindowsPath):
        _open_windows_regular(PATH, ROOT, backend)
    assert backend.closed == [PATH, ROOT, 'C:\\']


def test_declared_root_enforced_before_any_handle_open():
    backend = Backend()
    with pytest.raises(UnsafeWindowsPath):
        _open_windows_regular(ntpath.join(ROOT, '..', 'outside.json'), ROOT, backend)
    assert backend.opened == []


def test_winapi_open_uses_no_follow_and_no_delete_or_write_share():
    calls = []
    api = object.__new__(_WinAPI)
    api.ctypes = ctypes
    api.kernel = SimpleNamespace(CreateFileW=lambda *args: calls.append(args) or 123)
    assert api.open(PATH, directory=False) == 123
    assert api.open(ROOT, directory=True) == 123
    file_call, dir_call = calls
    for call in calls:
        assert call[2] == 1  # FILE_SHARE_READ only
        assert call[4] == 3  # OPEN_EXISTING
        assert call[5] & 0x00200000  # FILE_FLAG_OPEN_REPARSE_POINT
        assert call[5] & 0x02000000  # FILE_FLAG_BACKUP_SEMANTICS
    assert file_call[1] & 0x80000000  # GENERIC_READ
    assert not dir_call[1] & 0x80000000


def test_missing_posix_atomic_flags_fail_closed_before_path_open():
    no_follow = SimpleNamespace(name='posix', O_RDONLY=0)
    with pytest.raises(UnsafeWindowsPath, match='no-follow'):
        posix_read_flags(platform_os=no_follow)
    no_nonblock = SimpleNamespace(name='posix', O_RDONLY=0, O_NOFOLLOW=1)
    with pytest.raises(UnsafeWindowsPath, match='Nonblocking'):
        posix_read_flags(nonblock=True, platform_os=no_nonblock)
