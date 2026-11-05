import asyncio
import unittest
from aiohttp import web
from projects import local_projects, project_for_thread, thread_status
import test_sync

PROJECTS=[{'projectId':'watch','label':'Sample Watch','path':'C:/sample/sample-projects','projectKind':'local','hostId':'local'},
          {'projectId':'nested','label':'child','path':'c:/sample/sample-projects/child','projectKind':'local','hostId':'local'},
          {'projectId':'foreign','label':'remote','projectKind':'local','hostId':'remote'},
          {'projectId':'cloud','label':'cloud','projectKind':'chatgpt','hostId':None}]

class ProjectMappingTests(unittest.TestCase):
    def test_only_current_local_projects_are_creatable(self):
        self.assertEqual([p['id'] for p in local_projects({'projects':PROJECTS})],['watch','nested'])

    def test_native_id_has_priority_and_unknown_id_is_not_remapped(self):
        projects=local_projects({'projects':PROJECTS})
        self.assertEqual(project_for_thread({'projectId':'watch','cwd':'c:/sample/sample-projects/child'},projects)['id'],'watch')
        self.assertEqual(project_for_thread({'projectId':'foreign','cwd':'c:/sample/sample-projects'},projects)['name'],'未识别项目')

    def test_missing_project_uses_longest_case_insensitive_directory_boundary(self):
        projects=local_projects({'projects':PROJECTS})
        self.assertEqual(project_for_thread({'cwd':r'C:\SAMPLE\sample-projects\CHILD\sub'},projects)['id'],'nested')
        self.assertIsNone(project_for_thread({'cwd':'c:/sample/sample-projects2'},projects))
        self.assertIsNone(project_for_thread({'cwd':'sample-projects'},projects))

    def test_status_priorities_distinguish_running_waiting_unread_idle_unknown(self):
        self.assertEqual(thread_status({'status':'active','isUnread':True})['status'],'running')
        self.assertEqual(thread_status({'status':'idle','isUnread':True})['status'],'unread')
        for flag in ['waitingOnApproval','waitingOnUserInput']:
            self.assertEqual(thread_status({'status':'active'},{'status':{'type':'active','activeFlags':[flag]}})['status'],'waiting')
        self.assertEqual(thread_status({'status':'idle'})['status'],'idle')
        self.assertEqual(thread_status({'status':'notLoaded'})['statusLabel'],'未运行')
        self.assertIsNone(thread_status({'status':'idle'})['unread'])
        self.assertEqual(thread_status({})['status'],'unknown')
        self.assertEqual(thread_status({'status':'active'},{'status':{'type':'idle'}})['status'],'idle')

# Reuse the isolated HTTP fixture, without inheriting/rerunning its test methods.
class ProjectApiTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp=test_sync.CompanionTests.asyncSetUp
    asyncTearDown=test_sync.CompanionTests.asyncTearDown

    async def new_draft(self,project_id='watch'):
        self.desktop.projects=PROJECTS
        response=await self.client.post('/api/session/new',json={'projectId':project_id},headers=self.headers)
        self.assertEqual(response.status,200)
        return (await response.json())['state']

    async def test_project_picker_creates_only_local_draft_first_send_targets_project(self):
        draft=await self.new_draft()
        self.assertEqual(draft['projectName'],'Sample Watch');self.assertIsNone(draft['threadId'])
        self.assertFalse(any(n=='create_thread' for n,_ in self.desktop.calls))
        session=self.companion.sessions[draft['id']]
        await self.companion.submit(session,'fixture prompt','project-send')
        await asyncio.gather(*list(self.companion.work))
        target=next(p['target'] for n,p in self.desktop.calls if n=='create_thread')
        self.assertEqual(target,{'type':'project','projectId':'watch','environment':{'type':'local'}})
        self.assertEqual(session['projectId'],'watch')
        with self.assertRaises(web.HTTPConflict):await self.companion.set_project(session,None)

    async def test_projectless_remains_explicit_and_model_settings_survive_project_change(self):
        draft=await self.new_draft()
        session=self.companion.sessions[draft['id']];session['settings']={'model':'test','thinking':'high'}
        response=await self.client.post('/api/session/project',json={'sessionId':draft['id'],'projectId':None},headers=self.headers)
        self.assertEqual(response.status,200);self.assertEqual(session['settings'],{'model':'test','thinking':'high'})
        await self.companion.submit(session,'fixture prompt','none-send')
        await asyncio.gather(*list(self.companion.work))
        self.assertEqual(next(p['target'] for n,p in self.desktop.calls if n=='create_thread'),{'type':'projectless','directoryName':'watch-chat'})

    async def test_missing_or_foreign_project_fails_closed_without_sending(self):
        draft=await self.new_draft()
        for project_id in ['foreign','missing','cloud','']:
            response=await self.client.post('/api/session/new',json={'projectId':project_id},headers=self.headers)
            self.assertIn(response.status,(400,409))
        self.desktop.projects=[]
        with self.assertRaises(web.HTTPConflict):await self.companion.submit(self.companion.sessions[draft['id']],'fixture prompt','removed')
        self.assertEqual(self.companion.sessions[draft['id']]['outbox'],{})
        self.assertFalse(any(n=='create_thread' for n,_ in self.desktop.calls))

    async def test_cannot_reassign_real_or_pending_chat_project(self):
        self.desktop.projects=PROJECTS
        for session in [self.session,self.companion.sessions[self.companion.new_session()]]:
            if not session.get('threadId'):session['outbox']['pending']={'state':'unknown'}
            with self.assertRaises(web.HTTPConflict):await self.companion.set_project(session,'watch')

    async def test_history_groups_and_recent_unread_merge_and_live_waiting_status(self):
        self.desktop.projects=PROJECTS
        original=self.desktop.call
        async def grouped(name,params=None,**kwargs):
            if name=='list_threads':
                item={'id':'shared-thread','kind':'codex','hostId':'local','title':'Fixture','cwd':r'c:\sample\sample-projects','status':'active'}
                if params.get('mode')!='history':item['isUnread']=True
                return {'threads':[item]}
            value=await original(name,params,**kwargs)
            if name=='read_thread':value['thread']['status']={'type':'active','activeFlags':['waitingOnApproval']}
            return value
        self.desktop.call=grouped
        value=await (await self.client.get('/api/conversations',headers=self.headers)).json()
        item=value['conversations'][0]
        self.assertEqual((item['projectId'],item['projectName'],item['status'],item['unread']),('watch','Sample Watch','waiting',True))
        states=await (await self.client.post('/api/conversations/status',json={'threadIds':['shared-thread']},headers=self.headers)).json()
        self.assertEqual(states['states']['shared-thread']['statusLabel'],'等你回复')
        self.assertEqual(sum(n=='read_thread' for n,_ in self.desktop.calls),1)
        self.assertFalse(any(n in ('send_message_to_thread','create_thread') for n,_ in self.desktop.calls))

    async def test_unread_is_unknown_when_native_recent_summary_no_longer_contains_thread(self):
        await self.companion.recent_threads()
        self.companion.thread_summaries['old']={'id':'old','status':'idle','isUnread':True}
        self.companion.recent_time=-5
        state=await self.companion.conversation_states(['old'])
        self.assertIsNone(state['old']['unread'])
        self.assertEqual(state['old']['status'],'idle')

    async def test_status_ids_are_validated_and_endpoint_requires_auth(self):
        self.assertEqual((await self.client.get('/api/projects')).status,401)
        for ids in [None,'thread',['a']*1001,[1],['x'*101]]:
            self.assertEqual((await self.client.post('/api/conversations/status',json={'threadIds':ids},headers=self.headers)).status,400)
