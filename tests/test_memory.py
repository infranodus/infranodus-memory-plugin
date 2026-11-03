"""Tests for hooks/memory.py (stdlib unittest, no network: a local fake
/recall server stands in for InfraNodus).

    python3 -m unittest discover -s tests
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "hooks", "memory.py")
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import memory  # noqa: E402

BLOCK = "From InfraNodus memory (learn-demo):\n- [learning: trap] x"


class FakeRecall(BaseHTTPRequestHandler):
    calls = []
    status = 200
    delay = 0.0
    saved = None
    ingest_status = 202

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        FakeRecall.calls.append(
            {"path": self.path, "body": body, "auth": self.headers.get("Authorization")}
        )
        time.sleep(FakeRecall.delay)
        status = FakeRecall.status
        if self.path.endswith("/ingest"):
            status = FakeRecall.ingest_status
            payload = {"accepted": status == 202}
        elif self.path.endswith("/memory/forget"):
            payload = {"forgotten": 3, "sessionId": "s0"}
        elif status == 200:
            payload = {"block": BLOCK, "graphUrl": "https://infranodus.com/u/learn-demo/edit", "items": [1]}
            if FakeRecall.saved:
                payload["saved"] = FakeRecall.saved
        else:
            payload = {"error": "nope"}
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class MemoryHookTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeRecall)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d/api/v1" % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeRecall.calls = []
        FakeRecall.status = 200
        FakeRecall.delay = 0.0
        FakeRecall.saved = None
        FakeRecall.ingest_status = 202
        self.tmp = tempfile.mkdtemp(dir=os.path.expanduser("~"), prefix=".imtest-")
        self.state = os.path.join(self.tmp, "state")
        self.repo = os.path.join(self.tmp, "work", "demo")
        os.makedirs(os.path.join(self.repo, ".git"))
        with open(os.path.join(self.repo, ".git", "config"), "w") as f:
            f.write('[core]\n[remote "origin"]\n\turl = git@github.com:acme/demo-repo.git\n')
        self.env = dict(
            os.environ,
            INFRANODUS_HOME=self.state,
            CLAUDE_PLUGIN_OPTION_API_KEY="k123",
            CLAUDE_PLUGIN_OPTION_API_BASE=self.base,
        )
        self.env.pop("INFRANODUS_MEMORY_DISABLE", None)

    def tearDown(self):
        subprocess.run(["rm", "-rf", self.tmp])

    def hook(self, session="s1", prompt="how do I run the tests", cwd=None, env=None):
        event = {"session_id": session, "prompt": prompt, "cwd": cwd or self.repo}
        started = time.time()
        result = subprocess.run(
            [sys.executable, SCRIPT, "hook-prompt"],
            input=json.dumps(event),
            capture_output=True,
            text=True,
            env=env or self.env,
            timeout=10,
        )
        elapsed = time.time() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout) if result.stdout.strip() else None
        return out, elapsed

    def command(self, name, cwd=None):
        result = subprocess.run(
            [sys.executable, SCRIPT, name],
            capture_output=True, text=True, env=self.env, cwd=cwd or self.repo, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    # --- project identity -------------------------------------------------

    def test_project_is_the_git_remote_name_else_the_folder(self):
        self.assertEqual(memory.project_for(self.repo), "demo-repo")
        sub = os.path.join(self.repo, "src", "deep")
        os.makedirs(sub)
        self.assertEqual(memory.project_for(sub), "demo-repo")
        os.remove(os.path.join(self.repo, ".git", "config"))
        self.assertEqual(memory.project_for(self.repo), "demo")

    def test_home_temp_and_plain_folders_are_not_projects(self):
        self.assertIsNone(memory.project_for(os.path.expanduser("~")))
        self.assertIsNone(memory.project_for(tempfile.gettempdir()))
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        self.assertIsNone(memory.project_for(plain))
        with open(os.path.join(plain, "package.json"), "w") as f:
            f.write("{}")
        self.assertEqual(memory.project_for(plain), "plain")

    # --- hook ---------------------------------------------------------------

    def test_first_prompt_recalls_and_tells_once(self):
        out, _ = self.hook()
        self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"], BLOCK)
        self.assertIn("InfraNodus memory is on for demo-repo", out["systemMessage"])
        self.assertIn("/infranodus-memory:off", out["systemMessage"])
        call = FakeRecall.calls[0]
        self.assertEqual(call["path"], "/api/v1/recall")
        self.assertEqual(call["body"]["project"], "demo-repo")
        self.assertEqual(call["body"]["prompt"], "how do I run the tests")
        self.assertEqual(call["body"]["client"], "claude-code")
        self.assertEqual(call["auth"], "Bearer k123")

        # Same session: nothing more. New session: recall again, no first-run line.
        again, _ = self.hook(session="s1")
        self.assertIsNone(again)
        next_session, _ = self.hook(session="s2")
        self.assertIn("additionalContext", next_session["hookSpecificOutput"])
        self.assertNotIn("systemMessage", next_session)
        self.assertEqual(len(FakeRecall.calls), 2)

    def test_off_sends_nothing_and_on_restores(self):
        self.assertIn("now off for demo-repo", self.command("off"))
        out, _ = self.hook()
        self.assertIsNone(out)
        self.assertEqual(FakeRecall.calls, [])
        self.assertIn("off for this project", self.command("status"))
        self.assertIn("on for demo-repo again", self.command("on"))
        out, _ = self.hook(session="s2")
        self.assertIsNotNone(out)

    def test_not_a_project_missing_key_or_disable_env_send_nothing(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain)
        self.assertIsNone(self.hook(cwd=plain)[0])
        no_key = dict(self.env, CLAUDE_PLUGIN_OPTION_API_KEY="")
        self.assertIsNone(self.hook(session="s2", env=no_key)[0])
        disabled = dict(self.env, INFRANODUS_MEMORY_DISABLE="1")
        self.assertIsNone(self.hook(session="s3", env=disabled)[0])
        self.assertEqual(FakeRecall.calls, [])

    def test_rejected_key_is_said_once_and_errors_are_silent(self):
        FakeRecall.status = 401
        out, _ = self.hook(session="a")
        self.assertIn("API key was rejected", out["systemMessage"])
        self.assertIsNone(self.hook(session="b")[0], "said only once")
        FakeRecall.status = 500
        self.assertIsNone(self.hook(session="c")[0])

    def test_timeout_is_silent_and_bounded(self):
        FakeRecall.delay = 3.5
        out, elapsed = self.hook()
        self.assertIsNone(out)
        self.assertLess(elapsed, memory.RECALL_TIMEOUT_S + 1.0)

    def test_skipped_prompts_are_fast(self):
        self.hook()
        _, elapsed = self.hook(session="s1")  # already recalled: no network
        self.assertLess(elapsed, 0.3)

    def test_broken_settings_file_means_defaults(self):
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, "memory.json"), "w") as f:
            f.write("{not json")
        out, _ = self.hook()
        self.assertIsNotNone(out)


class MemoryUploadTest(MemoryHookTest):
    """The session upload: worker, offsets, queue, saved line, exclusions."""

    def transcript(self, turns=4, name="t.jsonl", append=False):
        path = os.path.join(self.tmp, name)
        with open(path, "a" if append else "w") as f:
            for i in range(turns):
                f.write(json.dumps({"type": "user", "message": {"content": "Question %d: how does the parser in lib/parse.js handle quoted fields? Explain the edge cases please." % i}}) + "\n")
                f.write(json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "id": "b%d" % i, "name": "Bash", "input": {"command": "npm test -- --grep parser%d" % i}},
                ]}}) + "\n")
                f.write(json.dumps({"type": "user", "message": {"content": [
                    {"type": "tool_result", "tool_use_id": "b%d" % i, "content": "ok", "is_error": False},
                ]}}) + "\n")
                f.write(json.dumps({"type": "assistant", "message": {"content": [
                    {"type": "text", "text": "The parser in [[lib/parse.js]] splits on commas outside quotes; doubled quotes escape a quote. api_key=abcdef0123456789 is never logged. " * 2},
                ]}}) + "\n")
        return path

    def worker(self, transcript, event="SessionEnd", session="s1", env=None):
        result = subprocess.run(
            [sys.executable, SCRIPT, "ingest-worker", transcript, session, self.repo, event],
            capture_output=True, text=True, env=env or self.env, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def uploads(self):
        return [c for c in FakeRecall.calls if c["path"].endswith("/ingest")]

    def test_flush_hook_returns_at_once_and_the_worker_uploads(self):
        path = self.transcript()
        event = {"session_id": "s1", "cwd": self.repo, "transcript_path": path, "hook_event_name": "SessionEnd"}
        started = time.time()
        result = subprocess.run([sys.executable, SCRIPT, "hook-flush"], input=json.dumps(event),
                                capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertLess(time.time() - started, 1.0)
        for _ in range(100):
            if self.uploads():
                break
            time.sleep(0.1)
        body = self.uploads()[0]["body"]
        self.assertEqual(body["project"], "demo-repo")
        self.assertEqual(body["sessionId"], "s1")
        self.assertIn("COMMANDS RUN", body["excerpt"])
        self.assertIn("npm test -- --grep parser0", body["excerpt"])
        self.assertNotIn("abcdef0123456789", body["excerpt"], "secrets are redacted")

    def test_each_upload_covers_only_new_lines(self):
        path = self.transcript()
        self.worker(path, "PreCompact")
        self.assertEqual(len(self.uploads()), 1)
        self.worker(path, "SessionEnd")
        self.assertEqual(len(self.uploads()), 1, "nothing new, nothing sent")
        self.transcript(turns=4, append=True)
        self.worker(path, "SessionEnd")
        self.assertEqual(len(self.uploads()), 2)

    def test_tiny_sessions_send_nothing(self):
        path = self.transcript(turns=0)
        with open(path, "a") as f:
            f.write(json.dumps({"type": "user", "message": {"content": "hi"}}) + "\n")
        self.worker(path, "PreCompact")
        self.worker(path, "SessionEnd")
        self.assertEqual(self.uploads(), [])

    def test_failed_upload_is_queued_and_retried(self):
        path = self.transcript()
        FakeRecall.ingest_status = 503
        self.worker(path)
        self.assertEqual(len(os.listdir(os.path.join(self.state, "queue"))), 1)
        FakeRecall.ingest_status = 202
        other = self.transcript(name="other.jsonl")
        self.worker(other, session="s2")
        self.assertEqual(os.listdir(os.path.join(self.state, "queue")), [])
        sessions = [c["body"]["sessionId"] for c in self.uploads()]
        self.assertEqual(sessions, ["s1", "s1", "s2"], "queued one retried first")

    def test_off_or_excluded_projects_upload_nothing(self):
        path = self.transcript()
        self.command("off")
        self.worker(path)
        self.command("on")
        excluded = dict(self.env, CLAUDE_PLUGIN_OPTION_EXCLUDE_PATHS="~/nothing, %s" % os.path.dirname(self.repo) + "/*")
        self.worker(path, env=excluded)
        self.assertIsNone(self.hook(env=excluded)[0])
        self.assertEqual(self.uploads(), [])

    def test_saved_line_is_shown_once_per_session(self):
        FakeRecall.saved = {"sessionId": "s0", "count": 4}
        out, _ = self.hook(session="a")
        self.assertIn("saved 4 learnings from your last session", out["systemMessage"])
        self.assertIn("/infranodus-memory:forget-last", out["systemMessage"])
        out, _ = self.hook(session="b")
        self.assertNotIn("systemMessage", out)

    def test_upload_sends_the_save_setting(self):
        path = self.transcript()
        self.worker(path)
        self.assertEqual(self.uploads()[0]["body"]["save"], "both", "default")
        only = dict(self.env, CLAUDE_PLUGIN_OPTION_SAVE="Learnings")
        self.transcript(turns=4, append=True)
        self.worker(path, env=only)
        self.assertEqual(self.uploads()[1]["body"]["save"], "learnings")
        odd = dict(self.env, CLAUDE_PLUGIN_OPTION_SAVE="everything")
        self.transcript(turns=4, append=True)
        self.worker(path, env=odd)
        self.assertEqual(self.uploads()[2]["body"]["save"], "both", "unknown value -> default")

    def test_404_is_queued_not_dropped(self):
        path = self.transcript()
        FakeRecall.ingest_status = 404
        self.worker(path)
        self.assertEqual(len(os.listdir(os.path.join(self.state, "queue"))), 1)

    def test_commands_take_the_key_from_arguments_and_never_print_it(self):
        env = dict(self.env)
        env.pop("CLAUDE_PLUGIN_OPTION_API_KEY")
        env.pop("CLAUDE_PLUGIN_OPTION_API_BASE")
        run = lambda *args: subprocess.run([sys.executable, SCRIPT, *args], capture_output=True,
                                           text=True, env=env, cwd=self.repo, timeout=10).stdout
        self.assertIn("API key: missing", run("status"))
        self.assertIn("API key: missing", run("status", "--key", "${user_config.api_key}"))
        out = run("status", "--key", "k-secret-123", "--base", self.base)
        self.assertIn("API key: set", out)
        self.assertNotIn("k-secret-123", out)
        self.assertIn("Removed the 3 learnings", run("forget-last", "--key", "k-secret-123", "--base", self.base))
        self.assertEqual(FakeRecall.calls[-1]["auth"], "Bearer k-secret-123")

    def test_forget_last_command(self):
        out = self.command("forget-last")
        self.assertIn("Removed the 3 learnings", out)
        self.assertTrue(FakeRecall.calls[-1]["path"].endswith("/memory/forget"))
        self.assertEqual(FakeRecall.calls[-1]["body"], {"project": "demo-repo"})


if __name__ == "__main__":
    unittest.main()
