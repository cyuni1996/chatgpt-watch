"""Choose an independent identity/cache for this physical computer, including copied checkouts."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge'))
from server import identity,atomic_json

def machine_key():
    if os.name=='nt':
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Cryptography',0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
            return str(winreg.QueryValueEx(key,'MachineGuid')[0])
    return socket.gethostname()

def runtime_directory(base=None,key=None):
    digest=hashlib.sha256((key if key is not None else machine_key()).encode()).hexdigest()[:24]
    return Path(base or ROOT/'.local')/'computers'/digest

def prepare_runtime(base=None,key=None,name=None,caller=None):
    directory=runtime_directory(base,key)
    config,cert,private_key=identity(directory)
    config.setdefault('computerId',str(uuid.uuid4()))
    config['computerName']=name or config.get('computerName') or socket.gethostname()
    if caller:config['callerThreadId']=caller
    atomic_json(directory/'connection.json',config)
    return directory,config,cert,private_key

def connection_address_lines(port):
    lines = [f'电脑连接服务 TCP 端口：{port}']
    try:
        import ifaddr
    except ImportError:
        adapters = []
    else:
        adapters = ifaddr.get_adapters()
    for adapter in adapters:
        for entry in adapter.ips:
            if not isinstance(entry.ip, str):
                continue
            address = ipaddress.IPv4Address(entry.ip)
            if not (address.is_loopback or address.is_link_local or address.is_unspecified):
                lines.append(f'{adapter.nice_name}  https://{address}:{port}')
    if len(lines) == 1:
        lines.append('未找到可用的内网 IPv4 地址，请检查电脑的网络连接。')
    else:
        lines.append('穿透映射目标：选择转发端能访问的网卡 IP，端口填上面的 TCP 端口。')
    return lines

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--name')
    parser.add_argument('--caller-thread-id',help='A real local Codex chat ID used as the bridge caller; kept only in ignored local configuration')
    parser.add_argument('--layout',action='store_true')
    args=parser.parse_args()
    if args.layout:result={'directory':str(runtime_directory()),'projectDirectory':str(ROOT)}
    else:
        caller=args.caller_thread_id or os.environ.get('CODEX_THREAD_ID')
        if caller:
            try: uuid.UUID(caller)
            except ValueError: parser.error('--caller-thread-id must be an existing chat UUID')
        directory,config,_,_=prepare_runtime(name=args.name,caller=caller)
        result={'directory':str(directory),'projectDirectory':str(ROOT),'computerId':config['computerId'],'computerName':config['computerName'],
                'port':config['port'],'callerThreadId':config.get('callerThreadId'),
                'connectionAddressLines':connection_address_lines(config['port'])}
    print(json.dumps(result))
