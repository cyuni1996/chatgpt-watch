"""Local TLS fixture for navigation/power checks. Never connects to Codex or executes actions."""
import asyncio
import json
import ssl
import time
from pathlib import Path
from aiohttp import web

ROOT=Path(__file__).resolve().parents[1]
requests=[]
held=set()
active=0
cancelled=0

async def api(request):
    global active,cancelled
    path=request.path
    requests.append({'path':path,'time':time.monotonic()})
    if path in held or path=='/api/speak':
        active+=1
        try:
            while request.transport is not None and not request.transport.is_closing():
                await asyncio.sleep(.05)
            cancelled+=1
            return web.Response(status=499)
        finally:
            active-=1
    if request.method!='GET':
        return web.json_response({'error':'Read-only test fixture'},status=403)
    if path=='/api/state':
        return web.json_response({
            'id':'power-navigation-fixture','threadId':'fixture-thread','title':'导航与省电测试',
            'connected':True,'busy':False,'canInterrupt':False,'waitingOnApproval':False,
            'messages':[{'id':'fixture-reply','role':'assistant','phase':'final','text':'这是隔离测试页面。不会发送消息或操作电脑。'}],
            'settings':{},'approvals':[],'hasOlder':False,
        })
    if path=='/api/conversations':
        return web.json_response({'conversations':[{'threadId':'fixture-thread','title':'隔离测试会话','pinned':False,'archived':False}],'nextCursor':None})
    if path=='/api/usage':
        return web.json_response({'groups':[],'updatedAt':'2026-11-04T00:00:00Z','availableResetCount':None})
    if path=='/api/models':
        return web.json_response({'models':[{'id':'fixture-model','name':'隔离测试模型','efforts':['low','high']}]})
    return web.json_response({'error':'Unsupported test endpoint'},status=404)

async def stats(request):
    return web.json_response({'requests':requests,'active':active,'cancelled':cancelled})

async def hold(request):
    path=request.query.get('path','/api/state')
    if request.query.get('enabled','1')=='1':held.add(path)
    else:held.discard(path)
    return web.json_response({'held':sorted(held)})

if __name__=='__main__':
    app=web.Application()
    app.router.add_get('/fixture/stats',stats)
    app.router.add_get('/fixture/hold',hold)
    app.router.add_route('*','/api/{tail:.*}',api)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(ROOT/'.local/server.pem',ROOT/'.local/server-key.pem')
    web.run_app(app,host='127.0.0.1',port=8767,ssl_context=context,access_log=None)
