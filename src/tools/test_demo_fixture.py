import unittest
from aiohttp.test_utils import TestClient, TestServer

from demo_fixture import make_demo, TOKEN


class DemoFixtureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = TestClient(TestServer(make_demo()))
        await self.client.start_server()
        self.headers = {'Authorization': 'Bearer ' + TOKEN}

    async def asyncTearDown(self):
        await self.client.close()

    async def test_demo_requires_its_own_token_and_rejects_real_task_operations(self):
        self.assertEqual(401, (await self.client.get('/api/state')).status)
        for path in ('/api/message', '/api/conversation/action', '/api/conversation/open', '/api/transcribe'):
            self.assertEqual(403, (await self.client.post(path, json={}, headers=self.headers)).status)

    async def test_stop_is_bound_to_demo_turn_and_changes_only_fixture(self):
        await self.client.get('/fixture/stage/busy')
        value = await (await self.client.get('/api/state', headers=self.headers)).json()
        self.assertTrue(value['canInterrupt'])
        self.assertEqual(409, (await self.client.post('/api/interrupt', json={'turnId': 'wrong'}, headers=self.headers)).status)
        response = await self.client.post('/api/interrupt', json={'turnId': 'demo-turn'}, headers=self.headers)
        self.assertFalse((await response.json())['state']['busy'])

    async def test_confirmation_is_bound_to_synthetic_request(self):
        await self.client.get('/fixture/stage/approval')
        self.assertEqual(409, (await self.client.post('/api/approval', json={'token': 'wrong'}, headers=self.headers)).status)
        value = await (await self.client.post('/api/approval', json={'token': 'demo-confirmation'}, headers=self.headers)).json()
        self.assertEqual([], value['state']['approvals'])


if __name__ == '__main__':
    unittest.main()
