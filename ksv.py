#!/usr/bin/env python
# should I force a new line before displaying message if there isn't one?
import argparse
import datetime
import os
import signal
import subprocess
import sys
import termios
import threading
import time
from pathlib import Path

import tomllib

import keyboard
from config import Config
from config_manager import ConfigManager

child = None
restart_requested = threading.Event()
stop_requested = threading.Event()
shutdown_requested = threading.Event()
duration_timer = None
config_path = None
_config: Config | None = None

QUIET = False
QUIET_STARTUP = False
_current_command = None
_run_as_root = False
_duration_seconds = None
_duration_str = None
_force_kill = False
_tty_restore_enabled = True
_saved_terminal = None

YELLOW = "\033[33m"
CYAN = "\033[36m"
NORMAL_COLOR = "\033[39m"
RED_BOLD = "\033[1;91m"
WHITE_BOLD = "\033[1;37m"
RESET = "\033[22;39m"


def current_timestamp():
    return datetime.datetime.now().strftime("%H:%M:%S.%f")[:-4]


def _parse_duration(duration_str):
    """
    Parse a duration string to seconds (float).
    '5' -> 5.0 seconds
    '500ms' -> 0.5 seconds
    """
    if duration_str is None:
        return None
    duration_str = duration_str.strip().lower()
    if duration_str.endswith("ms"):
        return float(duration_str[:-2]) / 1000.0
    else:
        return float(duration_str)


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


def start_child(command, run_as_root, duration=None):
    global child

    if is_linux() and os.geteuid() == 0 and not run_as_root:
        user = get_child_user(run_as_root)
        runuser_cmd = ["runuser", "-u", user, "--"] + command
        child = subprocess.Popen(
            runuser_cmd,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
        )
    else:
        child = subprocess.Popen(
            command,
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
        )

    if duration:
        start_duration_timer(duration)


def _read_children(pid):
    try:
        with open(f"/proc/{pid}/task/{pid}/children") as f:
            return [int(c) for c in f.read().split()]
    except (FileNotFoundError, ProcessLookupError, PermissionError, ValueError):
        return []


def _descendants(pid):
    """Walk /proc to find all descendant PIDs of pid (Linux only)."""
    result = []
    frontier = [pid]
    while frontier:
        nxt = []
        for p in frontier:
            for c in _read_children(p):
                result.append(c)
                nxt.append(c)
        frontier = nxt
    return result


def _kill_pids(pids, sig):
    for p in pids:
        try:
            os.kill(p, sig)
        except OSError:
            pass


def stop_child():
    global child, duration_timer
    if duration_timer:
        duration_timer.cancel()
        duration_timer = None
    if child and child.poll() is None:
        if _force_kill:
            _kill_pids(_descendants(child.pid), signal.SIGKILL)
            child.kill()
            child.wait()
        else:
            descendants = _descendants(child.pid)
            _kill_pids(descendants, signal.SIGTERM)
            if not descendants:
                child.send_signal(signal.SIGTERM)
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                _kill_pids(_descendants(child.pid), signal.SIGKILL)
                child.kill()
                child.wait()
    child = None
    _restore_terminal()


def start_duration_timer(seconds):
    global duration_timer
    if duration_timer:
        duration_timer.cancel()
    duration_timer = threading.Timer(seconds, on_duration_timeout)
    duration_timer.daemon = True
    duration_timer.start()


def on_duration_timeout():
    global duration_timer
    duration_timer = None
    sup_print_runtime(f"duration timeout ({_duration_str}), stopping")
    stop_requested.set()


def _save_terminal():
    global _saved_terminal
    if os.name != "posix" or not os.isatty(0):
        return
    if not _tty_restore_enabled:
        return
    if _saved_terminal is not None:
        return
    try:
        _saved_terminal = termios.tcgetattr(0)
    except Exception:
        pass


def _restore_terminal():
    global _saved_terminal
    if os.name != "posix" or not os.isatty(0):
        return
    if _saved_terminal is None:
        return
    try:
        termios.tcsetattr(0, termios.TCSADRAIN, _saved_terminal)
    except Exception:
        pass


def on_restart_hotkey():
    restart_requested.set()


def on_stop_hotkey():
    if child is not None and not stop_requested.is_set():
        stop_requested.set()


def on_clear_hotkey():
    if os.name == "nt":
        subprocess.run("cls")
    else:
        subprocess.run("clear")


def on_reload_hotkey():
    global _config, config_path
    assert _config is not None

    sup_print_runtime("reloading config")
    keyboard.unhook_all()

    data, path = _load_toml()
    config_path = path
    _config.update(data)

    _add_hotkey(_config.bindings.restart, on_restart_hotkey)
    _add_hotkey(_config.bindings.stop, on_stop_hotkey)
    _add_hotkey(_config.bindings.clear, on_clear_hotkey)
    _add_hotkey(_config.bindings.help, lambda: on_help_hotkey(_config))
    _add_hotkey(_config.bindings.reload, on_reload_hotkey)

    print_help_message(_current_command, _run_as_root,
                       QUIET_STARTUP, _config, config_path)


def _child_color(root):
    return RED_BOLD if root else WHITE_BOLD


def _print_help_info_item(item: str, command, root, config_path: str | None, config: Config):
    match item:
        case "user":
            user = get_child_user(root)
            sup_print(f"Child will run as user: {
                      _child_color(root)}{user}{RESET}")
        case "command":
            sup_print(f"Command: {WHITE_BOLD}{' '.join(command)}{RESET}")
        case "config":
            sup_print(f"Config path: {WHITE_BOLD}{config_path}{RESET}")
        case "restart":
            k = config.bindings.restart
            if k != "":
                sup_print(f"Restart hotkey: {WHITE_BOLD}{k}{RESET}")
        case "stop":
            k = config.bindings.stop
            if k != "":
                sup_print(f"Stop hotkey: {WHITE_BOLD}{k}{RESET}")
        case "clear":
            k = config.bindings.clear
            if k != "":
                sup_print(f"Clear hotkey: {WHITE_BOLD}{k}{RESET}")
        case "help":
            k = config.bindings.help
            if k != "":
                sup_print(f"Help hotkey: {WHITE_BOLD}{k}{RESET}")
        case "reload":
            k = config.bindings.reload
            if k != "":
                sup_print(f"Reload hotkey: {WHITE_BOLD}{k}{RESET}")
        case "terminate":
            sup_print(f"Press {WHITE_BOLD}ctrl+c{RESET} to quit supervisor")


def print_help_message(command, root, quiet_startup, config: Config, config_path: str | None):
    if quiet_startup:
        return

    for item in config.logging.help_info:
        _print_help_info_item(item, command, root, config_path, config)
    print()


def on_help_hotkey(config):
    print_help_message(_current_command, _run_as_root,
                       False, config, config_path)


def supervisor_loop(command, run_as_root, duration=None):
    global child

    start_child(command, run_as_root, duration)

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
                start_child(command, run_as_root, duration)

            time.sleep(0.05)

        if child and child.poll() is not None:
            sup_print_runtime(f"process exited with code {child.returncode}")
            child = None
            _restore_terminal()

        if child is None:
            if restart_requested.is_set():
                restart_requested.clear()
                sup_print_runtime("starting")
                start_child(command, run_as_root, duration)
            else:
                time.sleep(0.1)


def _add_hotkey(key, cmd):
    if key != "":
        keyboard.add_hotkey(key, cmd)


def _load_toml() -> tuple[dict, str | None]:
    PROJECT_NAME = "ksv"
    config_manager = ConfigManager(PROJECT_NAME)
    CONFIG_FILE_NAME = "config.toml"
    if os.path.exists(CONFIG_FILE_NAME):
        path = Path(CONFIG_FILE_NAME)
    else:
        path = config_manager.find_config_file(CONFIG_FILE_NAME)

    if not os.path.exists(path):
        return ({}, None)

    with open(path, "rb") as file:
        data = tomllib.load(file)

    return (data, str(path.absolute()))


def _make_config() -> Config:
    global config_path
    data, config_path = _load_toml()
    return Config(data)


def main():
    global QUIET, QUIET_STARTUP
    config = _make_config()
    global _config
    _config = config

    parser = argparse.ArgumentParser(
        description="A simple tool to easily run, restart, terminate, and rerun a process, based on a keybinding to make development easier."
    )
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
        action="store_true",
        help="suppress supervisor startup output",
    )
    parser.add_argument(
        "-Q",
        action="store_true",
        help="suppress supervisor runtime output",
    )
    parser.add_argument(
        "-d",
        "--duration",
        type=str,
        metavar="DURATION",
        help="automatically terminate the subprocess after this duration (e.g., '5' for 5 seconds, '500ms' for 500 milliseconds)",
    )
    parser.add_argument(
        "-t",
        "--terminate",
        action="store_true",
        help="forcefully terminate the child process (SIGKILL) instead of sending SIGTERM",
    )
    parser.add_argument(
        "--no-tty-restore",
        action="store_true",
        help="disable saving and restoring terminal settings after child process exits",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)

    args = parser.parse_args()

    QUIET = args.Q
    QUIET_STARTUP = args.q

    if not args.command:
        if not QUIET:
            print(
                "[supervisor] Usage: sudo python reloader.py [-r] [-q|-Q] <command...>"
            )
        sys.exit(1)

    global _current_command, _run_as_root, _duration_seconds, _duration_str, _force_kill, _tty_restore_enabled
    _current_command = args.command
    _run_as_root = args.root
    _force_kill = args.terminate
    _duration_str = args.duration
    _duration_seconds = _parse_duration(_duration_str)
    _tty_restore_enabled = not args.no_tty_restore and config.supervisor.tty_restore

    _add_hotkey(config.bindings.restart, on_restart_hotkey)
    _add_hotkey(config.bindings.stop, on_stop_hotkey)
    _add_hotkey(config.bindings.clear, on_clear_hotkey)

    def _on_help():
        on_help_hotkey(config)
    _add_hotkey(config.bindings.help, _on_help)
    _add_hotkey(config.bindings.reload, on_reload_hotkey)

    global YELLOW, CYAN, NORMAL_COLOR, RED_BOLD, WHITE_BOLD, RESET
    if args.no_ansii:
        YELLOW = ""
        CYAN = ""
        NORMAL_COLOR = ""
        RED_BOLD = ""
        WHITE_BOLD = ""
        RESET = ""

    print_help_message(args.command, args.root,
                       QUIET_STARTUP, config, config_path)

    _save_terminal()

    try:
        supervisor_loop(args.command, args.root, _duration_seconds)
    except KeyboardInterrupt:
        sup_print_runtime("shutting down")
    finally:
        shutdown_requested.set()
        stop_child()


if __name__ == "__main__":
    main()
