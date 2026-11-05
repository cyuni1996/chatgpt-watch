"""Download a named official project release and verify its published SHA-256."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'cyuni1996/chatgpt-watch'
DEFAULT_TAG = 'v0.13.0'
APK_NAME = 'chatgpt-watch-0.13.0.apk'


def read_url(url, limit):
    if not url.startswith('https://'):
        raise ValueError('Release download requires HTTPS')
    request = urllib.request.Request(url, headers={'User-Agent': 'chatgpt-watch-installer'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Release response exceeds the expected size limit')
    return data


def expected_hash(checksums, filename):
    matches = []
    for line in checksums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip('*') == filename and re.fullmatch(r'[a-fA-F0-9]{64}', parts[0]):
            matches.append(parts[0].lower())
    if len(matches) != 1:
        raise ValueError('Release checksum is missing or ambiguous')
    return matches[0]


def download(tag=DEFAULT_TAG, directory=None):
    if not re.fullmatch(r'v\d+\.\d+\.\d+(?:[-.][A-Za-z0-9.-]+)?', tag):
        raise ValueError('Use an explicit version tag such as v0.13.0')
    info = json.loads(read_url('https://api.github.com/repos/' + REPOSITORY + '/releases/tags/' + tag, 1024 * 1024))
    if info.get('draft') or info.get('prerelease') or info.get('tag_name') != tag:
        raise ValueError('Expected a published stable release with the requested tag')
    assets = info.get('assets', [])
    def asset(name):
        values = [a for a in assets if a.get('name') == name]
        if len(values) != 1:
            raise ValueError('Expected one release asset named ' + name)
        url = values[0].get('browser_download_url', '')
        if not url.startswith('https://github.com/' + REPOSITORY + '/releases/download/' + tag + '/'):
            raise ValueError('Release asset is outside the expected repository/version')
        return url
    digest = expected_hash(read_url(asset('SHA256SUMS'), 16384).decode('utf8'), APK_NAME)
    output = Path(directory) if directory else ROOT / '.local/downloads' / tag
    output.mkdir(parents=True, exist_ok=True)
    target = output / APK_NAME
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
        return target
    content = read_url(asset(APK_NAME), 30 * 1024 * 1024)
    if hashlib.sha256(content).hexdigest() != digest or not content.startswith(b'PK'):
        raise ValueError('APK checksum or file format did not match; nothing was installed')
    temporary = target.with_suffix('.download')
    try:
        temporary.write_bytes(content)
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default=DEFAULT_TAG)
    args = parser.parse_args()
    try:
        target = download(args.tag)
    except (ValueError, OSError) as error:
        parser.exit(1, 'Release download failed (' + type(error).__name__ + '). Nothing was installed.\n')
    print('Verified APK: ' + str(target.relative_to(ROOT)))


if __name__ == '__main__':
    main()
