"""LAN discovery and explicitly approved device enrollment. No chat commands here."""
import asyncio
import hashlib
import ipaddress
import json
import secrets
import socket
import time
from pathlib import Path
from urllib.parse import urlsplit
from aiohttp import web

SERVICE_TYPE = '_watchchat._tcp.local.'

def public_url(value):
    p=urlsplit(value.strip())
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
        raise ValueError('公网地址需为完整HTTPS域名，不包含路径或登录信息')
    host=p.hostname.lower()
    if '.' not in host or host.endswith(('.local','.lan','.internal')) or p.port not in (None,443):
        raise ValueError('公网地址需使用域名及标准HTTPS端口')
    try:ipaddress.ip_address(host)
    except ValueError:pass
    else:raise ValueError('公网模式请使用固定域名')
    return 'https://'+host

def verification_code(computer_id,pin,mode,url,request_id,claim_hash):
    message='\n'.join(['watch-pair-v1',computer_id,pin,mode,url,request_id,claim_hash])
    raw=hashlib.sha256(message.encode()).hexdigest()[:12].upper()
    return '-'.join(raw[i:i+4] for i in range(0,12,4))

class Connections:
    def __init__(self,config,directory,clock=time.monotonic):
        self.config=config;self.directory=Path(directory);self.clock=clock
        self.path=self.directory/'paired-devices.json'
        self.data=json.loads(self.path.read_text(encoding='utf8')) if self.path.exists() else {'adminToken':secrets.token_urlsafe(32),'devices':{}}
        self.window=0.;self.pending={};self.publisher=None
        self._save()
    def _save(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(self.path)
    def public_endpoint(self):
        path=self.directory/'public-endpoint.json'
        if not path.exists():return None
        value=json.loads(path.read_text(encoding='utf8'))
        value['url']=public_url(value['url'])
        port=int(value['originPort'])
        if not 1024<=port<=65535 or port==int(self.config['port']):raise ValueError('公网本地转发端口无效或与局域网端口冲突')
        value['originPort']=port
        return value
    def authorized(self,token):
        if not token:return False
        digest=hashlib.sha256(token.encode()).hexdigest()
        return any(not d.get('revoked') and secrets.compare_digest(digest,d['tokenHash']) for d in self.data['devices'].values())
    def _admin(self,request):
        peer=request.remote
        if peer not in ('127.0.0.1','::1') or not secrets.compare_digest(request.headers.get('Authorization',''),'Bearer '+self.data['adminToken']):
            raise web.HTTPForbidden(text='配对管理仅允许本机操作')
    def _prune(self):
        now=self.clock();self.pending={k:v for k,v in self.pending.items() if v['expires']>now}
    def _claim(self,request):
        self._prune();item=self.pending.get(request.match_info['request_id'])
        claim=request.headers.get('Authorization','').removeprefix('Bearer ')
        if not item or not secrets.compare_digest(hashlib.sha256(claim.encode()).hexdigest(),item['claimHash']):
            raise web.HTTPNotFound(text='配对已结束，请重新开始')
        return item
    async def info(self,request):
        return web.json_response({'protocol':1,'computerId':self.config['computerId'],'certificateSha256':self.config['certificateSha256'],'pairingOpen':self.clock()<self.window})
    async def create(self,request):
        self._prune()
        if self.clock()>=self.window:raise web.HTTPForbidden(text='请先在电脑运行“开启电脑配对.cmd”')
        d=await request.json()
        if not isinstance(d,dict):raise web.HTTPBadRequest(text='配对请求无效')
        rid=d.get('requestId','');claim=d.get('claimHash','');mode=d.get('mode');url=d.get('url','')
        import re
        if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',rid) or not isinstance(claim,str) or not re.fullmatch(r'[a-f0-9]{64}',claim):
            raise web.HTTPBadRequest(text='配对请求无效')
        if not isinstance(url,str) or len(url)>1024:raise web.HTTPBadRequest(text='配对地址无效')
        if mode=='public':
            try:endpoint=self.public_endpoint();url=public_url(url)
            except (ValueError,KeyError):raise web.HTTPBadRequest(text='公网入口尚未正确配置')
            if not endpoint or endpoint['url']!=url:raise web.HTTPForbidden(text='公网域名与电脑配置不一致')
        elif mode=='lan':
            p=urlsplit(url)
            if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in ('','/'):
                raise web.HTTPBadRequest(text='局域网地址无效')
            url=url.rstrip('/')
        else:raise web.HTTPBadRequest(text='连接模式无效')
        if rid in self.pending:
            old=self.pending[rid]
            if old['claimHash']!=claim or old['url']!=url or old['mode']!=mode:raise web.HTTPConflict(text='配对请求发生变化')
            return web.json_response({'state':old['state']})
        if len(self.pending)>=5:raise web.HTTPTooManyRequests(text='配对请求较多，请稍后再试')
        name=''.join(c for c in str(d.get('deviceName','手表')) if c.isprintable())[:40]
        self.pending[rid]={'claimHash':claim,'mode':mode,'url':url,'deviceName':name,'expires':self.clock()+180,'state':'waiting',
            'code':verification_code(self.config['computerId'],self.config['certificateSha256'],mode,url,rid,claim)}
        return web.json_response({'state':'waiting'})
    async def status(self,request):
        item=self._claim(request)
        result={'state':item['state']}
        if item['state']=='approved':
            result.update(computerId=self.config['computerId'],computerName=self.config['computerName'],certificateSha256=self.config['certificateSha256'],token=item['token'])
        return web.json_response(result)
    async def finish(self,request):
        self._claim(request);self.pending.pop(request.match_info['request_id'],None)
        return web.json_response({'ok':True})
    async def window_control(self,request):
        self._admin(request);d=await request.json();self.window=self.clock()+180 if d.get('open') else 0
        return web.json_response({'open':self.window>self.clock(),'expiresIn':180 if self.window>self.clock() else 0})
    async def pending_list(self,request):
        self._admin(request);self._prune()
        return web.json_response({'requests':[dict(requestId=k,code=v['code'],deviceName=v['deviceName'],mode=v['mode'],state=v['state'],expiresIn=max(0,int(v['expires']-self.clock()))) for k,v in self.pending.items() if v['state']=='waiting']})
    async def decide(self,request):
        self._admin(request);self._prune();d=await request.json();item=self.pending.get(d.get('requestId'))
        if not item:raise web.HTTPNotFound(text='配对请求已结束')
        if item['state']!='waiting':return web.json_response({'state':item['state']})
        if d.get('approve') is True:
            token=secrets.token_urlsafe(32);device_id=secrets.token_hex(12)
            self.data['devices'][device_id]={'name':item['deviceName'],'tokenHash':hashlib.sha256(token.encode()).hexdigest(),'createdAt':int(time.time()),'revoked':False}
            self._save();item.update(state='approved',token=token)
        else:item['state']='denied'
        return web.json_response({'state':item['state']})
    async def device_list(self,request):
        self._admin(request)
        return web.json_response({'devices':[dict(id=k,name=v['name'],revoked=v.get('revoked',False)) for k,v in self.data['devices'].items()]})
    async def revoke(self,request):
        self._admin(request);d=await request.json();item=self.data['devices'].get(d.get('deviceId'))
        if not item:raise web.HTTPNotFound(text='设备不存在')
        item['revoked']=True;self._save()
        return web.json_response({'ok':True})
    def routes(self,app):
        app.add_routes([web.get('/api/connect/info',self.info),web.post('/api/connect/requests',self.create),
            web.get('/api/connect/requests/{request_id}',self.status),web.post('/api/connect/requests/{request_id}/finish',self.finish),
            web.post('/api/connect/admin/window',self.window_control),web.get('/api/connect/admin/pending',self.pending_list),
            web.post('/api/connect/admin/decide',self.decide),web.get('/api/connect/admin/devices',self.device_list),web.post('/api/connect/admin/revoke',self.revoke)])
    async def start(self,app):
        try:
            from zeroconf import ServiceInfo,IPVersion
            from zeroconf.asyncio import AsyncZeroconf
            from zeroconf import InterfaceChoice
            import ifaddr
            addresses=sorted({item.ip for adapter in ifaddr.get_adapters() for item in adapter.ips
                if isinstance(item.ip,str) and not ipaddress.ip_address(item.ip).is_loopback and not ipaddress.ip_address(item.ip).is_link_local})
            if not addresses:return
            self.publisher=AsyncZeroconf(ip_version=IPVersion.V4Only,interfaces=InterfaceChoice.All)
            self.service=ServiceInfo(SERVICE_TYPE,'WatchChat-'+self.config['computerId'][:12]+'.'+SERVICE_TYPE,
                parsed_addresses=addresses,port=int(self.config['port']),properties={'id':self.config['computerId'],'name':self.config['computerName'],'pin':self.config['certificateSha256'],'v':'1','ipv4':','.join(addresses[:14])},server='watchchat-'+self.config['computerId'][:12]+'.local.')
            await self.publisher.async_register_service(self.service,allow_name_change=True)
        except Exception as e:
            import logging
            logging.getLogger('watch-chat').warning('局域网广播暂不可用: %s',type(e).__name__)
            if self.publisher:await self.publisher.async_close();self.publisher=None
    async def close(self,app):
        if self.publisher:
            await self.publisher.async_unregister_service(self.service);await self.publisher.async_close();self.publisher=None
        self.pending.clear();self.window=0
