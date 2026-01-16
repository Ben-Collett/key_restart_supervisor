import os
import fcntl
import threading
import ctypes
import time
from ._nixutils import is_our_virtual_keyboard

# =========================
# ioctl constants
# =========================

EVIOCGRAB = 0x40044590
EVIOCGBIT_EV = 0x80084520
EVIOCGBIT_KEY = 0x80084521

EV_KEY = 0x01
KEY_A = 30

# =========================
# global state
# =========================

_grabbed = {}          # path -> fd
_auto_thread = None
_auto_stop = threading.Event()

# =========================
# helpers
# =========================


def _bit_is_set(buf, bit):
    return buf[bit // 8] & (1 << (bit % 8))


def _is_keyboard(fd):
    """
    Detects if an event device is a keyboard by capability.
    """
    ev_bits = bytearray(32)
    fcntl.ioctl(fd, EVIOCGBIT_EV, ev_bits)

    if not _bit_is_set(ev_bits, EV_KEY):
        return False

    key_bits = bytearray(96)
    fcntl.ioctl(fd, EVIOCGBIT_KEY, key_bits)

    return _bit_is_set(key_bits, KEY_A)


# =========================
# grab / release single
# =========================

def grab_keyboard(path):
    if path in _grabbed:
        return

    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, EVIOCGRAB, 1)
    _grabbed[path] = fd


def release_keyboard(path):
    fd = _grabbed.pop(path, None)
    if fd is None:
        return

    try:
        fcntl.ioctl(fd, EVIOCGRAB, 0)
    finally:
        os.close(fd)


# =========================
# grab / release all
# =========================

def grab_all_keyboards():
    for name in os.listdir("/dev/input"):
        if not name.startswith("event"):
            continue

        path = f"/dev/input/{name}"

        try:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            continue

        try:
            if _is_keyboard(fd):
                fcntl.ioctl(fd, EVIOCGRAB, 1)
                _grabbed[path] = fd
            else:
                os.close(fd)
        except Exception:
            os.close(fd)


def release_all_keyboards():
    for path in list(_grabbed.keys()):
        release_keyboard(path)


# =========================
# auto-grab via inotify
# =========================

libc = ctypes.CDLL("libc.so.6")

IN_CREATE = 0x00000100


class InotifyEvent(ctypes.Structure):
    _fields_ = [
        ("wd", ctypes.c_int),
        ("mask", ctypes.c_uint32),
        ("cookie", ctypes.c_uint32),
        ("len", ctypes.c_uint32),
    ]


def _auto_grab_loop():
    fd = libc.inotify_init1(0)
    wd = libc.inotify_add_watch(fd, b"/dev/input", IN_CREATE)

    while not _auto_stop.is_set():
        try:
            n = os.read(fd, 4096)
        except BlockingIOError:
            time.sleep(0.05)
            continue

        offset = 0
        while offset < len(n):
            ev = InotifyEvent.from_buffer_copy(n, offset)
            offset += ctypes.sizeof(InotifyEvent)

            name = n[offset:offset + ev.len].rstrip(b"\0").decode()
            offset += ev.len

            if name.startswith("event"):
                path = f"/dev/input/{name}"
                try:
                    grab_keyboard(path)
                except Exception:
                    pass

    libc.inotify_rm_watch(fd, wd)
    os.close(fd)


def start_auto_grab():
    global _auto_thread
    if _auto_thread and _auto_thread.is_alive():
        return

    _auto_stop.clear()
    _auto_thread = threading.Thread(target=_auto_grab_loop, daemon=True)
    _auto_thread.start()


def stop_auto_grab():
    _auto_stop.set()
