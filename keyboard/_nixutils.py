import fcntl
import struct
from io import BufferedWriter
import os
from ._nixcommon import EV_KEY

USB_BUS_TYPE = 0x03
VENDOR = 0xFEED
PRODUCT = 0xBEEF
VERSION = 1
NAME = b"Virtual Keyboard\x00"


def _make_support_key_events(uinput: BufferedWriter):
    UI_SET_EVBIT = 0x40045564
    fcntl.ioctl(uinput, UI_SET_EVBIT, EV_KEY)


def _make_support_standard_keys(uinput: BufferedWriter):
    UI_SET_KEYBIT = 0x40045565
    for i in range(256):
        fcntl.ioctl(uinput, UI_SET_KEYBIT, i)


def _make_support_keys(uinput: BufferedWriter):
    _make_support_key_events(uinput)
    _make_support_standard_keys(uinput)


def _write_metadata(uinput: BufferedWriter):

    uinput_user_dev_struct_fmt = "80sHHHHI" + "64i" * 4
    abs_vals = [0] * 64

    data = struct.pack(
        uinput_user_dev_struct_fmt,
        NAME,
        USB_BUS_TYPE,
        VENDOR,
        PRODUCT,
        VERSION,
        0,          # ff_effects_max->  not used so zeroed
        *abs_vals,  # absmax -> for joysticks so zeroed
        *abs_vals,  # absmin -> for josysticks so zeroed
        *abs_vals,  # absfuzz -> for joysticks and worn sensors so zeroed
        *abs_vals,  # absflat-> for centering joysticks, zeroed
    )

    uinput.write(data)


def _create(uinput: BufferedWriter):
    UI_DEV_CREATE = 0x5501
    uinput.flush()  # Without this you may get Errno 22: Invalid argument.
    fcntl.ioctl(uinput, UI_DEV_CREATE)


def destroy(uinput: BufferedWriter):
    UI_DEV_DESTROY = 0x5502
    fcntl.ioctl(uinput, UI_DEV_DESTROY)


def make_keyboard(uinput: BufferedWriter):
    _make_support_keys(uinput)
    _write_metadata(uinput)
    _create(uinput)


def is_our_virtual_keyboard(path):
    event = os.path.basename(path)
    base = f"/sys/class/input/{event}/device"

    try:
        with open(f"{base}/name", "r") as f:
            name = f.read().strip()

        with open(f"{base}/id/vendor") as f:
            vendor = int(f.read().strip(), 16)
        with open(f"{base}/id/product") as f:
            product = int(f.read().strip(), 16)

    except OSError:
        return False

    return (
        name == NAME
        and vendor == VENDOR
        and product == PRODUCT
    )
