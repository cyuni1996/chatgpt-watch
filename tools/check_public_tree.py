"""Review staged/source/history contents without printing suspected secret values.

This is a local heuristic, not a complete secret scanner. --deny-file is private
input kept outside the repository. No data is uploaded by this tool.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PARTS = {'.local', '.tools', '.gradle', '.kotlin', '.venv', 'venv', '__pycache__', '.idea', 'build'}
PRIVATE_NAMES = {'local.properties', 'connection.json', 'sessions.json', 'paired-devices.json',
                 'public-endpoint.json', 'cloudflared.yml', 'cloudflared.yaml', 'credentials.json'}
PRIVATE_SUFFIXES = {'.pem', '.key', '.jks', '.keystore', '.p12', '.pfx', '.crt', '.cer',
                    '.db', '.sqlite', '.sqlite3', '.log', '.pid', '.apk', '.aab', '.wav', '.mp4', '.pyc'}
RULES = {
    'private-key': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
    'github-token': re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'api-key': re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b'),
    'url-password': re.compile(r'https?://[^\s/<>"\']+:[^\s/@<>"\']+@'),
    'windows-user-path': re.compile(r'(?i)[a-z]:[/\\]+Users[/\\]+[^\s/\\<>"\']+'),
    'unix-user-path': re.compile(r'/(?:home|Users)/[a-zA-Z0-9_.-]+/'),
    'credential-assignment': re.compile(r'''(?i)["']?(?:TunnelSecret|adminToken|api_key|access_token)["']?\s*[:=]\s*["'][A-Za-z0-9_+/=-]{24,}["']'''),
    'literal-bearer-token': re.compile(r'''Bearer\s+[A-Za-z0-9_.+/=-]{28,}'''),
}


def findings(path, data, denied=()):
    """Return non-sensitive (rule, line) pairs; never return matching values."""
    p = PurePosixPath(path)
    hits = []
    if any(part in PRIVATE_PARTS for part in p.parts) or p.name in PRIVATE_NAMES or p.suffix.lower() in PRIVATE_SUFFIXES or p.name.startswith('.env'):
        hits.append(('private-file', 0))
    # Only the wrapper, artwork, reviewed poster and maintainer-approved support image are binary inputs.
    binary_allowed = path == 'gradle/wrapper/gradle-wrapper.jar' or path in {
        'app/src/main/res/drawable-nodpi/dragon_chat.webp',
        'app/src/main/res/drawable-nodpi/dragon_drawer.webp',
        'app/src/main/res/drawable-nodpi/dragon_portrait.png',
        'docs/media/demo-poster.jpg',
        'docs/media/support.png',
    }
    if b'\0' in data:
        if not binary_allowed:
            hits.append(('unreviewed-binary', 0))
        for value in denied:
            if value.encode('utf-8').lower() in data.lower():
                hits.append(('private-identifier', 0))
        return hits
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return hits if binary_allowed else hits + [('unreviewed-encoding', 0)]
    for number, line in enumerate(text.splitlines(), 1):
        checked_line = line
        if path in {'bridge/test_connections.py', 'app/src/test/java/org/watchchat/app/ConnectionModesTest.kt'}:
            # Exact synthetic rejected-URL fixture only; other embedded credentials still fail.
            checked_line = line.replace('https://' + 'user:pass' + '@watch.example.com', 'https://watch.example.com')
        for name, pattern in RULES.items():
            if pattern.search(checked_line):
                hits.append((name, number))
        if any(value.casefold() in line.casefold() for value in denied):
            hits.append(('private-identifier', number))
    return hits


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def entries(tracked=False, history=False):
    if history:
        # Inspect every committed path; do not rely on the current .gitignore.
        seen = set()
        for commit in git('rev-list', '--all').decode().splitlines():
            for entry in git('ls-tree', '-r', '-z', commit).split(b'\0'):
                if not entry:
                    continue
                meta, raw = entry.split(b'\t', 1)
                _, kind, oid = meta.split()
                path = raw.decode('utf-8')
                key = (oid, path)
                if key in seen:
                    continue
                seen.add(key)
                if kind != b'blob':
                    yield path, b'git-submodule-not-reviewed\0'
                else:
                    yield path, git('cat-file', 'blob', oid.decode())
    elif tracked:
        # Read the staged blob, not the possibly different working file.
        for item in git('ls-files', '--stage', '-z').split(b'\0'):
            if not item:
                continue
            meta, raw = item.split(b'\t', 1)
            _, oid, stage = meta.split()
            if stage != b'0':
                raise RuntimeError('Resolve merge conflicts before scanning')
            yield raw.decode('utf-8'), git('cat-file', 'blob', oid.decode())
    else:
        for path in ROOT.rglob('*'):
            rel = path.relative_to(ROOT)
            if not path.is_file() or '.git' in rel.parts or any(part in PRIVATE_PARTS for part in rel.parts):
                continue
            yield rel.as_posix(), path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--tracked', action='store_true', help='Inspect every staged/tracked blob')
    modes.add_argument('--history', action='store_true', help='Inspect every reachable commit blob')
    parser.add_argument('--deny-file', type=Path, help='External private file: one literal identifier per line')
    args = parser.parse_args()
    denied = []
    if args.deny_file:
        private_path = args.deny_file.resolve()
        if private_path.is_relative_to(ROOT):
            parser.error('--deny-file must be outside the repository')
        denied = [line.strip() for line in private_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    issues, count = [], 0
    try:
        for path, data in entries(args.tracked, args.history):
            count += 1
            issues.extend({'file': path, 'rule': rule, 'line': line} for rule, line in findings(path, data, denied))
    except (subprocess.CalledProcessError, RuntimeError) as error:
        parser.exit(2, f'Cannot complete repository inspection ({type(error).__name__}).\n')
    print(json.dumps({'files_checked': count, 'findings': issues, 'passed': not issues}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if issues else 0)


if __name__ == '__main__':
    main()
