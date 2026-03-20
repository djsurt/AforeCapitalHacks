"""Tests for Podcast Generator."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

import app as app_module
from app import _parse_script_json, research_topic, research_url, generate_script


# ---------------------------------------------------------------------------
# _parse_script_json
# ---------------------------------------------------------------------------

class TestParseScriptJson:
    def test_valid_json_array(self):
        raw = '[{"speaker": "Alex", "text": "Hi"}, {"speaker": "Sam", "text": "Hello"}]'
        result = _parse_script_json(raw)
        assert len(result) == 2
        assert result[0]["speaker"] == "Alex"

    def test_markdown_fences(self):
        raw = '```json\n[{"speaker": "Alex", "text": "Hi"}]\n```'
        result = _parse_script_json(raw)
        assert len(result) == 1

    def test_surrounding_text(self):
        raw = 'Here is the script:\n[{"speaker": "Alex", "text": "Hi"}]\nDone!'
        result = _parse_script_json(raw)
        assert len(result) == 1

    def test_invalid_input(self):
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_script_json("this is not json at all")

    def test_empty_string(self):
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_script_json("")


# ---------------------------------------------------------------------------
# research_topic
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestResearchTopic:
    async def test_success_returns_brief_and_url(self, monkeypatch):
        wiki_url = "https://en.wikipedia.org/wiki/Black_hole"
        opensearch_response = [
            "black holes",
            ["Black hole"],
            ["A black hole is a region..."],
            [wiki_url],
        ]
        extract_response = {
            "query": {
                "pages": {
                    "123": {
                        "title": "Black hole",
                        "extract": "A black hole is a region of spacetime.",
                    }
                }
            }
        }

        mock_client = AsyncMock()
        # First call: opensearch, second call: extract
        resp1 = MagicMock()
        resp1.json.return_value = opensearch_response
        resp1.raise_for_status = MagicMock()

        resp2 = MagicMock()
        resp2.json.return_value = extract_response
        resp2.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(side_effect=[resp1, resp2])
        monkeypatch.setattr(app_module, "http_client", mock_client)

        brief, url = await research_topic("black holes")
        assert "Black hole" in brief
        assert "Source: https://en.wikipedia.org/wiki/Black_hole" in brief
        assert url == wiki_url

    async def test_no_results(self, monkeypatch):
        opensearch_response = ["nothinghere", [], [], []]
        mock_client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = opensearch_response
        resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=resp)
        monkeypatch.setattr(app_module, "http_client", mock_client)

        brief, url = await research_topic("nothinghere")
        assert "No Wikipedia article found" in brief
        assert url is None

    async def test_api_error(self, monkeypatch):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("connection failed"))
        monkeypatch.setattr(app_module, "http_client", mock_client)

        brief, url = await research_topic("test")
        assert "Wikipedia lookup failed" in brief
        assert url is None


# ---------------------------------------------------------------------------
# research_url
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestResearchUrl:
    @respx.mock
    async def test_success(self, monkeypatch):
        target = "https://example.com/article"
        html = "<html><body><article><p>Great content here.</p></article></body></html>"

        mock_client = AsyncMock()
        resp = MagicMock()
        resp.text = html
        resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=resp)
        monkeypatch.setattr(app_module, "http_client", mock_client)

        brief, url = await research_url(target)
        assert "Great content here" in brief
        assert url == target

    async def test_empty_page(self, monkeypatch):
        mock_client = AsyncMock()
        resp = MagicMock()
        resp.text = "<html><body></body></html>"
        resp.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=resp)
        monkeypatch.setattr(app_module, "http_client", mock_client)

        brief, url = await research_url("https://example.com/empty")
        assert "empty" in brief.lower() or "Page content was empty" in brief
        assert url == "https://example.com/empty"

    async def test_fetch_error(self, monkeypatch):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("timeout"))
        monkeypatch.setattr(app_module, "http_client", mock_client)

        brief, url = await research_url("https://example.com/fail")
        assert "Scraping failed" in brief
        assert url == "https://example.com/fail"


# ---------------------------------------------------------------------------
# generate_script
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestGenerateScript:
    async def test_success(self, monkeypatch):
        script_json = json.dumps([
            {"speaker": "Alex", "text": "Hey!"},
            {"speaker": "Sam", "text": "Hello!"},
        ])
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=script_json)]

        mock_client_instance = AsyncMock()
        mock_client_instance.messages.create = AsyncMock(return_value=mock_message)

        monkeypatch.setattr(app_module, "ANTHROPIC_API_KEY", "sk-test-key")
        with patch("anthropic.AsyncAnthropic", return_value=mock_client_instance):
            result = await generate_script("test topic", "some research", "casual")

        assert len(result) == 2
        assert result[0]["speaker"] == "Alex"

    async def test_no_api_key(self, monkeypatch):
        monkeypatch.setattr(app_module, "ANTHROPIC_API_KEY", "")
        result = await generate_script("test", "brief", "casual")
        assert len(result) > 0
        assert result[0]["speaker"] == "Alex"

    async def test_billing_error(self, monkeypatch):
        monkeypatch.setattr(app_module, "ANTHROPIC_API_KEY", "sk-test-key")

        error_response = httpx.Response(
            status_code=402,
            json={"error": {"message": "Your credit balance is too low"}},
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        )
        api_error = __import__("anthropic").APIStatusError(
            message="Your credit balance is too low",
            response=error_response,
            body={"error": {"message": "Your credit balance is too low"}},
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.messages.create = AsyncMock(side_effect=api_error)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client_instance):
            with pytest.raises(HTTPException) as exc_info:
                await generate_script("test", "brief", "casual")
            assert exc_info.value.status_code == 402

    async def test_model_config(self, monkeypatch):
        monkeypatch.setattr(app_module, "ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setattr(app_module, "ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='[{"speaker":"Alex","text":"Hi"}]')]

        mock_client_instance = AsyncMock()
        mock_client_instance.messages.create = AsyncMock(return_value=mock_message)

        with patch("anthropic.AsyncAnthropic", return_value=mock_client_instance) as _:
            await generate_script("test", "brief", "casual")

        call_kwargs = mock_client_instance.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# API routes via httpx ASGITransport
# ---------------------------------------------------------------------------

from fastapi import HTTPException


@pytest.fixture
def async_client(monkeypatch):
    """Create a test client that doesn't require startup/shutdown events."""
    monkeypatch.setattr(app_module, "http_client", AsyncMock())
    transport = httpx.ASGITransport(app=app_module.app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
class TestAPIRoutes:
    async def test_health(self, async_client):
        async with async_client as client:
            resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "anthropic_model" in data

    async def test_generate_with_topic(self, async_client, monkeypatch):
        monkeypatch.setattr(
            app_module, "research_topic",
            AsyncMock(return_value=("Research brief here", "https://en.wikipedia.org/wiki/Test")),
        )
        monkeypatch.setattr(
            app_module, "generate_script",
            AsyncMock(return_value=[{"speaker": "Alex", "text": "Hi"}]),
        )
        monkeypatch.setattr(
            app_module, "generate_voice_clips",
            AsyncMock(return_value=[]),
        )
        monkeypatch.setattr(
            app_module, "stitch_podcast",
            MagicMock(return_value=app_module.OUTPUT_DIR / "test" / "podcast.mp3"),
        )

        async with async_client as client:
            resp = await client.post("/generate", json={"topic": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["topic"] == "test"
        assert data["wikipedia_url"] == "https://en.wikipedia.org/wiki/Test"

    async def test_generate_missing_input(self, async_client):
        async with async_client as client:
            resp = await client.post("/generate", json={})
        assert resp.status_code == 400

    async def test_generate_with_url(self, async_client, monkeypatch):
        monkeypatch.setattr(
            app_module, "research_url",
            AsyncMock(return_value=("Scraped content", "https://example.com/article")),
        )
        monkeypatch.setattr(
            app_module, "generate_script",
            AsyncMock(return_value=[{"speaker": "Sam", "text": "Hey"}]),
        )
        monkeypatch.setattr(
            app_module, "generate_voice_clips",
            AsyncMock(return_value=[]),
        )
        monkeypatch.setattr(
            app_module, "stitch_podcast",
            MagicMock(return_value=app_module.OUTPUT_DIR / "test" / "podcast.mp3"),
        )

        async with async_client as client:
            resp = await client.post("/generate", json={"url": "https://example.com/article"})
        assert resp.status_code == 200
        data = resp.json()
        assert "Article from" in data["topic"]
        assert data["wikipedia_url"] == "https://example.com/article"
