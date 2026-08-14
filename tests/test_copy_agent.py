from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from copy_agent.knowledge_loader import build_system_prompt, knowledge_files
from copy_agent.llm import ChatClient, OpenAIError
from copy_agent.store import ChatStore
from copy_agent.youtube import TranscriptError, extract_video_id


def sse_response(deltas: list[str]) -> httpx.Response:
    lines = []
    for delta in deltas:
        event = {"choices": [{"delta": {"content": delta}}]}
        lines.append(f"data: {json.dumps(event)}")
    lines.append("data: [DONE]")
    body = "\n".join(lines).encode()
    return httpx.Response(
        200, content=body, headers={"content-type": "text/event-stream"}
    )


class ChatClientTests(unittest.TestCase):
    def test_stream_parses_deltas(self) -> None:
        transport = httpx.MockTransport(lambda request: sse_response(["Hel", "lo"]))
        client = ChatClient(api_key="k", transport=transport)
        self.assertEqual(["Hel", "lo"], list(client.stream([{"role": "user", "content": "hi"}])))

    def test_complete_returns_content(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            assert payload["model"]
            return httpx.Response(
                200, json={"choices": [{"message": {"content": "Sharp hook."}}]}
            )

        client = ChatClient(api_key="k", transport=httpx.MockTransport(handler))
        self.assertEqual(
            "Sharp hook.", client.complete([{"role": "user", "content": "hi"}])
        )

    def test_api_error_is_surfaced(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(
                401, json={"error": {"message": "Incorrect API key"}}
            )
        )
        client = ChatClient(api_key="bad", transport=transport)
        with self.assertRaisesRegex(OpenAIError, "Incorrect API key"):
            client.complete([{"role": "user", "content": "hi"}])

    def test_missing_key_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(OpenAIError, "not configured"):
                ChatClient()


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ChatStore(Path(self.tmp.name) / "chat.db")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_conversation_roundtrip(self) -> None:
        cid = self.store.create_conversation()
        self.store.add_message(cid, "user", "write a hook")
        self.store.set_title_if_empty(cid, "write a hook")
        self.store.add_message(cid, "assistant", "Here are 5 hooks...")
        messages = self.store.messages(cid)
        self.assertEqual(["user", "assistant"], [m["role"] for m in messages])
        listed = self.store.list_conversations()
        self.assertEqual("write a hook", listed[0]["title"])
        self.store.delete_conversation(cid)
        self.assertFalse(self.store.conversation_exists(cid))

    def test_learnings_feed_digest_newest_first(self) -> None:
        self.store.add_learning("youtube", "https://youtu.be/x", "Old lesson", "A" * 50)
        self.store.add_learning("note", "", "New lesson", "B" * 50)
        digest = self.store.learnings_digest()
        self.assertLess(digest.index("New lesson"), digest.index("Old lesson"))

    def test_digest_respects_cap(self) -> None:
        for i in range(10):
            self.store.add_learning("note", "", f"L{i}", "X" * 5000)
        self.assertLessEqual(len(self.store.learnings_digest(max_chars=12000)), 12500)


class KnowledgeTests(unittest.TestCase):
    def test_core_files_are_loaded(self) -> None:
        names = [path.name for path in knowledge_files()]
        self.assertIn("00-brand.md", names)
        self.assertIn("mindfluence.md", names)

    def test_prompt_contains_brand_and_skill(self) -> None:
        prompt = build_system_prompt()
        self.assertIn("8-Thon Intelligence", prompt)
        self.assertIn("mindfluence", prompt.lower())
        self.assertIn("NEVER", prompt)


class YouTubeTests(unittest.TestCase):
    def test_extracts_ids_from_common_url_shapes(self) -> None:
        for url in (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ?t=10",
            "https://www.youtube.com/shorts/dQw4w9WgXcQ",
            "dQw4w9WgXcQ",
        ):
            self.assertEqual("dQw4w9WgXcQ", extract_video_id(url))

    def test_rejects_non_video_input(self) -> None:
        with self.assertRaises(TranscriptError):
            extract_video_id("https://example.com/not-youtube")


class WebTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        import copy_agent.web as web

        self.web = web
        self.store = ChatStore(Path(self.tmp.name) / "chat.db")
        self._store_patch = patch.object(web, "STORE", self.store)
        self._store_patch.start()
        self.client = TestClient(web.app)

    def tearDown(self) -> None:
        self._store_patch.stop()
        self.tmp.cleanup()

    def test_status_reports_configuration(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "k"}):
            data = self.client.get("/api/status").json()
        self.assertEqual("ok", data["status"])
        self.assertEqual("configured", data["openai"])

    def test_dashboard_renders(self) -> None:
        response = self.client.get("/")
        self.assertEqual(200, response.status_code)
        self.assertIn("Copy Studio", response.text)
        self.assertIn("Research mode", response.text)

    def test_chat_streams_and_persists(self) -> None:
        transport = httpx.MockTransport(lambda request: sse_response(["Post ", "draft"]))

        def fake_client(*args, **kwargs):
            return ChatClient(api_key="k", transport=transport)

        with patch.dict("os.environ", {"OPENAI_API_KEY": "k"}), patch.object(
            self.web, "ChatClient", fake_client
        ):
            response = self.client.post(
                "/api/chat", json={"message": "Write a LinkedIn hook"}
            )
        self.assertEqual(200, response.status_code)
        self.assertIn('"text": "draft"', response.text)
        conversations = self.store.list_conversations()
        self.assertEqual(1, len(conversations))
        messages = self.store.messages(conversations[0]["id"])
        self.assertEqual(["user", "assistant"], [m["role"] for m in messages])
        self.assertEqual("Post draft", messages[1]["content"])

    def test_research_mode_uses_search_model(self) -> None:
        seen_models: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_models.append(json.loads(request.content)["model"])
            return sse_response(["ok"])

        def fake_client(*args, **kwargs):
            return ChatClient(api_key="k", transport=httpx.MockTransport(handler))

        with patch.dict("os.environ", {"OPENAI_API_KEY": "k"}), patch.object(
            self.web, "ChatClient", fake_client
        ):
            self.client.post(
                "/api/chat", json={"message": "what's trending?", "research": True}
            )
        self.assertEqual(["gpt-4o-search-preview"], seen_models)

    def test_learning_endpoints(self) -> None:
        created = self.client.post(
            "/api/learnings", json={"title": "Hook rule", "content": "Numbers beat adjectives."}
        )
        self.assertEqual(201, created.status_code)
        listed = self.client.get("/api/learnings").json()
        self.assertEqual("Hook rule", listed[0]["title"])
        deleted = self.client.delete(f"/api/learnings/{listed[0]['id']}")
        self.assertEqual(200, deleted.status_code)
        self.assertEqual([], self.client.get("/api/learnings").json())

    def test_youtube_ingest_stores_learning(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": "k"}), patch.object(
            self.web, "fetch_transcript", return_value="words " * 100
        ), patch.object(
            self.web, "summarize_transcript", return_value="## What this video is about\nHooks."
        ):
            response = self.client.post(
                "/api/youtube/ingest",
                json={"url": "https://youtu.be/dQw4w9WgXcQ"},
            )
        self.assertEqual(201, response.status_code)
        learnings = self.store.list_learnings()
        self.assertEqual(1, len(learnings))
        self.assertEqual("youtube", learnings[0]["source_type"])

    def test_chat_requires_configuration(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.post("/api/chat", json={"message": "hi"})
        self.assertEqual(400, response.status_code)



class HumanizeTests(unittest.TestCase):
    def test_humanize_skill_loads_last(self) -> None:
        names = [path.name for path in knowledge_files()]
        self.assertEqual("z-humanize.md", names[-1])
        prompt = build_system_prompt()
        self.assertIn("NO EM DASHES", prompt)
        self.assertIn("Not just X, but Y", prompt)
        self.assertIn("delve", prompt)

    def test_stream_scrubs_dashes(self) -> None:
        from copy_agent.web import scrub_dashes

        self.assertEqual(
            "Verified leads, the ones that reply, cost 2-3x less.",
            scrub_dashes("Verified leads—the ones that reply—cost 2–3x less."),
        )
        self.assertNotIn("—", scrub_dashes("a — b"))

if __name__ == "__main__":
    unittest.main()
