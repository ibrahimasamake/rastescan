"""The Groq provider against a fake HTTP server (httpx.MockTransport), plus rate-limit handling."""
import json

import httpx
import pytest

from app.config import Settings
from app.inspector import GroqInspector, InspectionError, InspectorBusy, make_inspector
from tests.conftest import make_result


def mock(inspector, handler):
    inspector.http = httpx.Client(transport=httpx.MockTransport(handler))
    inspector.backoff_s = 0
    return inspector


def groq_answer(text: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"choices": [{"message": {"content": text}}]})


def test_groq_request_and_answer():
    seen = []

    def handler(req: httpx.Request):
        seen.append(json.loads(req.content))
        assert req.headers["authorization"] == "Bearer gsk_test"
        return groq_answer(json.dumps(make_result()))

    g = mock(GroqInspector("gsk_test", "qwen/qwen3.8-27b", "PROMPT"), handler)
    assert g.inspect(b"JPEG").hazard_type == "Pothole"
    body = seen[0]
    assert body["response_format"] == {"type": "json_object"} and body["temperature"] == 0
    assert body["messages"][0] == {"role": "system", "content": "PROMPT"}
    assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_groq_retries_once_after_429_then_succeeds():
    calls = []

    def handler(req):
        calls.append(1)
        return groq_answer("", 429) if len(calls) == 1 else groq_answer(json.dumps(make_result()))

    assert mock(GroqInspector("k", "m", "P"), handler).inspect(b"x").severity_score == 7.6
    assert len(calls) == 2


def test_groq_two_429s_become_busy():
    with pytest.raises(InspectorBusy):
        mock(GroqInspector("k", "m", "P"), lambda req: groq_answer("", 429)).inspect(b"x")


def test_groq_invalid_json_retried_then_error():
    answers = iter(["not json", "still not json"])
    with pytest.raises(InspectionError):
        mock(GroqInspector("k", "m", "P"), lambda req: groq_answer(next(answers))).inspect(b"x")




def test_make_inspector_modes(tmp_path):
    assert make_inspector(Settings(ai_mode="fake")).mode == "fake"
    assert make_inspector(Settings(ai_mode="groq", groq_api_key="k")).mode == "groq"
    with pytest.raises(ValueError):
        make_inspector(Settings(ai_mode="groq", groq_api_key=""))
    with pytest.raises(ValueError):
        make_inspector(Settings(ai_mode="magic"))


def test_busy_error_says_why_and_retry_after_is_used(monkeypatch):
    import httpx

    from app import inspector as mod

    slept = []
    monkeypatch.setattr(mod.time, "sleep", slept.append)
    calls = []

    def answer(req):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "7"}, text='{"error":{"message":"Rate limit reached for tokens per minute"}}')

    with pytest.raises(InspectorBusy) as e:
        mock(GroqInspector("k", "m", "P"), answer).inspect(b"x")
    assert len(calls) == 3 and slept == [7.0, 7.0]
    assert "429" in str(e.value) and "tokens per minute" in str(e.value)






def test_timeout_counts_as_busy_and_patient_copy_waits_longer():
    def slow(req):
        raise httpx.ReadTimeout("slow", request=req)

    g = mock(GroqInspector("k", "m", "P"), slow)
    with pytest.raises(InspectorBusy):
        g.inspect(b"x")
    assert GroqInspector("k", "m", "P").timeout_s == 60
    assert GroqInspector("k", "m", "P").patient().timeout_s == 900


def test_azure_request_shape_and_reasoning_model_fallback():
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append((str(req.url), req.headers.get("api-key"), body))
        if "temperature" in body:
            return httpx.Response(400, text='{"error":{"message":"Unsupported value: temperature does not support 0"}}')
        return groq_answer(json.dumps(make_result()))

    from app.inspector import AzureInspector

    a = mock(AzureInspector("https://r.openai.azure.com/openai/v1/", "KEY", "my-deploy", "PROMPT"), handler)
    assert a.inspect(b"JPEG").hazard_type == "Pothole"
    url, key, first = seen[0]
    assert url == "https://r.openai.azure.com/openai/v1/chat/completions" and key == "KEY"
    assert first["model"] == "my-deploy" and first["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/jpeg")
    assert "temperature" not in seen[1][2]  # retried without it
    with pytest.raises(ValueError):
        AzureInspector("", "k", "d", "P")
