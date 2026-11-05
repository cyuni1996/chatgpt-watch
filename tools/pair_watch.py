"""Provision a saved computer over authorized ADB; works with the release APK."""
import argparse
import ipaddress
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import os

from computer_runtime import ROOT,prepare_runtime
APP='org.watchchat.app'


def resolve_adb(explicit=None):
    candidates=[explicit,shutil.which('adb')]
    for root in [os.environ.get('ANDROID_HOME'),os.environ.get('ANDROID_SDK_ROOT')]:
        if root:candidates.append(str(Path(root)/'platform-tools/adb.exe'))
    return next((value for value in candidates if value and Path(value).is_file()),None)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',help='LAN IPv4 address of this computer')
    parser.add_argument('--name',help='Name shown in the watch computer list')
    parser.add_argument('--adb')
    parser.add_argument('--serial')
    parser.add_argument('--reverse',action='store_true',help='Temporary ADB connection only')
    parser.add_argument('--skip-install',action='store_true')
    parser.add_argument('--apk',type=Path,default=ROOT/'app/build/outputs/apk/release/app-release.apk')
    args=parser.parse_args()
    executable=resolve_adb(args.adb)
    if not executable:parser.error('ADB not found; supply --adb')
    serial=args.serial
    if not serial:
        result=subprocess.run([executable,'devices'],check=True,capture_output=True,text=True)
        devices=[line.split()[0] for line in result.stdout.splitlines()[1:] if len(line.split())>=2 and line.split()[1]=='device']
        if len(devices)!=1:parser.error('Connect one watch or supply --serial')
        serial=devices[0]
    command=[executable,'-s',serial]
    def adb(*parts):
        result=subprocess.run(command+list(parts),capture_output=True,text=True,encoding='utf8',errors='replace',check=True)
        return result.stdout.strip()
    host='127.0.0.1' if args.reverse else str(ipaddress.IPv4Address(args.host or input('Computer LAN IPv4: ').strip()))
    directory,config,_,_=prepare_runtime(name=args.name,caller=os.environ.get('CODEX_THREAD_ID'))
    if not args.skip_install:
        print(adb('install','-r',str(args.apk)))
    port=config['port']
    if args.reverse:adb('reverse',f'tcp:{port}',f'tcp:{port}')
    payload={key:config[key] for key in ['computerId','computerName','token','certificateSha256']}
    payload['url']=f'https://{host}:{port}'
    local=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf8',suffix='.json',prefix='pairing-',dir=directory,delete=False) as file:
            local=Path(file.name);json.dump(payload,file)
        adb('shell','am','force-stop',APP)
        adb('push',str(local),'/data/local/tmp/watch-chat-pairing.json')
        adb('shell','chmod','600','/data/local/tmp/watch-chat-pairing.json')
        result=adb('shell','sh','-c',"'cat /data/local/tmp/watch-chat-pairing.json | content write --uri content://org.watchchat.app.pairing/pairing'")
        if 'Error' in result or 'Exception' in result:raise RuntimeError('Watch pairing provider failed; install version 0.8.0 or newer')
    finally:
        adb('shell','rm','-f','/data/local/tmp/watch-chat-pairing.json')
        if local:local.unlink(missing_ok=True)
    adb('shell','am','start','-n',APP+'/.MainActivity')
    print('Computer added: '+config['computerName']+' ('+payload['url']+'). Existing computers were retained.')


if __name__=='__main__':main()
