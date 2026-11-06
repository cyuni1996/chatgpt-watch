"""One installation entry point for humans and terminal-capable AI assistants.

Doctor works before third-party Python packages are installed. No command sends
a chat, approves a desktop action, uninstalls an app, or changes firewall policy.
"""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import urllib.request
import uuid

PACKAGING = Path(__file__).resolve().parent
ROOT = PACKAGING.parent
SOURCE = ROOT / "src"
DEBUG_APK = PACKAGING / "build/app/outputs/apk/debug/app-debug.apk"


def sdk_root(env=None):
    env = os.environ if env is None else env
    candidates = [env.get('ANDROID_HOME'), env.get('ANDROID_SDK_ROOT')]
    properties = PACKAGING / 'local.properties'
    if properties.is_file():
        value = re.search(r'^\s*sdk\.dir\s*=\s*(.+)$',properties.read_text(encoding='utf-8-sig'),re.MULTILINE)
        if value:
            candidates.append(re.sub(r'\\([\\: ])',r'\1',value[1].strip()))
    if env.get('LOCALAPPDATA'):
        candidates.append(str(Path(env['LOCALAPPDATA']) / 'Android' / 'Sdk'))
    return next((Path(value) for value in candidates if value and Path(value).is_dir()), None)


def adb_path(explicit=None):
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ValueError('The supplied ADB executable does not exist')
        return str(path)
    found = shutil.which('adb')
    sdk = sdk_root()
    if not found and sdk:
        candidate = sdk / 'platform-tools' / ('adb.exe' if os.name == 'nt' else 'adb')
        if candidate.is_file():
            found = str(candidate)
    if not found:
        raise ValueError('ADB is missing. Set ANDROID_HOME or pass --adb.')
    return found


def connected_devices(output):
    return [parts[0] for line in output.splitlines() if len(parts := line.split()) >= 2 and parts[1] == 'device']


def select_device(adb, serial=None):
    result = subprocess.run([adb, 'devices'], check=True, capture_output=True, text=True, timeout=15)
    devices = connected_devices(result.stdout)
    if serial:
        if serial not in devices:
            raise ValueError('The selected watch is not an authorized connected ADB device')
        return serial
    if len(devices) != 1:
        raise ValueError('Connect exactly one watch, or select one with --serial. Unauthorized devices require confirmation on the watch.')
    return devices[0]


def checked(command, **kwargs):
    return subprocess.run([str(value) for value in command], check=True, **kwargs)


def version(name, args, minimum, maximum=None):
    executable = shutil.which(name)
    if name in ('java','javac') and os.environ.get('JAVA_HOME'):
        candidate = Path(os.environ['JAVA_HOME']) / 'bin' / (name+'.exe' if os.name == 'nt' else name)
        if candidate.is_file():
            executable = str(candidate)
    if not executable:
        return {'ok': False, 'reason': 'not-found'}
    try:
        result = subprocess.run([executable, *args], capture_output=True, text=True, timeout=12)
        line = (result.stdout or result.stderr).splitlines()[0]
        numbers = re.search(r'(\d+)(?:\.(\d+))?', line)
        major = int(numbers.group(1)) if numbers else None
        ready = major is not None and major >= minimum and (maximum is None or major <= maximum)
        details = {'ok': result.returncode == 0 and ready, 'major': major, 'minimum': minimum}
        if maximum is not None:
            details['maximum'] = maximum
        return details
    except (OSError, subprocess.SubprocessError, IndexError):
        return {'ok': False, 'reason': 'cannot-run'}


async def desktop_catalog():
    sys.path.insert(0, str(SOURCE / 'bridge'))
    from desktop import DesktopClient
    client = DesktopClient()
    try:
        await client.start()
        catalog = await client.call('catalog', timeout=12)
        return {'ok': True, 'tools': len(catalog)}
    except Exception:
        return {'ok': False, 'reason': 'Open signed-in Codex desktop; its local tool protocol must be compatible.'}
    finally:
        await client.close()


def doctor(target='all', desktop=False):
    sdk = sdk_root()
    checks = {'windows': {'ok': os.name == 'nt'},
              'python': {'ok': sys.version_info >= (3, 11), 'major': sys.version_info.major, 'minor': sys.version_info.minor},
              'node': version('node', ['--version'], 20),
              'python_dependencies': {'ok': all(importlib.util.find_spec(name) is not None for name in ('aiohttp', 'cryptography', 'zeroconf', 'ifaddr'))}}
    required = ['windows', 'python', 'node', 'python_dependencies'] if target in ('all', 'companion') else ['python']
    if target in ('all', 'build'):
        # AGP 8.7 requires Java 17; the Gradle 8.11.1 wrapper supports up to Java 23.
        checks['java'] = version('java', ['-version'], 17, 23)
        checks['javac'] = version('javac', ['-version'], 17, 23)
        checks['android_sdk_35'] = {'ok': bool(sdk and (sdk / 'platforms/android-35/android.jar').is_file())}
        aapt2 = 'aapt2.exe' if os.name == 'nt' else 'aapt2'
        checks['android_build_tools_34'] = {'ok': bool(sdk and (sdk / 'build-tools/34.0.0' / aapt2).is_file())}
        required += ['java', 'javac', 'android_sdk_35', 'android_build_tools_34']
    if target in ('all', 'install'):
        try:
            adb = adb_path()
            output = subprocess.run([adb, 'devices'], check=True, capture_output=True, text=True, timeout=15).stdout
            count = len(connected_devices(output))
            checks['adb'] = {'ok': count > 0, 'authorized_devices': count,
                             'reason': 'ready' if count else 'Connect and authorize the watch before installation.'}
        except (ValueError, OSError, subprocess.SubprocessError):
            checks['adb'] = {'ok': False, 'reason': 'Install Android Platform Tools; set ANDROID_HOME or put adb on PATH.'}
        required += ['adb']
    if desktop:
        checks['desktop'] = asyncio.run(desktop_catalog())
        required += ['desktop']
    return {'ready': all(checks[name]['ok'] for name in required), 'target': target, 'checks': checks}


def install(adb, serial, apk):
    apk = Path(apk).resolve()
    if not apk.is_file() or apk.suffix.lower() != '.apk':
        raise ValueError('Provide an existing signed .apk file')
    # A different signature is intentionally an error. Never retry by uninstalling.
    return checked([adb, '-s', serial, 'install', '-r', apk])


def build(mirror=False):
    env = os.environ.copy()
    sdk = sdk_root()
    if sdk:
        env['ANDROID_HOME'] = str(sdk)
    wrapper = PACKAGING / ('gradlew.bat' if os.name == 'nt' else 'gradlew')
    command = [str(wrapper), ':app:assembleDebug', '--console=plain']
    if mirror:
        command.append('-PuseRepositoryMirror=true')
    checked(command, cwd=PACKAGING, env=env)
    print('APK: ' + DEBUG_APK.relative_to(ROOT).as_posix())


def start(caller=None, name=None):
    if os.name != 'nt':
        raise ValueError('The desktop companion currently requires Windows')
    if caller:
        try:
            uuid.UUID(caller)
        except ValueError:
            raise ValueError('Use a real existing chat UUID, not a made-up value') from None
    if caller or name:
        command = [sys.executable, SOURCE / 'tools/computer_runtime.py']
        if caller:
            command += ['--caller-thread-id', caller]
        if name:
            command += ['--name', name]
        # This helper returns private configuration details; do not echo them.
        checked(command, cwd=ROOT, stdout=subprocess.DEVNULL)
    checked(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', SOURCE / 'tools/start-companion.ps1'], cwd=ROOT)


def verify():
    sys.path.insert(0, str(SOURCE / 'tools'))
    from computer_runtime import runtime_directory
    directory = runtime_directory()
    config = json.loads((directory / 'connection.json').read_text(encoding='utf8'))
    context = ssl.create_default_context(cafile=str(directory / 'server.pem'))
    context.check_hostname = False  # CA trust is pinned to this local self-signed certificate.
    request = urllib.request.Request('https://127.0.0.1:' + str(config['port']) + '/api/conversations',
                                     headers={'Authorization': 'Bearer ' + config['token']})
    with urllib.request.urlopen(request, context=context, timeout=30) as response:
        value = json.load(response)
    print(json.dumps({'ok': True, 'read_only': True, 'history_items': len(value.get('conversations', []))}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='action', required=True)
    check = subs.add_parser('doctor', help='Read-only prerequisites check; no secrets/paths in report')
    check.add_argument('--target', choices=['all', 'companion', 'install', 'build'], default='all')
    check.add_argument('--desktop', action='store_true', help='Read the desktop tool catalog without sending a chat')
    subs.add_parser('deps', help='Install Python dependencies into the current interpreter/environment')
    downloader = subs.add_parser('download', help='Download the signed project APK and verify its release checksum')
    downloader.add_argument('--tag', help='Published tag matching the current source version')
    builder = subs.add_parser('build', help='Build a locally signed debug APK')
    builder.add_argument('--mirror', action='store_true', help='Explicitly opt into the Aliyun dependency mirrors')
    installer = subs.add_parser('install', help='Install/update on one authorized watch; never uninstall')
    installer.add_argument('--apk', type=Path, default=DEBUG_APK)
    installer.add_argument('--adb')
    installer.add_argument('--serial')
    starter = subs.add_parser('start', help='Start the companion using a real caller context')
    starter.add_argument('--caller-thread-id')
    starter.add_argument('--name')
    subs.add_parser('pair', help='Open the three-minute LAN pairing window; confirm on the watch')
    subs.add_parser('verify', help='Read desktop history counts; never send a test prompt')
    args = parser.parse_args()
    try:
        if args.action == 'doctor':
            result = doctor(args.target, args.desktop)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0 if result['ready'] else 1
        if args.action == 'download':
            from download_release import download
            target = download(args.tag)
            print('Verified APK: ' + str(target.relative_to(ROOT)))
        elif args.action == 'deps':
            checked([sys.executable, '-m', 'pip', 'install', '-r', SOURCE / 'bridge/requirements.txt'])
        elif args.action == 'build':
            build(args.mirror)
        elif args.action == 'install':
            adb = adb_path(args.adb)
            install(adb, select_device(adb, args.serial), args.apk)
        elif args.action == 'start':
            start(args.caller_thread_id, args.name)
        elif args.action == 'pair':
            checked([sys.executable, SOURCE / 'tools/manage_connections.py', 'pair'], cwd=ROOT)
        elif args.action == 'verify':
            verify()
    except (ValueError, OSError, subprocess.SubprocessError, ImportError) as error:
        # Do not dump tracebacks, caller IDs, authenticated requests, or configuration.
        if isinstance(error, ValueError):
            parser.exit(1, str(error) + '\n')
        parser.exit(1, 'Setup did not complete (' + type(error).__name__ + '). Check prerequisites and retry; no uninstall was attempted.\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
