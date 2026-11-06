"""Open a local pairing window or manage authorized watches."""
import argparse,json,ssl,subprocess,sys,time,urllib.request,urllib.error
from computer_runtime import ROOT,connection_address_lines,prepare_runtime

def main():
    parser=argparse.ArgumentParser(description='管理手表配对与授权')
    parser.add_argument('action',choices=['pair','internet-code','devices','revoke'],nargs='?',default='pair')
    parser.add_argument('--device-id')
    args=parser.parse_args()
    directory,config,_,_=prepare_runtime()
    context=ssl.create_default_context(cafile=str(directory/'server.pem'));context.check_hostname=False
    def request(path,data=None,*,admin=True):
        headers = {'Content-Type':'application/json'}
        if admin:
            token=json.loads((directory/'paired-devices.json').read_text(encoding='utf8'))['adminToken']
            headers['Authorization']='Bearer '+token
            path='admin/'+path
        req=urllib.request.Request('https://127.0.0.1:'+str(config['port'])+'/api/connect/'+path,
            data=None if data is None else json.dumps(data).encode(),headers=headers)
        with urllib.request.urlopen(req,context=context,timeout=8) as response:return json.load(response)
    try:request('devices')
    except (OSError,ValueError,KeyError):
        if sys.platform!='win32':raise SystemExit('请先启动最新版电脑连接服务。')
        subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'tools/start-companion.ps1')],check=True)
        for attempt in range(40):
            try:request('devices');break
            except (OSError,ValueError,KeyError):time.sleep(1)
        else:raise SystemExit('连接服务尚未就绪；旧版正在运行时，请先停止并重新启动连接服务。')
    if args.action=='devices':
        for d in request('devices')['devices']:print(d['id'],d['name'],'已撤销' if d['revoked'] else '有效')
        return
    if args.action=='revoke':
        if not args.device_id:parser.error('请用 --device-id 指定要撤销的设备编号')
        request('revoke',{'deviceId':args.device_id});print('设备授权已撤销。');return
    if args.action=='internet-code':
        try:
            code=request('internet',{})['code']
        except urllib.error.HTTPError as error:
            if error.code!=404:raise
            raise SystemExit('请先重启新版电脑连接服务。') from error
        print('外网配对码：'+'-'.join(code[i:i+4] for i in range(0,len(code),4)))
        print('3 分钟内输入手表，使用一次后失效。')
        return
    if args.action=='pair':
        print('\n'.join(connection_address_lines(config['port'])),flush=True)
        if not request('info',admin=False).get('lanProofRequired'):
            raise SystemExit('当前连接服务仍是旧版，请停止后重新启动，再开启局域网配对。')
        window=request('window',{'open':True,'mode':'watch'})
        if window.get('mode')!='watch':
            request('window',{'open':False})
            raise SystemExit('请先重启新版电脑连接服务。')
        print('局域网配对已开启，有效期 3 分钟。请在手表上选择电脑并点“确认配对”。')

if __name__=='__main__':main()
