from __future__ import annotations

import copy
import ctypes
import sys
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class _BufferHandle:
    buf: ctypes.Array
    size: int
    locked: bool


class SecureBuffer:
    __slots__ = ('_handle',)

    _libc: ClassVar[object | None] = None
    _libc_checked: ClassVar[bool] = False

    def __init__(self, payload: str | bytes | bytearray | memoryview):
        if isinstance(payload, str):
            raw = payload.encode('utf-8')
        else:
            raw = bytes(payload)
        buf = ctypes.create_string_buffer(len(raw))
        if raw:
            ctypes.memmove(ctypes.addressof(buf), raw, len(raw))
        locked = self._mlock(buf, len(raw))
        self._handle = _BufferHandle(buf=buf, size=len(raw), locked=locked)

    @classmethod
    def _get_libc(cls):
        if cls._libc_checked:
            return cls._libc
        cls._libc_checked = True
        if not sys.platform.startswith('linux'):
            cls._libc = None
            return None
        try:
            cls._libc = ctypes.CDLL('libc.so.6', use_errno=True)
        except OSError:
            cls._libc = None
        return cls._libc

    @classmethod
    def _mlock(cls, buf: ctypes.Array, size: int) -> bool:
        if size <= 0:
            return False
        libc = cls._get_libc()
        if libc is None:
            return False
        try:
            rc = libc.mlock(ctypes.c_void_p(ctypes.addressof(buf)), ctypes.c_size_t(size))
            return rc == 0
        except Exception:
            return False

    @classmethod
    def _munlock(cls, buf: ctypes.Array, size: int) -> None:
        if size <= 0:
            return
        libc = cls._get_libc()
        if libc is None:
            return
        try:
            libc.munlock(ctypes.c_void_p(ctypes.addressof(buf)), ctypes.c_size_t(size))
        except Exception:
            return

    @property
    def size(self) -> int:
        return self._handle.size

    @property
    def locked(self) -> bool:
        return self._handle.locked

    def to_bytes(self) -> bytes:
        if self._handle.size <= 0:
            return b''
        return ctypes.string_at(ctypes.addressof(self._handle.buf), self._handle.size)

    def to_text(self, encoding: str = 'utf-8') -> str:
        return self.to_bytes().decode(encoding)

    def zero(self) -> None:
        if self._handle.size > 0:
            ctypes.memset(ctypes.addressof(self._handle.buf), 0, self._handle.size)

    def __bool__(self) -> bool:
        return self._handle.size > 0

    def __repr__(self) -> str:
        return '[REDACTED]'

    __str__ = __repr__

    def __reduce_ex__(self, protocol):
        raise TypeError('SecureBuffer cannot be pickled')

    def __copy__(self):
        raise TypeError('SecureBuffer cannot be copied')

    def __deepcopy__(self, memo):
        raise TypeError('SecureBuffer cannot be copied')

    def __del__(self):
        handle = getattr(self, '_handle', None)
        if handle is None:
            return
        try:
            self.zero()
        finally:
            if handle.locked:
                self._munlock(handle.buf, handle.size)


__all__ = ['SecureBuffer']
