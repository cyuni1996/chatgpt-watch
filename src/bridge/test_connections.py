import hashlib,json,ssl,tempfile,unittest
from pathlib import Path
from aiohttp import TCPConnector
from aiohttp.test_utils import TestClient,TestServer
from connections import Connections,internet_proof
from server import Companion,identity,make_app
from test_sync import FakeDesktop


class ConnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = 100
        self.config = {'computerId':'pc-one','computerName':'测试电脑','port':8766,'certificateSha256':'a'*64}
        self.connection = Connections(self.config,self.tmp.name,clock=lambda:self.now)
        async def noop(app):
            pass
        self.connection.start = noop
        self.companion = Companion('legacy-secret',self.tmp.name,desktop=FakeDesktop())
        self.client = TestClient(TestServer(make_app(self.companion,self.connection)))
        await self.client.start_server()
        self.addAsyncCleanup(self.client.close)
        self.admin = {'Authorization':'Bearer '+self.connection.data['adminToken']}
        self.claim = 'random-watch-claim-secret-256-bits'
        self.headers = {'Authorization':'Bearer '+self.claim}
        self.window = {'open':True,'mode':'watch'}
        self.data = {'requestId':'request-for-watch-one','claimHash':hashlib.sha256(self.claim.encode()).hexdigest(),
            'deviceName':'手表','mode':'lan','url':'https://192.168.1.2:8766','confirmation':'watch','lanProof':self.connection.lan_proof}

    async def secure_client(self):
        _,cert,key = identity(Path(self.tmp.name))
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert,key)
        server = TestServer(make_app(self.companion,self.connection),scheme='https')
        await server.start_server(ssl=context)
        client = TestClient(server,connector=TCPConnector(ssl=False))
        self.addAsyncCleanup(client.close)
        return client

    async def open(self):
        result = await self.client.post('/api/connect/admin/window',json=self.window,headers=self.admin)
        self.assertEqual(result.status,200)

    async def test_removed_pairing_routes_and_modes_are_rejected(self):
        client = await self.secure_client()
        self.assertEqual((await client.post('/api/connect/admin/window',json={'open':True},headers=self.admin)).status,400)
        self.assertEqual((await client.get('/api/connect/admin/pending',headers=self.admin)).status,404)
        self.assertEqual((await client.post('/api/connect/admin/decide',json={},headers=self.admin)).status,404)
        self.assertEqual((await client.post('/api/connect/requests/request-for-watch-one/finish',json={},headers=self.headers)).status,404)
        await self.open()
        for data in (dict(self.data,mode='public'),dict(self.data,confirmation='local'),dict(self.data,confirmation=None)):
            self.assertEqual((await client.post('/api/connect/requests',json=data,headers=self.headers)).status,400)
        self.assertEqual(self.connection.data['devices'],{})

    async def test_watch_confirmation_requires_tls_discovery_proof_and_single_lan_window(self):
        client = await self.secure_client()
        endpoint = '/api/connect/requests'
        path = endpoint+'/'+self.data['requestId']
        self.assertEqual((await client.post(endpoint,json=self.data,headers=self.headers)).status,403)
        self.assertEqual((await client.post('/api/connect/admin/window',json=self.window)).status,403)
        await self.open()
        self.assertEqual((await self.client.post(endpoint,json=self.data,headers=self.headers)).status,400)
        self.assertEqual((await client.post(endpoint,json=dict(self.data,lanProof=''),headers=self.headers)).status,403)
        self.assertEqual((await client.post(endpoint,json=self.data)).status,403)
        self.assertEqual(self.connection.data['devices'],{})
        for _ in range(2):
            result = await client.post(endpoint,json=self.data,headers=self.headers)
            self.assertEqual(await result.json(),{'state':'approved'})
        self.assertEqual(len(self.connection.data['devices']),1)
        self.assertEqual((await client.get(path)).status,404)
        result = await (await client.get(path,headers=self.headers)).json()
        self.assertTrue(self.connection.authorized(result['token']))
        changed = dict(self.data,url='https://192.168.1.3:8766')
        self.assertEqual((await client.post(endpoint,json=changed,headers=self.headers)).status,409)
        second = dict(self.data,requestId='request-for-watch-two')
        self.assertEqual((await client.post(endpoint,json=second,headers=self.headers)).status,403)
        await self.open()
        self.now += 181
        self.assertEqual((await client.get(path,headers=self.headers)).status,404)
        self.assertEqual((await client.post(endpoint,json=second,headers=self.headers)).status,403)

    async def test_device_token_persists_and_revocation_blocks_chat_but_not_other_clients(self):
        client = await self.secure_client()
        await self.open()
        self.assertEqual((await client.post('/api/connect/requests',json=self.data,headers=self.headers)).status,200)
        result = await (await client.get('/api/connect/requests/'+self.data['requestId'],headers=self.headers)).json()
        token = result['token']
        headers = {'Authorization':'Bearer '+token}
        self.assertEqual((await self.client.get('/api/sessions',headers=headers)).status,200)
        self.assertEqual((await self.client.get('/api/sessions',headers={'Authorization':token})).status,401)
        self.assertEqual((await self.client.get('/api/connect/admin/devices',headers=headers)).status,403)
        self.assertNotIn(token,(Path(self.tmp.name)/'paired-devices.json').read_text())
        self.assertTrue(Connections(self.config,self.tmp.name).authorized(token))
        device = next(iter(self.connection.data['devices']))
        await self.client.post('/api/connect/admin/revoke',json={'deviceId':device},headers=self.admin)
        self.assertEqual((await self.client.get('/api/sessions',headers=headers)).status,401)
        self.assertEqual((await self.client.get('/api/sessions',headers={'Authorization':'Bearer legacy-secret'})).status,200)

    async def test_malformed_lan_requests_and_excess_pending_requests_are_rejected(self):
        client = await self.secure_client()
        await self.open()
        for data in ([],{},dict(self.data,url={}),dict(self.data,url='https://['),dict(self.data,claimHash='short')):
            self.assertEqual((await client.post('/api/connect/requests',json=data,headers=self.headers)).status,400)
        for index in range(5):
            await self.open()
            data = dict(self.data,requestId='request-number-%03d'%index)
            self.assertEqual((await client.post('/api/connect/requests',json=data,headers=self.headers)).status,200)
        await self.open()
        self.assertEqual((await client.post('/api/connect/requests',json=self.data,headers=self.headers)).status,429)

    async def test_internet_code_requires_local_admin_and_is_bound_to_tls_and_single_use(self):
        admin_path = '/api/connect/admin/internet'
        pair_path = '/api/connect/internet'
        self.assertEqual((await self.client.post(admin_path,json={})).status,403)
        await self.client.post('/api/connect/admin/window',json={'mode':'watch','open':True},headers=self.admin)
        window = await (await self.client.post(admin_path,json={},headers=self.admin)).json()
        self.assertEqual(self.connection.watch_window,0)
        self.assertEqual(window['expiresIn'],180)
        code = window['code']
        nonce = '1'*32
        pin = self.config['certificateSha256']
        valid = {'nonce':nonce,'proof':internet_proof(code,'watch',pin,nonce)}
        self.assertEqual((await self.client.post(pair_path,json=valid)).status,403)
        _,cert,key=identity(Path(self.tmp.name))
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert,key)
        server=TestServer(make_app(self.companion,self.connection),scheme='https')
        await server.start_server(ssl=context)
        async with TestClient(server,connector=TCPConnector(ssl=False)) as client:
            info=await (await client.get('/api/connect/info')).json()
            self.assertNotIn(code,str(info))
            self.assertNotIn(self.connection.lan_proof,str(info))
            wrong_pin = dict(valid,proof=internet_proof(code,'watch','b'*64,nonce))
            self.assertEqual((await client.post(pair_path,json=wrong_pin)).status,403)
            self.assertEqual(self.connection.data['devices'],{})
            result=await (await client.post(pair_path,json=valid)).json()
            self.assertTrue(self.connection.authorized(result['token']))
            self.assertEqual(result['proof'],internet_proof(code,'computer',pin,nonce,result['computerId'],result['token']))
            self.assertEqual((await client.post(pair_path,json=valid)).status,403)
            code=(await (await client.post(admin_path,json={},headers=self.admin)).json())['code']
            self.now+=180
            self.assertEqual((await client.post(pair_path,json=dict(valid,proof=internet_proof(code,'watch',pin,nonce)))).status,403)
            self.assertEqual(len(self.connection.data['devices']),1)


if __name__=='__main__':unittest.main()
