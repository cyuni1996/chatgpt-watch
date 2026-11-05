"""Loopback-only UI fixture. No desktop client, message sending, or real approval execution."""
import argparse
import json
import ssl
import sys
from pathlib import Path
from aiohttp import web
from computer_runtime import runtime_directory

mode='idle'
events=[]
session_id=''
state_reads=0

def state():
    approval={
        'token':'a'*64,'title':'请选择回复（隔离验收）','details':'这里只验证界面，不会操作电脑。',
        'questions':[{'id':'response','question':'本次怎么回复？','required':True,
            'options':[{'label':'方案一','description':'第一个测试选项'},{'label':'方案二','description':'第二个测试选项'}]}],
        'actions':[{'id':'answer','label':'提交选择'},{'id':'cancel','label':'取消'}],
    }
    return {'id':session_id,'threadId':'isolated-ui-thread','title':'布局与手势验收',
        'connected':True,'busy':mode=='busy','canInterrupt':mode=='busy',
        'turnId':'isolated-turn' if mode=='busy' else None,'waitingOnApproval':mode=='approval',
        'approvals':[approval] if mode=='approval' else [],'hasOlder':False,'settings':{},
        'messages':[{'id':'isolated-reply','role':'assistant','phase':'final',
            'text':'这是一段隔离界面测试内容。\n'*12}]}

async def api(request):
    global mode,state_reads
    if request.path=='/api/state':
        state_reads+=1
        return web.json_response(state())
    if request.path=='/api/usage':
        events.append({'path':'/api/usage'})
        return web.json_response({'groups':[],'updatedAt':'2026-11-04T00:00:00Z','availableResetCount':None})
    if request.path=='/api/interrupt' and request.method=='POST':
        data=await request.json()
        if data.get('sessionId')!=session_id or data.get('turnId')!='isolated-turn':return web.json_response({'error':'Wrong fixture turn'},status=409)
        events.append({'path':request.path,'turnId':data['turnId']});mode='idle'
        return web.json_response({'state':state(),'result':{}})
    if request.path=='/api/approval' and request.method=='POST':
        data=await request.json()
        if data.get('sessionId')!=session_id or data.get('token')!='a'*64:return web.json_response({'error':'Wrong fixture approval'},status=409)
        events.append({'path':request.path,'action':data.get('action'),'answers':data.get('answers')});mode='idle'
        return web.json_response({'state':state()})
    if request.path=='/api/conversations':return web.json_response({'conversations':[],'nextCursor':None})
    return web.json_response({'error':'Fixture rejects this operation'},status=403)

async def stage(request):
    global mode
    mode=request.match_info['mode']
    if mode not in ['idle','busy','approval']:raise web.HTTPBadRequest()
    return web.json_response({'stage':mode})

async def stats(request):return web.json_response({'mode':mode,'events':events,'stateReads':state_reads})

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--session-id',required=True);args=parser.parse_args()
    session_id=args.session_id
    directory=runtime_directory()
    app=web.Application()
    app.router.add_get('/fixture/stage/{mode}',stage);app.router.add_get('/fixture/stats',stats)
    app.router.add_route('*','/api/{tail:.*}',api)
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(directory/'server.pem',directory/'server-key.pem')
    web.run_app(app,host='127.0.0.1',port=8767,ssl_context=context,access_log=None)
