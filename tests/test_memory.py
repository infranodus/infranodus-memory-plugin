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
        elif self.path.endswith("/listGraphs"):
            payload = [
                {"contextName": "learn-demo-repo", "contextType": "MEMORY"},
                {"contextName": "learn-other", "contextType": "MEMORY"},
                {"contextName": "memory-acme", "contextType": "MEMORY"},
                {"contextName": "memory-handmade", "contextType": "STANDARD"},
                {"contextName": "personal-alice", "contextType": "MEMORY"},
                {"contextName": "notes", "contextType": "STANDARD"},
            ]
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
            INFRANODUS_TRANSCRIPTS=os.path.join(self.tmp, "projects"),
            CLAUDE_PLUGIN_OPTION_API_KEY="k123",
            INFRANODUS_API_BASE=self.base,
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
        disabled = dict(self.env, INFRANODUS_MEMORY_DISABLE="1")
        self.assertIsNone(self.hook(session="s3", env=disabled)[0])
        self.assertEqual(FakeRecall.calls, [])

    def test_no_key_sends_nothing_and_says_once_per_project_how_to_add_one(self):
        no_key = dict(self.env)
        no_key.pop("CLAUDE_PLUGIN_OPTION_API_KEY")
        out, _ = self.hook(session="n1", env=no_key)
        self.assertEqual(
            out, {"systemMessage": "InfraNodus memory: add an API key in /plugin to turn on "
                                   "automatic memory for demo-repo."})
        self.assertIsNone(self.hook(session="n1", env=no_key)[0], "later prompts: silent")
        self.assertIsNone(self.hook(session="n2", env=no_key)[0], "next session: said only once")
        for unset in ("", "${user_config.api_key}", "[sensitive option 'api_key' not available in skill content]"):
            self.assertIsNone(self.hook(session="n3" + unset[:2], env=dict(no_key, CLAUDE_PLUGIN_OPTION_API_KEY=unset))[0])
        self.assertEqual(FakeRecall.calls, [])
        out, _ = self.hook(session="n4")
        self.assertIn("InfraNodus memory is on for demo-repo", out["systemMessage"], "with a key: the usual notice")

    def test_the_key_is_read_from_the_plugin_setting_only(self):
        other = dict(self.env, INFRANODUS_API_KEY="envkey")
        other.pop("CLAUDE_PLUGIN_OPTION_API_KEY")
        os.makedirs(self.state, exist_ok=True)
        with open(os.path.join(self.state, "memory.json"), "w") as f:
            json.dump({"apiKey": "storedkey", "toldNoKey": ["demo-repo"]}, f)
        self.assertIsNone(self.hook(session="o1", env=other)[0])
        self.assertEqual(FakeRecall.calls, [], "no other variable and no file gives the script a key")

    def test_the_key_is_sent_only_to_infranodus_or_this_machine(self):
        self.assertTrue(memory.key_allowed_for("https://infranodus.com/api/v1"))
        self.assertTrue(memory.key_allowed_for("https://eu.infranodus.com/api/v1"))
        self.assertTrue(memory.key_allowed_for("http://localhost:3000/api/v1"))
        self.assertTrue(memory.key_allowed_for(self.base))
        for url in ("https://infranodus.com.evil.example/api/v1", "https://example.com/api/v1",
                    "https://notinfranodus.com/api/v1", "nonsense"):
            self.assertFalse(memory.key_allowed_for(url), url)
        elsewhere = dict(self.env, INFRANODUS_API_BASE="http://192.0.2.1:9/api/v1")
        out, elapsed = self.hook(session="h1", env=elsewhere)
        self.assertIsNone(out)
        self.assertLess(elapsed, 1.5, "no request is even attempted")
        result = subprocess.run([sys.executable, SCRIPT, "status"], capture_output=True, text=True,
                                env=elsewhere, cwd=self.repo, timeout=10).stdout
        self.assertIn("not infranodus.com or this machine", result)
        self.assertNotIn("k123", result)

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

    def test_save_command_uploads_the_current_session_once(self):
        import re
        folder = os.path.join(self.tmp, "projects", re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(self.repo)))
        os.makedirs(folder)
        path = self.transcript()
        os.replace(path, os.path.join(folder, "sess-9.jsonl"))
        env = dict(self.env, INFRANODUS_TRANSCRIPTS=os.path.join(self.tmp, "projects"))
        run = lambda: subprocess.run(
            [sys.executable, SCRIPT, "save"],
            capture_output=True, text=True, env=env, cwd=self.repo, timeout=60).stdout
        out = run()
        self.assertIn("Sent this session to InfraNodus (saving: both)", out)
        self.assertEqual(self.uploads()[0]["body"]["sessionId"], "sess-9")
        self.assertIn("Nothing new to save", run())
        self.assertEqual(len(self.uploads()), 1)

    def test_graphs_lists_this_projects_memory_graphs(self):
        out = self.command("graphs")
        self.assertIn("learn-demo-repo: learnings for this project (project name: demo-repo)", out)
        self.assertIn("memory-acme: topic memory (topic: acme)", out)
        self.assertIn("personal-alice: personal memory", out)
        self.assertNotIn("learn-other", out, "another project's learnings")
        self.assertNotIn("memory-handmade", out, "not a memory graph")
        self.assertNotIn("notes", out)
        self.assertIn("Claude's own memory for this folder: none.", out)

    def test_graphs_lists_claudes_own_memory_notes(self):
        import re
        folder = os.path.join(self.tmp, "projects",
                              re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(self.repo)), "memory")
        os.makedirs(folder)
        for name in ("MEMORY.md", "feedback_a.md", "project_b.md"):
            open(os.path.join(folder, name), "w").write("x")
        self.assertIn("2 notes in %s" % folder, self.command("graphs"))

    def test_404_is_queued_not_dropped(self):
        path = self.transcript()
        FakeRecall.ingest_status = 404
        self.worker(path)
        self.assertEqual(len(os.listdir(os.path.join(self.state, "queue"))), 1)

    def expansion(self, name, args="", env=None, **extra):
        """The UserPromptExpansion hook, as Claude Code calls it for a typed
        /infranodus-memory:<name> <args>."""
        event = dict({
            "hook_event_name": "UserPromptExpansion", "expansion_type": "slash_command",
            "command_name": "infranodus-memory:" + name, "command_args": args,
            "command_source": "plugin", "prompt": ("/infranodus-memory:%s %s" % (name, args)).strip(),
            "session_id": "sx", "cwd": self.repo,
        }, **extra)
        result = subprocess.run([sys.executable, SCRIPT, "hook-command"], input=json.dumps(event),
                                capture_output=True, text=True, env=env or self.env, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        if not result.stdout.strip():
            return None
        out = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "UserPromptExpansion")
        self.assertTrue(out["additionalContext"].startswith("[infranodus-memory] "))
        return out["additionalContext"]

    def test_typed_commands_work_through_the_hook_with_a_key(self):
        out = self.expansion("status")
        self.assertIn("Project: demo-repo (learnings graph: learn-demo-repo)", out)
        self.assertIn("API key: set", out)
        self.assertIn("Automatic memory: active", out)
        self.assertNotIn("k123", out, "the key is never printed")
        out = self.expansion("recall", "how do I run the tests")
        self.assertIn(BLOCK, out)
        self.assertIn("- learn-demo-repo: learnings for this project", out)
        recall = [c for c in FakeRecall.calls if c["path"].endswith("/recall")][-1]
        self.assertEqual(recall["body"]["prompt"], "how do I run the tests")
        self.assertEqual(recall["auth"], "Bearer k123")
        out = self.expansion("forget-last")
        self.assertIn("Removed the 3 learnings", out)
        path = self.transcript()
        out = self.expansion("save", transcript_path=path, session_id="typed-1")
        self.assertIn("Sent this session to InfraNodus", out)
        self.assertEqual(self.uploads()[-1]["body"]["sessionId"], "typed-1")
        self.assertIn("off for demo-repo", self.expansion("off"))
        self.assertIn("inactive: memory is off", self.expansion("status"))
        self.assertIn("on for demo-repo again", self.expansion("on"))

    def test_typed_commands_without_a_key_send_nothing_and_point_to_the_tools(self):
        env = dict(self.env)
        env.pop("CLAUDE_PLUGIN_OPTION_API_KEY")
        out = self.expansion("status", env=env)
        self.assertIn("API key: not set", out)
        self.assertIn("Automatic memory: inactive: no API key. Add one in /plugin", out)
        out = self.expansion("recall", "webpack", env=env)
        self.assertIn("learn-demo-repo", out)
        self.assertIn("InfraNodus tools", out)
        out = self.expansion("save", transcript_path=self.transcript(), env=env)
        self.assertIn("Nothing was uploaded", out)
        self.assertIn("add_project_learnings", out)
        self.assertIn("needs the key", self.expansion("forget-last", env=env))
        self.assertIn("learn-demo-repo", self.expansion("remember", "these rules", env=env))
        self.assertIn("list_graphs", self.expansion("optimize", env=env))
        self.assertIn("list_graphs", self.expansion("dream", env=env))
        self.assertEqual(FakeRecall.calls, [])

    def test_dream_is_told_the_graph_and_where_the_session_transcripts_are(self):
        out = self.expansion("dream")
        self.assertIn("learnings graph: learn-demo-repo", out)
        self.assertIn("Session transcripts for this folder: none on this machine", out)
        folder = os.path.join(
            self.env["INFRANODUS_TRANSCRIPTS"],
            "".join(c if c.isalnum() and c.isascii() else "-" for c in os.path.realpath(self.repo)),
        )
        os.makedirs(folder)
        open(os.path.join(folder, "abc-123.jsonl"), "w").close()
        out = self.expansion("dream")
        self.assertIn("Session transcripts for this folder: 1 in %s (<session id>.jsonl)" % folder, out)
        self.assertEqual(self.uploads(), [], "a dream uploads nothing by itself")

    def test_the_hook_ignores_other_commands_and_never_fails(self):
        self.assertIsNone(self.expansion("status", command_name="other-plugin:status"))
        self.assertIsNone(self.expansion("status", command_name="infranodus-memory:unknown"))
        self.assertIn("isn't a project", self.expansion("status", cwd=os.path.join(self.tmp)))
        result = subprocess.run([sys.executable, SCRIPT, "hook-command"], input="not json",
                                capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        out, _ = self.hook(session="cmd", prompt="/infranodus-memory:status")
        self.assertIsNone(out, "the prompt hook leaves a typed command to the expansion hook")
        self.assertEqual(FakeRecall.calls, [])
        self.assertIsNotNone(self.hook(session="cmd")[0], "and the session's first real prompt still recalls")

    def test_saving_commands_write_in_one_call(self):
        # A preview call makes the server ask the client for an approval
        # dialog. Through a claude.ai connector that request never arrived and
        # the call timed out after a minute. The user asking to save is the
        # approval, and the confirmed call runs the same checks as the preview.
        for name in ("save", "remember", "optimize", "dream"):
            with open(os.path.join(ROOT, "skills", name, "SKILL.md"), encoding="utf-8") as f:
                text = f.read()
            self.assertIn("confirm: true", text, name)
            self.assertNotIn("dry run", text.lower(), name)

    def test_dream_works_from_the_state_of_the_graph_and_its_insight_clusters(self):
        with open(os.path.join(ROOT, "skills", "dream", "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        # The state is read before anything is chosen, from the insight clusters.
        self.assertLess(text.index("optimize_knowledge_base"), text.index("get_project_learnings` for"))
        self.assertIn('`optimize: "optimize"`', text)
        # Which clusters to work on is InfraNodus's choice for the state of the
        # graph; the skill has no rules of its own per state.
        self.assertIn("Do not branch on it yourself", text)
        # Further sets come from the next gap depth, not from asking again.
        self.assertIn("`gapDepth: 1`", text)
        # A gap becomes a question; one the repo can't answer is saved as such.
        self.assertIn("type `question`", text)
        self.assertIn("Never answer a question on a guess", text)

    def test_transcend_ideas_are_made_and_recalled_only_on_request(self):
        def skill(name):
            with open(os.path.join(ROOT, "skills", name, "SKILL.md"), encoding="utf-8") as f:
                return f.read()
        dream, recall = skill("dream"), skill("recall")
        # Looking outward is a part of its own, entered only by request.
        outward = dream[dream.index("## Looking outward"):]
        self.assertIn("Only when asked", outward)
        self.assertIn("develop_conceptual_bridges", outward)
        self.assertNotIn("develop_conceptual_bridges", dream[:dream.index("## Looking outward")])
        self.assertIn("at most two ideas", outward)
        # Saved, then labelled so that recall leaves them out.
        self.assertIn('addCategories: ["transcend", "dream-<date>"]', outward)
        self.assertIn('`transcend: "only"`', outward)
        # A normal dream only offers it.
        self.assertIn("/infranodus-memory:dream transcend", dream[:dream.index("## Looking outward")])
        # Recall gives them only when asked, and keeps them out otherwise.
        self.assertIn('`transcend: "only"`', recall)
        self.assertIn("leave out any statement whose categories include `transcend`", recall)

    def test_recall_transcend_makes_no_api_recall(self):
        before = len([c for c in FakeRecall.calls if c["path"].endswith("/recall")])
        out = self.expansion("recall", "transcend webpack")
        self.assertEqual(len([c for c in FakeRecall.calls if c["path"].endswith("/recall")]), before)
        self.assertIn("Transcend ideas are not part of the recall through the API", out)
        self.assertIn("learn-demo-repo", out)

    def test_plugin_files_hold_no_key_handling_of_their_own(self):
        """What Claude Code loads must not read a key from the machine or
        ask Claude Code to paste one into a command."""
        banned = ("INFRANODUS_API_KEY", "set-key", "user_config.api_key", "--key")
        files = [os.path.join(ROOT, "hooks", n) for n in ("memory.py", "excerpt.py", "hooks.json")]
        files.append(os.path.join(ROOT, ".claude-plugin", "plugin.json"))
        for folder, _dirs, names in os.walk(os.path.join(ROOT, "skills")):
            files += [os.path.join(folder, n) for n in names]
        for path in files:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for word in banned:
                self.assertNotIn(word, text, "%s in %s" % (word, os.path.relpath(path, ROOT)))
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json")) as f:
            manifest = json.load(f)
        self.assertNotIn("mcpServers", manifest)
        self.assertEqual(sorted(manifest["userConfig"]), ["api_key", "exclude_paths", "save"])
        self.assertFalse(manifest["userConfig"]["api_key"].get("required"))
        self.assertTrue(manifest["userConfig"]["api_key"]["sensitive"])
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".mcp.json")),
                         "Claude Code would load a root .mcp.json as the plugin's server")

    def test_forget_last_command(self):
        out = self.command("forget-last")
        self.assertIn("Removed the 3 learnings", out)
        self.assertTrue(FakeRecall.calls[-1]["path"].endswith("/memory/forget"))
        self.assertEqual(FakeRecall.calls[-1]["body"], {"project": "demo-repo"})


if __name__ == "__main__":
    unittest.main()


class OtherClientsTest(MemoryUploadTest):
    """Codex and Grok Build: payload shapes, the Codex rollout format, the
    API key without plugin settings, and the Grok rules file."""

    def codex_rollout(self, name="rollout-2026-11-03T10-00-00-abc.jsonl", folder=None, cwd=None):
        folder = folder or self.tmp
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name)
        def item(payload, kind="response_item"):
            return json.dumps({"type": kind, "payload": payload}) + "\n"
        with open(path, "w") as f:
            f.write(item({"id": "abc", "cwd": cwd or self.repo, "cli_version": "0.163.0"}, "session_meta"))
            f.write(item({"type": "message", "role": "developer", "content": [{"type": "input_text", "text": "You are Codex."}]}))
            f.write(item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "<environment_context>\n  <cwd>/x</cwd>\n</environment_context>"}]}))
            for i in range(3):
                f.write(item({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Question %d: how does the parser in lib/parse.js handle quoted fields? Explain the edge cases please." % i}]}))
                f.write(item({"type": "function_call", "name": "shell", "call_id": "c%d" % i, "arguments": json.dumps({"command": ["bash", "-lc", "npm test -- --grep parser%d" % i]})}))
                f.write(item({"type": "function_call_output", "call_id": "c%d" % i, "output": [{"type": "input_text", "text": "Exit code: 0\n12 passing"}]}))
                f.write(item({"type": "function_call", "name": "shell", "call_id": "f%d" % i, "arguments": json.dumps({"cmd": "node broken%d.js" % i})}))
                f.write(item({"type": "function_call_output", "call_id": "f%d" % i, "output": "Exit code: 1\nTypeError: boom"}))
                f.write(item({"type": "custom_tool_call", "name": "apply_patch", "call_id": "p%d" % i, "input": "*** Begin Patch\n*** Update File: lib/parse%d.js\n@@\n-a\n+b\n*** End Patch" % i}))
                f.write(item({"type": "custom_tool_call_output", "call_id": "p%d" % i, "output": "Done"}))
                f.write(item({"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Working on it."}]}))
                f.write(item({"type": "task_complete", "last_agent_message": "The parser in [[lib/parse.js]] splits on commas outside quotes; token=abcdef0123456789 never logged. " * 2}, "event_msg"))
        return path

    def test_codex_rollout_is_read_like_a_transcript(self):
        import excerpt
        path = self.codex_rollout()
        text, end, turns = excerpt.build_excerpt(path)
        self.assertEqual(turns, 3, "the environment_context message is not a prompt")
        self.assertIn("npm test -- --grep parser0", text)
        self.assertNotIn("node broken0.js", text.split("FILES EDITED")[0], "failed commands aren't how-to")
        self.assertIn("TOOL FAILED: Bash(command=node broken2.js)", text)
        self.assertIn("FILES EDITED: lib/parse0.js, lib/parse1.js, lib/parse2.js", text)
        self.assertIn("AGENT (final answer): The parser", text)
        self.assertNotIn("abcdef0123456789", text)

    def test_codex_payload_uploads_with_its_client_name(self):
        path = self.codex_rollout()
        env = dict(self.env, PLUGIN_ROOT=ROOT, CLAUDE_PLUGIN_ROOT=ROOT)
        event = {"session_id": "cx1", "cwd": self.repo, "transcript_path": path,
                 "hook_event_name": "SessionEnd", "turn_id": "t1", "model": "gpt-5.5"}
        subprocess.run([sys.executable, SCRIPT, "hook-flush"], input=json.dumps(event),
                       capture_output=True, text=True, env=env, timeout=10)
        for _ in range(100):
            if self.uploads():
                break
            time.sleep(0.1)
        body = self.uploads()[0]["body"]
        self.assertEqual(body["client"], "codex")
        self.assertIn("npm test -- --grep parser1", body["excerpt"])
        out, _ = self.hook(session="cx2", env=env)
        self.assertEqual(FakeRecall.calls[-1]["body"]["client"], "codex")
        self.assertIn("additionalContext", json.dumps(out))
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".grok")), "no rules file outside Grok")

    def test_grok_camelcase_payload_recalls_and_writes_the_rules_file(self):
        env = dict(self.env, GROK_HOOK_EVENT="UserPromptSubmit", GROK_SESSION_ID="g1", GROK_WORKSPACE_ROOT=self.repo)
        event = {"hookEventName": "UserPromptSubmit", "sessionId": "g1", "cwd": self.repo, "workspaceRoot": self.repo}
        result = subprocess.run([sys.executable, SCRIPT, "hook-prompt"], input=json.dumps(event),
                                capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"], BLOCK)
        self.assertEqual(FakeRecall.calls[-1]["body"]["client"], "grok")
        rules = os.path.join(self.repo, ".grok", "rules", "infranodus-memory.md")
        with open(rules) as f:
            content = f.read()
        self.assertIn(BLOCK, content)
        self.assertTrue(content.startswith("<!-- Generated by the InfraNodus memory plugin"))
        # the same session again: no second recall, file untouched
        result = subprocess.run([sys.executable, SCRIPT, "hook-prompt"], input=json.dumps(event),
                                capture_output=True, text=True, env=env, timeout=10)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len([c for c in FakeRecall.calls if c["path"].endswith("/recall")]), 1)

    def test_codex_wrapper_supplies_the_key_when_there_are_no_plugin_settings(self):
        wrapper = os.path.join(ROOT, "codex", "key.py")
        env = dict(self.env)
        env.pop("CLAUDE_PLUGIN_OPTION_API_KEY")

        def hook(session, env):
            event = {"session_id": session, "prompt": "how do I run the tests", "cwd": self.repo}
            result = subprocess.run([sys.executable, wrapper, "hook-prompt"], input=json.dumps(event),
                                    capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout) if result.stdout.strip() else None

        out = hook("k1", env)
        self.assertIn("add an API key", out["systemMessage"], "no key anywhere: the notice, nothing sent")
        self.assertEqual(FakeRecall.calls, [])
        hook("k2", dict(env, INFRANODUS_API_KEY="envkey"))
        self.assertEqual(FakeRecall.calls[-1]["auth"], "Bearer envkey")
        result = subprocess.run([sys.executable, wrapper, "set-key", "storedkey"],
                                capture_output=True, text=True, env=env, cwd=self.repo, timeout=10)
        self.assertIn("stored", result.stdout)
        self.assertNotIn("storedkey", result.stdout)
        self.assertEqual(oct(os.stat(os.path.join(self.state, "memory.json")).st_mode & 0o777), "0o600")
        out = hook("k3", env)
        self.assertEqual(out["hookSpecificOutput"]["additionalContext"], BLOCK)
        self.assertEqual(FakeRecall.calls[-1]["auth"], "Bearer storedkey")
        result = subprocess.run([sys.executable, wrapper, "status"], capture_output=True, text=True,
                                env=env, cwd=self.repo, timeout=10)
        self.assertIn("API key: set", result.stdout)
        self.assertNotIn("storedkey", result.stdout)
        subprocess.run([sys.executable, wrapper, "clear-key"], capture_output=True, text=True, env=env, cwd=self.repo, timeout=10)
        self.assertIsNone(hook("k4", env))

    def test_save_finds_the_codex_rollout_for_this_folder(self):
        codex_home = os.path.join(self.tmp, "codex-home")
        self.codex_rollout(folder=os.path.join(codex_home, "sessions", "2026", "11", "02"), cwd="/elsewhere",
                           name="rollout-2026-11-02T09-00-00-zzz.jsonl")
        time.sleep(0.05)
        self.codex_rollout(folder=os.path.join(codex_home, "sessions", "2026", "11", "03"))
        env = dict(self.env, CODEX_HOME=codex_home, PLUGIN_ROOT=ROOT)
        result = subprocess.run([sys.executable, SCRIPT, "save"], capture_output=True, text=True,
                                env=env, cwd=self.repo, timeout=60)
        self.assertIn("Sent this session", result.stdout, result.stdout)
        body = self.uploads()[0]["body"]
        self.assertEqual(body["sessionId"], "abc")
        self.assertEqual(body["client"], "codex")
        self.assertIn("lib/parse2.js", body["excerpt"])

    def test_session_end_hook_fits_codex_limit(self):
        with open(os.path.join(ROOT, "hooks", "hooks.json")) as f:
            hooks = json.load(f)["hooks"]
        self.assertLessEqual(hooks["SessionEnd"][0]["hooks"][0]["timeout"], 3)
        for event in ("UserPromptSubmit", "UserPromptExpansion", "PreCompact", "SessionEnd"):
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/hooks/memory.py", hooks[event][0]["hooks"][0]["command"])
        with open(os.path.join(ROOT, "codex", "hooks.json")) as f:
            codex = json.load(f)["hooks"]
        self.assertLessEqual(codex["SessionEnd"][0]["hooks"][0]["timeout"], 3)
        for event in ("UserPromptSubmit", "PreCompact", "SessionEnd"):
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/codex/key.py", codex[event][0]["hooks"][0]["command"])
        with open(os.path.join(ROOT, ".codex-plugin", "plugin.json")) as f:
            manifest = json.load(f)
        self.assertEqual((manifest["hooks"], manifest["mcpServers"]), ("./codex/hooks.json", "./mcp.json"))
