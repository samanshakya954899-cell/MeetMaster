import tempfile
import unittest
from pathlib import Path
import agent


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = agent.Workspace(self.temp.name, approve=lambda _: False)

    def test_escape_and_protected_paths_rejected(self):
        for path in ("../outside.txt", ".env", ".git/config", ".aws/credentials"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.workspace.path(path)

    def test_denied_write_does_not_touch_existing_file(self):
        path = Path(self.temp.name) / "keep.txt"
        path.write_text("original", encoding="utf-8")
        result = self.workspace.call("write_file", {"path": "keep.txt", "content": "replacement"})
        self.assertEqual(result["status"], "denied")
        self.assertEqual(path.read_text(), "original")

    def test_approved_write_is_verified(self):
        self.workspace.approve = lambda _: True
        result = self.workspace.call("write_file", {"path": "sub/new.txt", "content": "hello"})
        self.assertTrue(result["verified"])

    def test_denied_command_does_not_run(self):
        result = self.workspace.call("run_command", {"command": "invalid-command"})
        self.assertEqual(result["status"], "denied")

    def test_tool_loop_returns_output_and_keeps_context(self):
        requests = []
        def request(payload):
            requests.append(list(payload["input"]))
            if len(requests) == 1:
                return {"status": "completed", "output": [{"type": "function_call", "name": "list_files",
                        "arguments": '{"path":"."}', "call_id": "call_1"}]}
            return {"status": "completed", "output": [{"type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": "The workspace is empty."}]}]}
        bot = agent.Agent(self.workspace, "test", web=False, request=request)
        self.assertEqual(bot.turn("Inspect files"), "The workspace is empty.")
        self.assertEqual(requests[1][-1]["type"], "function_call_output")
        self.assertTrue(bot.history)

    def test_incomplete_response_does_not_execute_tool(self):
        def request(_):
            return {"status": "incomplete", "output": [{"type": "function_call", "name": "write_file",
                    "arguments": '{"path":"bad.txt","content":"bad"}', "call_id": "1"}]}
        bot = agent.Agent(self.workspace, "test", request=request)
        with self.assertRaises(RuntimeError):
            bot.turn("Write")
        self.assertFalse((Path(self.temp.name) / "bad.txt").exists())

    def test_repeated_calls_hit_step_limit(self):
        def request(_):
            return {"output": [{"type": "function_call", "name": "list_files",
                    "arguments": '{"path":"."}', "call_id": "call"}]}
        bot = agent.Agent(self.workspace, "test", request=request, max_steps=2)
        with self.assertRaisesRegex(RuntimeError, "step limit"):
            bot.turn("Inspect")


if __name__ == "__main__":
    unittest.main()
