import select
import ctypes
from ctypes import c_void_p, c_char_p, c_int


libudev = None


def set_up_libudev():
    libudev = ctypes.CDLL("libudev.so.1")

    libudev.udev_new.restype = c_void_p

    libudev.udev_unref.argtypes = [c_void_p]

    libudev.udev_monitor_new_from_netlink.argtypes = [c_void_p, c_char_p]
    libudev.udev_monitor_new_from_netlink.restype = c_void_p

    libudev.udev_monitor_filter_add_match_subsystem_devtype.argtypes = [
        c_void_p, c_char_p, c_char_p
    ]

    libudev.udev_monitor_enable_receiving.argtypes = [c_void_p]

    libudev.udev_monitor_get_fd.argtypes = [c_void_p]
    libudev.udev_monitor_get_fd.restype = c_int

    libudev.udev_monitor_receive_device.argtypes = [c_void_p]
    libudev.udev_monitor_receive_device.restype = c_void_p

    libudev.udev_device_get_action.argtypes = [c_void_p]
    libudev.udev_device_get_action.restype = c_char_p

    libudev.udev_device_get_devnode.argtypes = [c_void_p]
    libudev.udev_device_get_devnode.restype = c_char_p

    libudev.udev_device_unref.argtypes = [c_void_p]

    return libudev


def monitor_on_add(libudev, mon, on_add):
    fd = libudev.udev_monitor_get_fd(mon)

    while True:
        select.select([fd], [], [])

        dev = libudev.udev_monitor_receive_device(mon)
        if not dev:
            continue

        action = libudev.udev_device_get_action(dev)
        if not action or action != b"add":
            libudev.udev_device_unref(dev)
            continue

        devnode = libudev.udev_device_get_devnode(dev)
        if devnode:
            on_add(devnode.decode())

        libudev.udev_device_unref(dev)


def create_udev_monitor(libudev):
    udev = libudev.udev_new()
    if not udev:
        raise RuntimeError("udev_new failed")

    mon = libudev.udev_monitor_new_from_netlink(udev, b"udev")
    if not mon:
        raise RuntimeError("udev_monitor_new_from_netlink failed")

    libudev.udev_monitor_filter_add_match_subsystem_devtype(
        mon, b"input", None
    )

    libudev.udev_monitor_enable_receiving(mon)
    fd = libudev.udev_monitor_get_fd(mon)

    return udev, mon, fd


if __name__ == "__main__":

    def on_add(devnode):
        print(f"{devnode}")
    libudev = set_up_libudev()
    udev, mon, fd = create_udev_monitor(libudev)

    try:
        monitor_on_add(libudev, mon, on_add)
    finally:
        libudev.udev_unref(udev)
