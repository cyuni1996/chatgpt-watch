"""LAN discovery and explicitly approved device enrollment. No chat commands here."""
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time
from pathlib import Path
from urllib.parse import urlsplit
from aiohttp import web

SERVICE_TYPE = '_watchchat._tcp.local.'
PAIRING_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'

def internet_proof(code, role, pin, nonce, *fields):
    # Bind proofs to the end-to-end TLS certificate and separate the two directions.
    message = '\n'.join(('watch-internet-v1', role, pin, nonce, *fields))
    return hmac.new(code.encode('ascii'), message.encode('utf8'), hashlib.sha256).hexdigest()


class Connections:
    def __init__(self,config,directory,clock=time.monotonic):
        self.config=config;self.directory=Path(directory);self.clock=clock
        self.path=self.directory/'paired-devices.json'
        self.data=json.loads(self.path.read_text(encoding='utf8')) if self.path.exists() else {'adminToken':secrets.token_urlsafe(32),'devices':{}}
        self.watch_window=0.;self.pending={};self.publisher=None
        self.lan_proof = secrets.token_hex(24)
        self.internet_code = None
        self.internet_deadline = 0.
        self._save()
    def _save(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(self.path)
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
        return web.json_response({'protocol':1,'computerId':self.config['computerId'],'computerName':self.config['computerName'],
            'certificateSha256':self.config['certificateSha256'],'watchConfirmation':request.secure,
            'lanProofRequired':True,
            'watchPairingOpen':request.secure and self.clock()<self.watch_window})
    async def create(self,request):
        self._prune()
        data = await request.json()
        if not isinstance(data,dict):
            raise web.HTTPBadRequest(text='配对请求无效')
        if data.get('mode') != 'lan' or data.get('confirmation') != 'watch' or not request.secure:
            raise web.HTTPBadRequest(text='此入口仅支持局域网扫描配对')
        request_id, claim, url = data.get('requestId'), data.get('claimHash'), data.get('url')
        if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}',request_id) or not isinstance(claim,str) or not re.fullmatch(r'[a-f0-9]{64}',claim):
            raise web.HTTPBadRequest(text='配对请求无效')
        bearer = request.headers.get('Authorization','').removeprefix('Bearer ')
        if not secrets.compare_digest(hashlib.sha256(bearer.encode()).hexdigest(),claim):
            raise web.HTTPForbidden(text='配对凭据不匹配')
        proof = data.get('lanProof')
        if not isinstance(proof,str) or not re.fullmatch(r'[a-f0-9]{48}',proof) or not secrets.compare_digest(proof,self.lan_proof):
            raise web.HTTPForbidden(text='首次局域网配对请在手表上扫描并选择电脑')
        if not isinstance(url,str) or len(url)>1024:
            raise web.HTTPBadRequest(text='局域网地址无效')
        try:
            endpoint = urlsplit(url)
            if endpoint.scheme!='https' or not endpoint.hostname or endpoint.username is not None or endpoint.password is not None or endpoint.query or endpoint.fragment or endpoint.path not in ('','/'):
                raise ValueError('invalid endpoint')
        except ValueError:
            raise web.HTTPBadRequest(text='局域网地址无效') from None
        url = url.rstrip('/')
        old = self.pending.get(request_id)
        if old:
            if old['claimHash']!=claim or old['url']!=url:
                raise web.HTTPConflict(text='配对请求发生变化')
            return web.json_response({'state':'approved'})
        if self.clock()>=self.watch_window:
            raise web.HTTPForbidden(text='请在电脑运行 Start Companion.cmd 并按 L')
        if len(self.pending)>=5:
            raise web.HTTPTooManyRequests(text='配对请求较多，请稍后再试')
        name = ''.join(c for c in str(data.get('deviceName','手表')) if c.isprintable())[:40]
        item = {'claimHash':claim,'url':url,'expires':self.clock()+180,'token':self._issue_token(name)}
        self.watch_window = 0.
        self.pending[request_id] = item
        return web.json_response({'state':'approved'})
    async def open_internet_pairing(self, request):
        self._admin(request)
        self.internet_code = ''.join(secrets.choice(PAIRING_ALPHABET) for _ in range(16))
        self.internet_deadline = self.clock() + 180
        self.watch_window = 0.
        return web.json_response({'code':self.internet_code,'expiresIn':180},headers={'Cache-Control':'no-store'})
    async def internet_pair(self, request):
        if not request.secure:
            raise web.HTTPForbidden(text='外网配对需要直达电脑的 HTTPS 连接')
        data = await request.json()
        nonce = data.get('nonce','') if isinstance(data,dict) else ''
        proof = data.get('proof','') if isinstance(data,dict) else ''
        if not isinstance(nonce,str) or not re.fullmatch(r'[a-f0-9]{32}',nonce) or not isinstance(proof,str) or not re.fullmatch(r'[a-f0-9]{64}',proof):
            raise web.HTTPBadRequest(text='外网配对请求无效')
        code = self.internet_code
        pin = self.config['certificateSha256']
        if not code or self.clock() >= self.internet_deadline or not secrets.compare_digest(proof,internet_proof(code,'watch',pin,nonce)):
            raise web.HTTPForbidden(text='外网配对码不正确或已失效，请在电脑生成新码')
        token = self._issue_token('外网配对手表')
        self.internet_code = None
        computer_id = self.config['computerId']
        return web.json_response({
            'computerId':computer_id,'computerName':self.config['computerName'],'token':token,
            'proof':internet_proof(code,'computer',pin,nonce,computer_id,token),
        },headers={'Cache-Control':'no-store'})
    async def status(self,request):
        item = self._claim(request)
        return web.json_response({'state':'approved','computerId':self.config['computerId'],
            'computerName':self.config['computerName'],'certificateSha256':self.config['certificateSha256'],
            'token':item['token']},headers={'Cache-Control':'no-store'})

    async def window_control(self,request):
        self._admin(request)
        data = await request.json()
        if not isinstance(data,dict) or data.get('mode')!='watch':
            raise web.HTTPBadRequest(text='配对窗口模式无效')
        opened = data.get('open') is True
        self.watch_window = self.clock()+180 if opened else 0.
        return web.json_response({'open':opened,'expiresIn':180 if opened else 0,'mode':'watch'})

    def _issue_token(self,name):
        token=secrets.token_urlsafe(32);device_id=secrets.token_hex(12)
        devices=self.data['devices']
        devices[device_id]={'name':name,'tokenHash':hashlib.sha256(token.encode()).hexdigest(),'createdAt':int(time.time()),'revoked':False}
        try:self._save()
        except OSError:
            del devices[device_id]
            raise
        return token
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
            web.get('/api/connect/requests/{request_id}',self.status),
            web.post('/api/connect/internet',self.internet_pair),web.post('/api/connect/admin/internet',self.open_internet_pairing),
            web.post('/api/connect/admin/window',self.window_control),
            web.get('/api/connect/admin/devices',self.device_list),web.post('/api/connect/admin/revoke',self.revoke)])
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
                parsed_addresses=addresses,port=int(self.config['port']),properties={'id':self.config['computerId'],'name':self.config['computerName'],'pin':self.config['certificateSha256'],'pair':self.lan_proof,'v':'1','ipv4':','.join(addresses[:14])},server='watchchat-'+self.config['computerId'][:12]+'.local.')
            await self.publisher.async_register_service(self.service,allow_name_change=True)
        except Exception as e:
            import logging
            logging.getLogger('watch-chat').warning('局域网广播暂不可用: %s',type(e).__name__)
            if self.publisher:await self.publisher.async_close();self.publisher=None
    async def close(self,app):
        if self.publisher:
            await self.publisher.async_unregister_service(self.service);await self.publisher.async_close();self.publisher=None
        self.pending.clear();self.watch_window=0.
        self.internet_code=None;self.internet_deadline=0.
