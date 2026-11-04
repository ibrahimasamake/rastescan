"""Checks the request sent to Groq/Ollama and the retry, with urlopen replaced (no network)."""
import io
import json

import pytest

from app import inspector as mod
from app.inspector import InspectionError, OpenAICompatInspector
from tests.conftest import make_result


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def reply(text: str) -> Reply:
    return Reply(json.dumps({"choices": [{"message": {"content": text}}]}).encode())


@pytest.fixture
def sent(monkeypatch):
    calls, answers = [], []

    def fake_urlopen(req, timeout):
        calls.append((req, json.loads(req.data)))
        return reply(answers.pop(0))

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    return calls, answers


def test_sends_image_with_key_and_parses(sent):
    calls, answers = sent
    answers.append(json.dumps(make_result()))
    result = OpenAICompatInspector("groq", "https://x/v1/", "m", "PROMPT", "KEY").inspect(b"\xff\xd8jpeg")
    req, body = calls[0]
    assert req.full_url == "https://x/v1/chat/completions"
    assert req.get_header("Authorization") == "Bearer KEY"
    assert body["messages"][0] == {"role": "system", "content": "PROMPT"}
    assert body["messages"][1]["content"][0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert result.hazard_type == "Pothole"


def test_retries_once_then_gives_up(sent):
    calls, answers = sent
    answers += ["not json", json.dumps(make_result())]
    assert OpenAICompatInspector("ollama", "http://l/v1", "m", "P").inspect(b"x").hazard_type == "Pothole"
    assert len(calls) == 2 and "Authorization" not in dict(calls[0][0].header_items())
    answers += ["bad", "worse"]
    with pytest.raises(InspectionError):
        OpenAICompatInspector("ollama", "http://l/v1", "m", "P").inspect(b"x")
