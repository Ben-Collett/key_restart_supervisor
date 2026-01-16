# -*- coding: utf-8 -*-
import re
from collections import namedtuple
import struct
from io import BufferedWriter
import os
import signal
import atexit
from time import time as now
from threading import Thread
from glob import glob
# from queue import Queue
from multiprocessing import Queue, Process

# l = long, H = unsigned short,I = unsigned int
event_bin_format = 'llHHI'

# Taken from include/linux/input.h
# https://www.kernel.org/doc/Documentation/input/event-codes.txt

# sync event
EV_SYN = 0x00
# key event
EV_KEY = 0x01
# mouse relative movement, like 5 left
EV_REL = 0x02
# abs position like touching a screen
EV_ABS = 0x03
# miscellanesus event
EV_MSC = 0x04


def make_uinput():
    if not os.path.exists('/dev/uinput'):
        raise IOError('No uinput module found.')

    from ._nixutils import make_keyboard
    # Requires uinput driver, but it's usually available.
    uinput = open("/dev/uinput", 'wb')

    make_keyboard(uinput)

    return uinput


class EventDevice(object):
    def __init__(self, path):
        self.path = path
        self._input_file = None
        self._output_file = None

    @property
    def input_file(self):
        if self._input_file is None:
            try:
                self._input_file: BufferedWriter = open(self.path, 'rb')
            except IOError as e:
                if e.strerror == 'Permission denied':
                    print(f"# ERROR: Failed to read device '{
                          self.path}'. You must be in the 'input' group to access global events. Use 'sudo usermod -a -G input USERNAME' to add user to the required group.")
                    exit()

        return self._input_file

    @property
    def output_file(self):
        if self._output_file is None:
            self._output_file = open(self.path, 'wb')
            atexit.register(self._output_file.close)
        return self._output_file

    def read_event(self):
        data = self.input_file.read(struct.calcsize(event_bin_format))
        seconds, microseconds, type, code, value = struct.unpack(
            event_bin_format, data)

        return seconds + microseconds / 1e6, type, code, value, self.path

    def write_event(self, type, code, value):
        integer, fraction = divmod(now(), 1)
        seconds = int(integer)
        microseconds = int(fraction * 1e6)
        data_event = struct.pack(
            event_bin_format, seconds, microseconds, type, code, value)

        # Send a sync event to ensure other programs update.
        sync_event = struct.pack(
            event_bin_format, seconds, microseconds, EV_SYN, 0, 0)

        self.output_file.write(data_event + sync_event)
        self.output_file.flush()


def device_reader_worker(device_paths, event_queue):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    devices = [EventDevice(p) for p in device_paths]

    def read_loop(device):
        while True:
            event_queue.put(device.read_event(), block=True)

    threads = []
    for d in devices:
        t = Thread(target=read_loop, args=(d,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()


class AggregatedEventDevice:
    def __init__(self, devices, output=None):
        self.event_queue = Queue()

        self.output = output  # stays in parent only
        paths = [d.path for d in devices]

        self.process = Process(
            target=device_reader_worker,
            args=(paths, self.event_queue),
            daemon=True,
        )
        self.process.start()

    def read_event(self):
        # Blocks until an event is available
        return self.event_queue.get()

    def write_event(self, type, code, value):
        self.output.write_event(type, code, value)


DeviceDescription = namedtuple(
    'DeviceDescription', 'event_file is_mouse is_keyboard')
device_pattern = r"""N: Name="([^"]+?)".+?H: Handlers=([^\n]+)"""


def list_devices_from_proc(type_name):
    try:
        with open('/proc/bus/input/devices') as f:
            description = f.read()
    except FileNotFoundError:
        return

    for name, handlers in re.findall(device_pattern, description, re.DOTALL):
        path = '/dev/input/event' + re.search(r'event(\d+)', handlers).group(1)
        if type_name in handlers:
            yield EventDevice(path)


def list_devices_from_by_id(name_suffix, by_id=True):
    for path in glob('/dev/input/{}/*-event-{}'.format('by-id' if by_id else 'by-path', name_suffix)):
        yield EventDevice(path)


def aggregate_devices(type_name):
    # Some systems have multiple keyboards with different range of allowed keys
    # on each one, like a notebook with a "keyboard" device exclusive for the
    # power button. Instead of figuring out which keyboard allows which key to
    # send events, we create a fake device and send all events through there.
    try:
        uinput = make_uinput()
        fake_device = EventDevice('uinput Fake Device')
        fake_device._input_file = uinput
        fake_device._output_file = uinput
    except IOError:
        import warnings
        warnings.warn(
            'Failed to create a device file using `uinput` module. Sending of events may be limited or unavailable depending on plugged-in devices.', stacklevel=2)
        fake_device = None

    # We don't aggregate devices from different sources to avoid
    # duplicates.

    devices_from_proc = list(list_devices_from_proc(type_name))
    if devices_from_proc:
        return AggregatedEventDevice(devices_from_proc, output=fake_device)

    # breaks on mouse for virtualbox
    # was getting /dev/input/by-id/usb-VirtualBox_USB_Tablet-event-mouse
    devices_from_by_id = list(list_devices_from_by_id(type_name)) or list(
        list_devices_from_by_id(type_name, by_id=False))
    if devices_from_by_id:
        return AggregatedEventDevice(devices_from_by_id, output=fake_device)

    # If no keyboards were found we can only use the fake device to send keys.
    assert fake_device
    return fake_device
