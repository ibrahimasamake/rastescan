"""Checks the request sent to Bedrock and the retry, using botocore's Stubber (no AWS account needed)."""
import json

import pytest
from botocore.stub import ANY, Stubber

from app.inspector import BedrockInspector, InspectionError
from tests.conftest import make_result


def answer(text: str) -> dict:
    return {
        "output": {"message": {"role": "assistant", "content": [{"text": text}]}},
        "stopReason": "end_turn",
        "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
        "metrics": {"latencyMs": 1},
    }


@pytest.fixture
def inspector():
    return BedrockInspector("apac.amazon.nova-pro-v1:0", "ap-south-1", "PROMPT")


EXPECTED = {
    "modelId": "apac.amazon.nova-pro-v1:0",
    "system": [{"text": "PROMPT"}],
    "messages": ANY,
    "inferenceConfig": {"maxTokens": 2000, "temperature": 0},
}


def test_sends_image_and_parses_answer(inspector):
    with Stubber(inspector.client) as stub:
        stub.add_response("converse", answer(json.dumps(make_result())), EXPECTED)
        result = inspector.inspect(b"\xff\xd8jpeg")
        stub.assert_no_pending_responses()
    assert result.hazard_type == "Pothole"


def test_retries_once_on_bad_answer(inspector):
    with Stubber(inspector.client) as stub:
        stub.add_response("converse", answer("Sorry, I think it is a pothole."), EXPECTED)
        stub.add_response("converse", answer(json.dumps(make_result())), EXPECTED)
        assert inspector.inspect(b"\xff\xd8jpeg").severity_score == 7.6


def test_gives_up_after_second_bad_answer(inspector):
    with Stubber(inspector.client) as stub:
        stub.add_response("converse", answer("nope"), EXPECTED)
        stub.add_response("converse", answer("still nope"), EXPECTED)
        with pytest.raises(InspectionError):
            inspector.inspect(b"\xff\xd8jpeg")


def test_message_shape(inspector, monkeypatch):
    sent = []
    monkeypatch.setattr(inspector, "_ask", lambda messages: sent.append(messages) or json.dumps(make_result()))
    inspector.inspect(b"JPEG")
    content = sent[0][0]["content"]
    assert content[0] == {"image": {"format": "jpeg", "source": {"bytes": b"JPEG"}}}
    assert sent[0][0]["role"] == "user"
