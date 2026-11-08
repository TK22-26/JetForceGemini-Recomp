"""Bounded, filtered Wine pointer-grab capture; no ROM/save or keyboard trace collection."""
from __future__ import annotations
import argparse
import ctypes
import threading
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time

FUNCTIONS = (
    'NtUserClipCursor', 'process_wine_clipcursor', 'grab_clipping_window',
    'ungrab_clipping_window', 'X11DRV_ClipCursor', 'X11DRV_SetCursorPos',
    'X11DRV_SetCapture', 'X11DRV_FocusIn', 'X11DRV_FocusOut', 'focus_out',
    'set_focus', 'wait_grab_pointer',
)
TRACE = re.compile(rb'^(?:[0-9a-fA-F]+(?:\.[0-9]+)?:)*(?:trace|warn|err):(?:cursor|win|event):(' +
                   b'|'.join(x.encode('ascii') for x in FUNCTIONS) + rb')\b')
ANSI = re.compile(rb'\x1b\[[0-?]*[ -/]*[@-~]')
MAX_TRACE = 16 * 1024 * 1024
LOG_NAMES = {'mouse.log', 'native.log', 'launcher.log', 'presentation.log', 'build.log'}
POLICY_NAMES = {'GrabPointer', 'GrabFullscreen', 'MouseWarpOverride', 'UseTakeFocus', 'Graphics'}
POLICY_SECTION = re.compile(r'^Software\\\\Wine\\\\(?:(?:AppDefaults\\\\(?:JFG-Launcher|jfg-native-boot)\.exe\\\\)?(?:X11 Driver|DirectInput|Drivers))$', re.I)

def stamp() -> str:
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')

def filtered(line: bytes) -> tuple[str, bytes] | None:
    line = ANSI.sub(b'', line)
    # Match the diagnostic prefix, not text embedded in a window message.
    match = TRACE.search(line[:160])
    if not match or len(line) > 2048:
        return None
    return match[1].decode('ascii'), line.rstrip(b'\r\n') + b'\n'

def policy(prefix: Path | None) -> dict:
    result = {}
    if prefix is None:
        return result
    path = prefix / 'pfx/user.reg'
    if not path.is_file() or path.stat().st_size > 32 * 1024 * 1024:
        return result
    section = None
    with path.open(encoding='utf-8', errors='replace') as source:
        for line in source:
            if line.startswith('['):
                section = line[1:line.find(']')]
            if section and POLICY_SECTION.fullmatch(section):
                match = re.fullmatch(r'"([A-Za-z]+)"="([A-Za-z0-9_, -]{0,100})"\s*', line)
                if match and match[1] in POLICY_NAMES:
                    result.setdefault(section, {})[match[1]] = match[2]
    return result

def safe_file(root: Path, relative: str) -> Path:
    target = root / relative
    if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != root):
        raise ValueError('Linked destination preserved: ' + relative)
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError('Destination escapes installation')
    return target

def sample_x11(out: Path, stopped: threading.Event, env: dict[str, str]) -> None:
    """Read-only X server observations; no focus changes, input or window titles."""
    status = {'available': False, 'samples': 0, 'scope': 'X server pointer/focus, not direct Wayland compositor proof'}
    display = None
    try:
        if sys.platform != 'linux' or not env.get('DISPLAY'):
            status['reason'] = 'No Linux X11 display'
            return
        x11 = ctypes.CDLL('libX11.so.6')
        ulong = ctypes.c_ulong
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x11.XDefaultRootWindow.restype = ulong
        x11.XQueryPointer.argtypes = [ctypes.c_void_p, ulong, ctypes.POINTER(ulong), ctypes.POINTER(ulong), *([ctypes.POINTER(ctypes.c_int)] * 4), ctypes.POINTER(ctypes.c_uint)]
        x11.XGetInputFocus.argtypes = [ctypes.c_void_p, ctypes.POINTER(ulong), ctypes.POINTER(ctypes.c_int)]
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        display = x11.XOpenDisplay(env['DISPLAY'].encode())
        if not display:
            status['reason'] = 'XOpenDisplay failed'
            return
        root = x11.XDefaultRootWindow(display)
        status['available'] = True
        started = time.monotonic()
        with (out / 'x11-pointer.jsonl').open('w', encoding='utf-8') as stream:
            while not stopped.is_set() and time.monotonic() - started < 300:
                returned_root, child, focus = ulong(), ulong(), ulong()
                x, y, local_x, local_y, revert = (ctypes.c_int() for _ in range(5))
                mask = ctypes.c_uint()
                ok = x11.XQueryPointer(display, root, ctypes.byref(returned_root), ctypes.byref(child), ctypes.byref(x), ctypes.byref(y), ctypes.byref(local_x), ctypes.byref(local_y), ctypes.byref(mask))
                x11.XGetInputFocus(display, ctypes.byref(focus), ctypes.byref(revert))
                # Deliberately omit the button mask and all window/property text.
                stream.write(json.dumps({'time_unix_ms': int(time.time() * 1000), 'same_screen': bool(ok), 'x': x.value, 'y': y.value, 'child': child.value, 'focus': focus.value}) + '\n')
                status['samples'] += 1
                stopped.wait(.25)
    except (OSError, AttributeError, ValueError) as error:
        status['reason'] = type(error).__name__
    finally:
        if display:
            x11.XCloseDisplay(display)
        (out / 'x11-status.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')


def copy_capture(archive: Path, destination: Path) -> Path:
    destination = destination.expanduser()
    # Do not recreate a disconnected removable drive's mount point.
    if not destination.parent.is_dir():
        raise ValueError('Capture destination is unavailable; retain the local archive.')
    destination.mkdir(exist_ok=True)
    target = safe_file(destination.resolve(), archive.name)
    with archive.open('rb') as source, target.open('xb') as output:
        shutil.copyfileobj(source, output)
    if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(archive.read_bytes()).digest():
        raise ValueError('USB copy verification failed; retain the local archive.')
    return target


def install(source: Path, root: Path) -> str:
    root = root.expanduser().resolve()
    if not (root / 'game/JFG-Launcher.exe').is_file():
        raise ValueError('Choose the existing JFG test installation with --root.')
    for name in ('capture-proton-mouse.sh', 'proton_mouse_capture.py'):
        if not (source / name).is_file():
            raise ValueError('Both capture files must remain together.')
        safe_file(root, name)
    backup = root / 'mouse-capture-tools-backups' / stamp()
    for name in ('capture-proton-mouse.sh', 'proton_mouse_capture.py'):
        src = source / name
        dest = safe_file(root, name)
        if dest.exists() and src.read_bytes() == dest.read_bytes():
            continue
        if dest.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup / name)
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
    options = 'bash ' + shlex.quote(str(root / 'capture-proton-mouse.sh'))
    if source.resolve() != root:
        options += ' --copy-to ' + shlex.quote(str(source.resolve() / 'mouse-capture-results'))
    options += ' -- %command% --portable --region usa'
    target = safe_file(root, 'mouse-capture-launch-options.txt')
    target.write_text(options + '\n', encoding='utf-8')
    print('Capture tools installed. Game files, profiles and Steam settings retained.')
    print('Replace the JFG Steam shortcut Launch Options with this one line:\n' + options)
    print('Play briefly, reproduce the mouse escape, then close the launcher normally.')
    print('The capture is saved under: ' + str(root / 'mouse-captures'))
    return options

def capture(root: Path, command: list[str], env: dict[str, str] | None = None, copy_to: Path | None = None) -> int:
    root = root.resolve()
    if not command:
        raise ValueError('The command after -- is missing.')
    if not (root / 'game/JFG-Launcher.exe').is_file():
        raise ValueError('Run --install first, then use the printed Steam launch option.')
    directory = safe_file(root, 'mouse-captures')
    directory.mkdir(exist_ok=True)
    out = directory / stamp()
    out.mkdir()
    inherited = dict(os.environ if env is None else env)
    context = {k: inherited.get(k, 'unknown') for k in
               ('XDG_SESSION_TYPE', 'XDG_CURRENT_DESKTOP', 'DESKTOP_SESSION', 'DISPLAY', 'WAYLAND_DISPLAY')}
    prefix = inherited.get('STEAM_COMPAT_DATA_PATH')
    context['wine_input_policy_registry_available'] = bool(prefix and (Path(prefix) / 'pfx/user.reg').is_file())
    context['wine_input_policy'] = policy(Path(prefix) if prefix else None)
    context['tool_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    context['scope'] = 'Filtered Wine cursor/focus decisions; existing Steam command and prefix.'
    (out / 'context.json').write_text(json.dumps(context, indent=2) + '\n', encoding='utf-8')
    child_env = {**inherited, 'PROTON_LOG': '0', 'WINEDEBUG': '-all,+timestamp,+pid,+tid,+cursor,+win,+event'}
    # The broad Wine channels are filtered in memory. Other messages, including
    # key/window text, are discarded without being written to the capture.
    counts = Counter()
    written = discarded = 0
    start_wall = time.time()
    started = time.monotonic()
    print('Mouse capture running; reproduce briefly and close normally.', flush=True)
    child = subprocess.Popen(command, env=child_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert child.stdout is not None
    stopped = threading.Event()
    sampler = threading.Thread(target=sample_x11, args=(out, stopped, inherited), daemon=True)
    sampler.start()
    with (out / 'pointer-trace.log').open('wb') as target:
        continuation = False
        while chunk := child.stdout.readline(8193):
            complete = chunk.endswith(b'\n')
            record = None if continuation or len(chunk) > 8192 else filtered(chunk)
            continuation = not complete
            if record and time.monotonic() - started <= 300 and written + len(record[1]) <= MAX_TRACE:
                name, line = record
                target.write(line)
                counts[name] += 1
                written += len(line)
            else:
                discarded += 1
    child.stdout.close()
    code = child.wait()
    stopped.set()
    sampler.join(timeout=3)
    copied = []
    report_root = root / 'game/userdata/reports'
    if report_root.is_dir() and not report_root.is_symlink():
        for report in sorted(report_root.iterdir())[-6:]:
            if not report.is_dir() or report.is_symlink():
                continue
            for source in report.iterdir():
                if source.name in LOG_NAMES and source.is_file() and not source.is_symlink() and source.stat().st_mtime >= start_wall - 2:
                    dest = out / 'game-reports' / report.name / source.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with source.open('rb') as src, dest.open('wb') as dst:
                        size = source.stat().st_size
                        if size > 2 * 1024 * 1024:
                            src.seek(size - 2 * 1024 * 1024)
                        left = min(size, 2 * 1024 * 1024)
                        while left:
                            block = src.read(min(left, 64 * 1024))
                            if not block:
                                break
                            dst.write(block)
                            left -= len(block)
                    copied.append(str(dest.relative_to(out)))
    receipt = {'exit_code': code, 'function_counts': dict(counts), 'trace_bytes': written,
               'discarded_lines_or_chunks': discarded, 'seconds': time.monotonic() - started,
               'game_reports': copied, 'limits': {'trace_bytes': MAX_TRACE, 'trace_seconds': 300},
               'x11_sampler_finished': not sampler.is_alive(), 'resolution_claimed': False}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    archive = out.with_suffix('.tar.gz')
    with tarfile.open(archive, 'x:gz') as tar:
        tar.add(out, arcname=out.name)
    print('Mouse capture saved: ' + str(archive), flush=True)
    if copy_to is not None:
        try:
            print('Verified USB copy: ' + str(copy_capture(archive, copy_to)), flush=True)
        except (OSError, ValueError) as error:
            print('USB copy unavailable: ' + str(error) + ' Local archive retained.', flush=True)
    print('Wine grab decisions: ' + str(counts['grab_clipping_window']), flush=True)
    if not counts['grab_clipping_window']:
        print('No grab decision was captured; this is not proof that capture worked.', flush=True)
    print('Restore the previous Steam launch options after this diagnostic run.', flush=True)
    return code

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install', action='store_true')
    parser.add_argument('--root', type=Path)
    parser.add_argument('--copy-to', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    here = Path(__file__).resolve().parent
    if args.install or not command:
        install(here, args.root or Path.home() / 'Games/JFG-Issue40-20261107')
        return 0
    return capture(args.root or here, command, copy_to=args.copy_to)

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print('Mouse capture: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
