"""Loopback-only project UI acceptance fixture; never opens a desktop connection."""
import argparse,json,ssl
from aiohttp import web
from computer_runtime import runtime_directory

PROJECTS=[{'id':'fixture-watch','name':'Sample Watch','path':'E:/fixture/watch'}, {'id':'fixture-notes','name':'Sample Notes','path':'E:/fixture/notes'}]
events=[]; reads=0; updated=False; approval_pending=False
sessions={}; original=''
def base(key,project=None):
    return {'id':key,'threadId':None,'title':'新的对话','projectId':project['id'] if project else None,'projectName':project['name'] if project else None,'messages':[],'settings':{},'connected':True,'busy':False,'approvals':[],'error':'','canInterrupt':False}
def status(code):
    labels={'running':'运行中','waiting':'等你回复','unread':'有新回复','idle':'空闲'}
    return {'status':code,'statusLabel':labels[code],'busy':code in ['running','waiting'],'unread':code=='unread'}
def chats():
    values=[]
    for key,title,project,code in [('fixture-running','隔离运行对话',PROJECTS[0],'running'),('fixture-waiting','隔离等待回复',PROJECTS[0],'waiting'),('fixture-unread','隔离新回复',PROJECTS[0],'unread'),('fixture-idle','隔离空闲对话',PROJECTS[0],'idle'),('fixture-notes-a','另一个项目对话',PROJECTS[1],'idle'),('fixture-notes-b','另一个未读对话',PROJECTS[1],'unread'),('isolated-original','返回原聊天',None,'idle')]:
        if updated and key=='fixture-running':code='waiting'
        values.append({'threadId':key,'title':title,'projectId':project['id'] if project else None,'projectName':project['name'] if project else None,'pinned':False,'archived':False,**status(code)})
    return values
async def api(request):
    global reads,approval_pending
    path=request.path
    if path=='/api/state':
        reads+=1;value=dict(sessions.get(request.query.get('sessionId'),sessions[original]))
        if approval_pending:
            value.update(waitingOnApproval=True,approvals=[{'token':'a'*64,'title':'请选择回复','details':'隔离 UI 验收，不会操作电脑。','questions':[{'id':'response','question':'选择一个方案','required':True,'options':[{'label':'方案一'},{'label':'方案二'}]}],'actions':[{'id':'answer','label':'提交选择'},{'id':'cancel','label':'取消'}]}])
        return web.json_response(value)
    if path=='/api/models':return web.json_response({'models':[]})
    if path=='/api/usage':return web.json_response({'groups':[]})
    if path=='/api/projects':return web.json_response({'projects':PROJECTS})
    if path=='/api/conversations':return web.json_response({'conversations':chats(),'projects':PROJECTS,'nextCursor':None})
    if request.method!='POST':raise web.HTTPForbidden()
    data=await request.json();events.append({'path':path,'data':data})
    if path=='/api/approval':
        approval_pending=False;return web.json_response({'state':sessions[original]})
    if path=='/api/conversations/status':return web.json_response({'states':{v['threadId']:{k:v[k] for k in ['status','statusLabel','busy','unread']} for v in chats()}})
    if path in ['/api/session/new','/api/session/project']:
        project=next((p for p in PROJECTS if p['id']==data.get('projectId')),None)
        if path.endswith('new'):
            key='fixture-draft-'+str(len(sessions));sessions[key]=base(key,project)
            return web.json_response({'sessionId':key,'state':sessions[key]})
        value=sessions[data['sessionId']];value.update(projectId=project['id'] if project else None,projectName=project['name'] if project else None)
        return web.json_response(value)
    if path=='/api/message':
        value=sessions[data['sessionId']];value.update(threadId='fixture-created',messages=[{'id':'u','role':'user','text':data['text']}])
        events.append({'path':'fixture-create','projectId':value['projectId']})
        return web.json_response(value)
    if path=='/api/session/link':return web.json_response(sessions[original])
    raise web.HTTPForbidden()
async def stats(request):return web.json_response({'events':events,'stateReads':reads})
async def pending(request):
    global approval_pending
    approval_pending=True;return web.json_response({'ok':True})
async def update(request):
    global updated
    updated=True;return web.json_response({'ok':True})
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--session-id',required=True);parser.add_argument('--title');parser.add_argument('--long-messages',action='store_true');args=parser.parse_args();original=args.session_id
    sessions[original]=base(original);sessions[original].update(threadId='isolated-original',title='隔离项目验收')
    if args.title:sessions[original].update(title=args.title,projectId='fixture-watch',projectName='Sample Watch')
    if args.long_messages:sessions[original]['messages']=[{'id':'reading-preview','role':'assistant','phase':'final','text':'\n'.join(f'第{i}行：保留原字号。' for i in range(1,21))}]
    directory=runtime_directory();context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(directory/'server.pem',directory/'server-key.pem')
    app=web.Application();app.router.add_get('/fixture/stats',stats);app.router.add_get('/fixture/update',update);app.router.add_get('/fixture/pending',pending);app.router.add_route('*','/api/{tail:.*}',api)
    web.run_app(app,host='127.0.0.1',port=8767,ssl_context=context,access_log=None)
