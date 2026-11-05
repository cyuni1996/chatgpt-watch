"""Generate a fixed-domain Cloudflare Tunnel configuration without exposing LAN TLS."""
import argparse,json,ipaddress,socket,sys,uuid
from pathlib import Path
from computer_runtime import ROOT,prepare_runtime
sys.path.insert(0,str(ROOT/'bridge'))
from connections import public_url

def tunnel_config(url,tunnel_id,credentials_file,origin_port):
    url=public_url(url);tunnel_id=str(uuid.UUID(tunnel_id))
    if not 1024<=origin_port<=65535:raise ValueError('本地转发端口无效')
    host=url.removeprefix('https://')
    # JSON is valid YAML; quoting paths also works on Windows.
    return '\n'.join(['tunnel: '+tunnel_id,'credentials-file: '+json.dumps(str(Path(credentials_file).resolve())),
        'ingress:', '  - hostname: '+host,'    path: "^/api/connect/admin/.*"','    service: http_status:404',
        '  - hostname: '+host,'    service: http://127.0.0.1:'+str(origin_port),'  - service: http_status:404',''])

def main():
    p=argparse.ArgumentParser(description='配置公网固定域名；不会创建或发布隧道')
    p.add_argument('--domain',required=True);p.add_argument('--tunnel-id',required=True)
    p.add_argument('--credentials-file',required=True,type=Path);p.add_argument('--origin-port',default=8767,type=int)
    args=p.parse_args()
    try:
        url=public_url(args.domain if '://' in args.domain else 'https://'+args.domain)
        if not args.credentials_file.is_file():raise ValueError('隧道凭据文件不存在；请先完成Cloudflare登录并创建命名隧道')
        c=json.loads(args.credentials_file.read_text(encoding='utf8'))
        if str(uuid.UUID(c.get('TunnelID','')))!=str(uuid.UUID(args.tunnel_id)) or not c.get('TunnelSecret'):raise ValueError('凭据文件与隧道编号不一致')
        directory,config,_,_=prepare_runtime()
        if config['port']==args.origin_port:raise ValueError('本地转发端口不能与局域网端口相同')
        text=tunnel_config(url,args.tunnel_id,args.credentials_file,args.origin_port)
    except (ValueError,OSError,KeyError) as error:p.error(str(error))
    endpoint={'url':url,'originPort':args.origin_port}
    def save(path,content):
        temp=path.with_suffix('.tmp');temp.write_text(content,encoding='utf8');temp.replace(path)
    save(directory/'public-endpoint.json',json.dumps(endpoint,ensure_ascii=False,indent=2))
    target=directory/'cloudflared.yml';save(target,text)
    print('公网入口已配置：'+url)
    print('请重启电脑连接服务，再运行“Start Public Tunnel.cmd”。首次手表配对请运行“开启电脑配对.cmd”。')
    print('隧道配置：'+str(target))

if __name__=='__main__':main()
