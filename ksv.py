#!/usr/bin/env python
# should I force a new line before displaying message if there isn't one?
import subprocess
import threading
import keyboard
import sys
import time
import signal
import os
import argparse
import datetime

RESTART_HOTKEY = "ctrl+windows+r"
STOP_HOTKEY = "ctrl+windows+q"

child = None
restart_requested = threading.Event()
stop_requested = threading.Event()
shutdown_requested = threading.Event()

QUIET = False
QUIET_STARTUP = False

YELLOW = "\033[33m"
CYAN = "\033[36m"
NORMAL_COLOR = "\033[39m"
RED_BOLD = "\033[1;91m"
WHITE_BOLD = "\033[1;37m"
RESET = "\033[22;39m"


def current_timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-4]


def is_linux():
    return os.name == "posix" and sys.platform.startswith("linux")


def sup_print(*args, **kwargs):
    t = current_timestamp()
    print(f"{YELLOW}[supervisor]{CYAN}[{t}]{NORMAL_COLOR}", *args, **kwargs)


def sup_print_runtime(*args, **kwargs):
    if not QUIET:
        sup_print(*args, **kwargs)


def get_child_user(run_as_root: bool) -> str:
    """
    Return the username the CHILD process will run as.
    Cross-platform safe.
    """
    if not is_linux():
        return os.getlogin()

    if run_as_root:
        return "root"

    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        return sudo_user

    # Fallback: effective user
    try:
        import pwd  # Linux-only
        return pwd.getpwuid(os.geteuid()).pw_name
    except Exception:
        return "unknown"


def drop_privileges_preexec():
    """
    Drop root privileges to original sudo user.
    Linux only, runs in child before exec().
    """
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")

    if not sudo_uid or not sudo_gid:
        return

    os.setgid(int(sudo_gid))
    os.setuid(int(sudo_uid))


def start_child(command, run_as_root):
    global child

    preexec = None
    if is_linux() and os.geteuid() == 0 and not run_as_root:
        preexec = drop_privileges_preexec

    child = subprocess.Popen(
        command,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True,
        preexec_fn=preexec,
    )


def stop_child():
    global child
    if child and child.poll() is None:
        try:
            child.send_signal(signal.SIGTERM)
            child.wait(timeout=2)
        except Exception:
            child.kill()
    child = None


def on_restart_hotkey():
    restart_requested.set()


def on_stop_hotkey():
    if child is not None and not stop_requested.is_set():
        stop_requested.set()


def supervisor_loop(command, run_as_root):
    global child

    start_child(command, run_as_root)

    while not shutdown_requested.is_set():

        while child and child.poll() is None:

            if stop_requested.is_set():
                stop_requested.clear()
                sup_print_runtime("stopping")
                stop_child()
                break

            if restart_requested.is_set():
                restart_requested.clear()
                stop_requested.clear()
                sup_print_runtime("restarting")
                stop_child()
                start_child(command, run_as_root)

            time.sleep(0.05)

        if child and child.poll() is not None:
            sup_print_runtime(f"process exited with code {child.returncode}")
            child = None

        if child is None:
            if restart_requested.is_set():
                restart_requested.clear()
                sup_print_runtime("starting")
                start_child(command, run_as_root)
            else:
                time.sleep(0.1)


def main():
    global QUIET, QUIET_STARTUP

    parser = argparse.ArgumentParser(
        description="A simple tool to easily run, restart, terminate, and rerun a process, based on a keybinding to make development easier.")
    parser.add_argument(
        "-r",
        "--root",
        action="store_true",
        help="run child process as root (Linux only)",
    )
    parser.add_argument(
        "-n",
        "--no-ansii",
        action="store_true",
        help="removes all ansii sequences from supervisor",
    )
    parser.add_argument(
        "-q",
        action="count",
        default=0,
        help="suppress supervisor runtime output (-qq suppresses startup too)",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    QUIET = args.q >= 1
    QUIET_STARTUP = args.q >= 2

    if not args.command:
        if not QUIET:
            print(
                "[supervisor] Usage: sudo python reloader.py [-r] [-q|-qq] <command...>")
        sys.exit(1)

    keyboard.add_hotkey(RESTART_HOTKEY, on_restart_hotkey)
    keyboard.add_hotkey(STOP_HOTKEY, on_stop_hotkey)

    global YELLOW, CYAN, NORMAL_COLOR, RED_BOLD, WHITE_BOLD, RESET
    if args.no_ansii:
        YELLOW = ""
        CYAN = ""
        NORMAL_COLOR = ""
        RED_BOLD = ""
        WHITE_BOLD = ""
        RESET = ""
    if not QUIET_STARTUP:
        child_color = WHITE_BOLD
        if args.root:
            child_color = RED_BOLD

        user = get_child_user(args.root)
        sup_print(f"Child will run as user: {child_color}{user}{RESET}")

        sup_print(f"Command: {WHITE_BOLD}{' '.join(args.command)}{RESET}")

        k = RESTART_HOTKEY
        sup_print(f"Restart hotkey: {WHITE_BOLD}{k}{RESET}")
        k = STOP_HOTKEY
        sup_print(f"Stop hotkey: {WHITE_BOLD}{k}{RESET}")
        sup_print(f"Press {WHITE_BOLD}ctrl+c{RESET} to quit supervisor\n")

    try:
        supervisor_loop(args.command, args.root)
    except KeyboardInterrupt:
        sup_print_runtime("shutting down")
    finally:
        shutdown_requested.set()
        stop_child()


if __name__ == "__main__":
    main()
