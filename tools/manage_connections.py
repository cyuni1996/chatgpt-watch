"""Local operator approval for watch pairing; no long-lived secret is printed."""
import argparse,json,ssl,subprocess,sys,time,urllib.request,urllib.error
from pathlib import Path
from computer_runtime import ROOT,prepare_runtime

def main():
    parser=argparse.ArgumentParser(description='管理手表配对与授权')
    parser.add_argument('action',choices=['pair','devices','revoke'],nargs='?',default='pair')
    parser.add_argument('--device-id')
    args=parser.parse_args()
    directory,config,_,_=prepare_runtime()
    context=ssl.create_default_context(cafile=str(directory/'server.pem'));context.check_hostname=False
    def request(path,data=None):
        admin=json.loads((directory/'paired-devices.json').read_text(encoding='utf8'))['adminToken']
        req=urllib.request.Request('https://127.0.0.1:'+str(config['port'])+'/api/connect/admin/'+path,
            data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+admin,'Content-Type':'application/json'})
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
    request('window',{'open':True});print('配对窗口已开启，有效期3分钟。\n在手表选择“局域网扫描”或填写已部署的公网域名。\n只允许核对码与手表完全一致的请求。')
    deadline=time.monotonic()+180
    try:
        while time.monotonic()<deadline:
            pending=request('pending')['requests']
            if not pending:time.sleep(1);continue
            for item in pending:
                print('\n设备：'+item['deviceName']+' · '+('公网' if item['mode']=='public' else '局域网'))
                print('核对码：'+item['code'])
                answer=input('与手表相同则输入 y 允许；输入其他内容拒绝：').strip().lower()
                request('decide',{'requestId':item['requestId'],'approve':answer=='y'})
                if answer=='y':print('已允许，手表会自动保存连接。');return
        print('配对窗口已到期。')
    finally:request('window',{'open':False})

if __name__=='__main__':main()
