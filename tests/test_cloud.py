import io
import json
import os
import unittest
from unittest.mock import patch
import cloud
import server


class CloudTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'DATABASE_BACKEND':'supabase', 'SUPABASE_URL':'https://test.supabase.co',
                                     'SUPABASE_PUBLISHABLE_KEY':'test-publishable'}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        settings = patch.object(cloud, 'google_enabled', return_value=False)
        settings.start()
        self.addCleanup(settings.stop)
        context = cloud.CURRENT.set(None)
        self.addCleanup(cloud.CURRENT.reset, context)
        self.session = {'access':'user-jwt','refresh':'refresh-token', 'user':{'id':'owner-1','email':'owner@example.com'},
                        'expires':99999999999,'local_expiry':99999999999}

    def test_logged_out_state_never_reads_local_data(self):
        with patch.object(server, 'local_snapshot') as local:
            state = server.state()
        local.assert_not_called()
        self.assertFalse(state['config']['signed_in'])
        self.assertEqual(state['agents'], [])

    def test_logged_out_mutation_is_rejected(self):
        with self.assertRaises(cloud.CloudError) as failure:
            server.save_agent({'name':'Test','instructions':'Take notes','tags':[]})
        self.assertEqual(failure.exception.status, 401)

    def test_user_scoped_request(self):
        with patch.object(cloud, 'request', return_value=[]) as request:
            cloud.Store(self.session).listing('mm_agents')
        self.assertIn('owner_id=eq.owner-1',request.call_args.args[0])
        self.assertEqual(request.call_args.args[3],'user-jwt')

    def test_payload_owner_cannot_be_overridden(self):
        with patch.object(cloud, 'request', return_value=[{'id':'1'}]) as request:
            cloud.Store(self.session).save('mm_agents',{'id':'1','owner_id':'other'})
        self.assertEqual(request.call_args.args[2]['owner_id'],'owner-1')

    def test_cloud_writes_do_not_use_sqlite(self):
        cloud.CURRENT.set(self.session)
        with patch.object(cloud,'request',return_value=[{'id':'1'}]),patch.object(server,'connect') as local:
            server.save_agent({'name':'Cloud agent','instructions':'Notes','tags':[]})
        local.assert_not_called()

    def test_missing_schema_has_no_silent_fallback(self):
        cloud.CURRENT.set(self.session)
        with patch.object(cloud,'request',side_effect=cloud.CloudError('Schema missing',503)),patch.object(server,'local_snapshot') as local:
            state=server.state()
        local.assert_not_called()
        self.assertFalse(state['config']['database_ready'])

    def test_login_tokens_stay_on_server(self):
        response={'access_token':'sensitive-access','refresh_token':'sensitive-refresh','expires_in':3600,
                  'user':{'id':'owner-1','email':'owner@example.com'}}
        with patch.object(cloud,'request',return_value=response):
            sid,result=cloud.login('owner@example.com','password')
        self.addCleanup(cloud.SESSIONS.pop,sid,None)
        self.assertNotIn('sensitive',json.dumps(result))
        cloud.bind('mm_session='+sid)
        self.assertEqual(cloud.store().owner,'owner-1')

    def test_email_confirmation_does_not_create_session(self):
        with patch.object(cloud,'request',return_value={'user':{'id':'owner-1'}}):
            sid,result=cloud.login('owner@example.com','password',signup=True)
        self.assertIsNone(sid)
        self.assertIn('confirmation',result['message'])

    def test_publishable_key_is_not_used_as_bearer_token(self):
        with patch.object(cloud.urllib.request,'urlopen',return_value=io.BytesIO(b'[]')) as opener:
            cloud.request('/rest/v1/mm_agents',access='user-jwt')
        req=opener.call_args.args[0]
        self.assertEqual(req.get_header('Apikey'),'test-publishable')
        self.assertEqual(req.get_header('Authorization'),'Bearer user-jwt')

    def test_atomic_import_uses_authenticated_rpc(self):
        with patch.object(cloud,'request',return_value={}) as request:
            cloud.Store(self.session).import_local({'agents':[],'meetings':[],'profile':{}})
        self.assertEqual(request.call_args.args[0],'/rest/v1/rpc/mm_import_workspace')
        self.assertEqual(request.call_args.args[3],'user-jwt')

    def test_signup_sends_profile_metadata(self):
        with patch.object(cloud, 'request', return_value={'user': {}}) as request:
            cloud.login('owner@example.com', 'password123', True, {'full_name': 'Owner', 'company': 'Team'})
        self.assertEqual(request.call_args.args[2]['data']['full_name'], 'Owner')

    def test_otp_supports_new_and_existing_accounts_without_creating_session(self):
        with patch.object(cloud, 'request', return_value={}) as request:
            cloud.send_code('owner@example.com', 'login')
        self.assertTrue(request.call_args.args[2]['create_user'])
        self.assertIsNone(cloud.CURRENT.get())

    def test_numeric_http_code_does_not_hide_auth_error_code(self):
        error = cloud.urllib.error.HTTPError('https://test.supabase.co/auth/v1/otp', 422, 'error', {},
            io.BytesIO(b'{"code":422,"error_code":"email_address_invalid","msg":"private data"}'))
        with patch.object(cloud.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(cloud.CloudError) as failure:
                cloud.send_code('invalid', 'login')
        self.assertEqual(str(failure.exception), 'Enter a valid email address.')
        self.assertEqual(failure.exception.status, 422)

    def test_auth_422_explains_signup_requirement_without_exposing_payload(self):
        error = cloud.urllib.error.HTTPError('https://test.supabase.co/auth/v1/otp', 422, 'error', {},
            io.BytesIO(json.dumps({'code': 'signups_not_allowed', 'message': 'private@example.com'}).encode()))
        with patch.object(cloud.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(cloud.CloudError) as failure:
                cloud.send_code('private@example.com', 'login')
        self.assertEqual(failure.exception.status, 422)
        self.assertIn('Sign up first', str(failure.exception))
        self.assertNotIn('private@example.com', str(failure.exception))

    def test_disabled_otp_is_not_reported_as_expired_code(self):
        error = cloud.urllib.error.HTTPError('https://test.supabase.co/auth/v1/otp', 422, 'error', {},
            io.BytesIO(b'{"code":"otp_disabled"}'))
        with patch.object(cloud.urllib.request, 'urlopen', side_effect=error):
            with self.assertRaises(cloud.CloudError) as failure:
                cloud.send_code('owner@example.com', 'login')
        self.assertIn('disabled', str(failure.exception))
        self.assertNotIn('expired', str(failure.exception))

    def test_recovery_verification_gates_password_change(self):
        response={'access_token':'access','refresh_token':'refresh','user':{'id':'owner-1','email':'owner@example.com'}}
        with patch.object(cloud,'request',return_value=response) as request:
            sid, result = cloud.verify_code('owner@example.com','123456','recovery')
        self.addCleanup(cloud.SESSIONS.pop,sid,None)
        self.assertEqual(request.call_args.args[2]['type'],'recovery')
        self.assertNotIn('access',result)
        cloud.bind('mm_session='+sid)
        with patch.object(cloud,'request',return_value={}) as update:
            cloud.change_password('newpassword123')
        self.assertEqual(update.call_args.kwargs['access'],'access')
        self.assertFalse(cloud.CURRENT.get()['recovery'])
        with self.assertRaises(cloud.CloudError):
            cloud.change_password('anotherpassword')

    def test_google_flow_requires_matching_cookie_and_is_one_time(self):
        with patch.object(cloud,'google_enabled',return_value=True):
            ident,result=cloud.start_google('http://127.0.0.1:8787/api/auth/callback')
        self.assertIn('code_challenge_method=s256',result['url'])
        self.assertNotIn(cloud.OAUTH[ident]['verifier'],result['url'])
        with self.assertRaises(cloud.CloudError):
            cloud.finish_google('mm_oauth=wrong','code')
        response={'access_token':'access','refresh_token':'refresh','user':{'id':'owner-1'}}
        with patch.object(cloud,'request',return_value=response) as exchange:
            sid,_=cloud.finish_google('mm_oauth='+ident,'code')
        self.addCleanup(cloud.SESSIONS.pop,sid,None)
        self.assertEqual(exchange.call_args.args[2]['auth_code'],'code')
        with self.assertRaises(cloud.CloudError):
            cloud.finish_google('mm_oauth='+ident,'code')


if __name__=='__main__':
    unittest.main()
