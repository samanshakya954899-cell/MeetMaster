import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
import server


class MeetingAppTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = patch.object(server, 'DB', Path(self.temp.name) / 'test.sqlite3')
        self.db.start()
        self.addCleanup(self.db.stop)
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        server.initialize()
        self.agent_id = server.state()['agents'][0]['id']

    def meeting(self, **changes):
        data = {'title':'Test sync', 'transcript':'Ana: We agreed to ship Friday.\nBen: I will update the release checklist.',
                'agent_id':self.agent_id,'consent':True}
        data.update(changes)
        return server.create_meeting(data)['id']

    def test_consent_required(self):
        with self.assertRaises(server.AppError):
            self.meeting(consent=False)
        self.assertEqual(server.state()['meetings'],[])

    def test_platform_url_validation(self):
        for url in ('http://meet.google.com/abc', 'https://meet.google.com.attacker.example/abc', 'https://zoom.us@attacker.example/j/1','https://localhost/a'):
            with self.subTest(url=url), self.assertRaises(server.AppError):
                server.platform_for(url)
        self.assertEqual(server.platform_for('https://meet.google.com/abc-defg-hij'),'Google Meet')
        self.assertEqual(server.platform_for('https://teams.microsoft.com/l/meetup-join/123'),'Microsoft Teams')
        self.assertEqual(server.platform_for('https://us02web.zoom.us/j/123'),'Zoom')

    def test_import_and_extracted_notes_persist(self):
        ident = self.meeting()
        notes = server.summarize(ident,False)['notes']
        self.assertIn('We agreed',notes['decisions'][0])
        self.assertIn('will update',notes['actions'][0])
        self.assertIn('not an AI summary',notes['source'])
        with server.connect() as con:
            row = server.meeting_row(con,ident)
        self.assertTrue(row['consent_at'])
        self.assertEqual(json.loads(row['notes']),notes)

    def test_agent_delete_preserves_meetings(self):
        ident = self.meeting()
        with server.connect() as con:
            con.execute('DELETE FROM agents WHERE id=?',(self.agent_id,))
            self.assertIsNone(server.meeting_row(con,ident)['agent_id'])

    def test_missing_live_key_does_not_change_meeting_status(self):
        ident = self.meeting(url='https://meet.google.com/abc-defg-hij')
        with self.assertRaises(server.AppError):
            server.join_meeting(ident)
        self.assertEqual(server.state()['meetings'][0]['status'],'transcript_ready')

    def test_duplicate_join_is_prevented(self):
        ident = self.meeting(url='https://meet.google.com/abc-defg-hij')
        with patch.dict(os.environ,{'RECALL_API_KEY':'test-key'}), patch.object(server,'remote_json',return_value={'id':'11111111-1111-1111-1111-111111111111'}) as provider:
            server.join_meeting(ident)
            with self.assertRaises(server.AppError):
                server.join_meeting(ident)
            self.assertEqual(provider.call_count,1)

    def test_uncertain_join_cannot_be_blindly_retried(self):
        ident = self.meeting(url='https://meet.google.com/abc-defg-hij')
        with patch.dict(os.environ,{'RECALL_API_KEY':'test-key'}), patch.object(server,'remote_json',side_effect=server.AppError('timeout',502)) as provider:
            for _ in range(2):
                with self.assertRaises(server.AppError):
                    server.join_meeting(ident)
            self.assertEqual(provider.call_count,1)
        self.assertEqual(server.state()['meetings'][0]['status'],'join_uncertain')

    def test_ai_notes_with_mock_provider(self):
        ident = self.meeting()
        notes={'summary':'A release was discussed.','decisions':['Ship Friday.'],'actions':['Ben will update the checklist.']}
        response={'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(notes)}]}]}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key'}), patch.object(server,'remote_json',return_value=response) as provider:
            saved=server.summarize(ident,True)['notes']
            self.assertEqual(saved['summary'],notes['summary'])
            self.assertFalse(provider.call_args.args[1]['store'])
            self.assertEqual(provider.call_args.args[1]['text']['format']['type'],'json_schema')

    def test_sync_imports_provider_transcript(self):
        ident=self.meeting(url='https://meet.google.com/abc-defg-hij')
        with server.connect() as con:
            con.execute('UPDATE meetings SET bot_id=? WHERE id=?',('11111111-1111-1111-1111-111111111111',ident))
        bot={'status_changes':[{'code':'done'}],'recordings':[{'media_shortcuts':{'transcript':{'data':{'download_url':'https://bucket.s3.amazonaws.com/transcript.json'}}}}]}
        transcript=[{'participant':{'name':'Ana'},'words':[{'text':'Hello'},{'text':'team'}]}]
        with patch.dict(os.environ,{'RECALL_API_KEY':'test-key'}),patch.object(server,'remote_json',side_effect=[bot,transcript]):
            server.sync_meeting(ident)
        self.assertEqual(server.state()['meetings'][0]['transcript'],'Ana: Hello team')

    def test_http_rejects_mutation_without_session_token(self):
        httpd=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=httpd.serve_forever,daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        url=f'http://127.0.0.1:{httpd.server_port}/api/profile'
        request=urllib.request.Request(url,data=b'{"name":"Bad","company":"Bad"}',headers={'Content-Type':'application/json'})
        with self.assertRaises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(request)
        self.assertEqual(failure.exception.code,403)
        self.assertEqual(server.state()['profile']['name'],'Saman Shakya')


if __name__=='__main__':
    unittest.main()
