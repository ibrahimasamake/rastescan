"""Sends a prepared photo to a vision model and returns a validated Inspection.

Providers, chosen by AI_MODE: bedrock (Amazon Nova), groq (free key, hosted Llama vision), ollama (local, free)
and fake (canned answers for tests and UI work). Every provider gets the same prompt and the same JSON validation;
the server, not the model, decides urgency afterwards.
"""
import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Callable, Protocol

from pydantic import ValidationError

from .schema import Detection, Inspection, combine

ASK = "Inspect this whole road photo and list every defect you can see. Return only the JSON object."
FIX = "That answer did not match the schema. Reply with only one valid JSON object that matches it exactly."


class InspectionError(Exception):
    """The model's answer could not be turned into a valid Inspection."""


class InspectorBusy(Exception):
    """The provider kept refusing with a rate limit. The report is saved for a person to check instead."""


def load_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # Drop the file's own markdown title line; the rest is the prompt.
    return re.sub(r"\A#[^\n]*\n+", "", text).strip()


def parse_inspection(text: str) -> Inspection:
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise InspectionError("no JSON object in model answer")
    try:
        data = json.loads(cleaned[start : end + 1])
        # New format {"detections": [...]}; a single bare defect object is still accepted.
        raw = data["detections"] if isinstance(data, dict) and "detections" in data else [data]
        if not isinstance(raw, list) or not raw:
            raise InspectionError("no detections in model answer")
        return combine([Detection.model_validate(d) for d in raw])
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise InspectionError(str(exc)) from exc


def with_backoff(call: Callable[[], str], is_rate_limit: Callable[[Exception], bool], wait_s: float) -> str:
    """Retry once after a rate-limit refusal; a second refusal becomes InspectorBusy."""
    try:
        return call()
    except Exception as exc:
        if not is_rate_limit(exc):
            raise
    time.sleep(wait_s)
    try:
        return call()
    except Exception as exc:
        if is_rate_limit(exc):
            raise InspectorBusy("the AI provider is rate limiting requests") from exc
        raise


class Inspector(Protocol):
    mode: str
    model: str

    def inspect(self, jpeg: bytes) -> Inspection: ...


class BedrockInspector:
    """Amazon Nova through the Bedrock Converse API. Credentials come from the EC2 IAM role."""

    mode = "bedrock"

    def __init__(self, model_id: str, region: str, prompt: str):
        import boto3

        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = self.model = model_id
        self.prompt = prompt
        self.backoff_s = 2.0

    @staticmethod
    def _throttled(exc: Exception) -> bool:
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "") if hasattr(exc, "response") else ""
        return code in ("ThrottlingException", "TooManyRequestsException", "ServiceUnavailableException")

    def _ask(self, messages: list) -> str:
        return with_backoff(lambda: self._converse(messages), self._throttled, self.backoff_s)

    def _converse(self, messages: list) -> str:
        resp = self.client.converse(
            modelId=self.model_id,
            system=[{"text": self.prompt}],
            messages=messages,
            inferenceConfig={"maxTokens": 2000, "temperature": 0},
        )
        return "".join(block.get("text", "") for block in resp["output"]["message"]["content"])

    def inspect(self, jpeg: bytes) -> Inspection:
        messages = [{
            "role": "user",
            "content": [
                {"image": {"format": "jpeg", "source": {"bytes": jpeg}}},
                {"text": ASK},
            ],
        }]
        answer = self._ask(messages)
        try:
            return parse_inspection(answer)
        except InspectionError:
            messages += [
                {"role": "assistant", "content": [{"text": answer or "(empty)"}]},
                {"role": "user", "content": [{"text": FIX}]},
            ]
            return parse_inspection(self._ask(messages))



class _HttpInspector:
    """Shared logic for the HTTP providers: one retry on invalid JSON, one backoff on HTTP 429."""

    mode = ""
    model = ""

    def __init__(self, prompt: str, timeout_s: float):
        import httpx

        self.http = httpx.Client(timeout=timeout_s)
        self.prompt = prompt
        self.backoff_s = 2.0

    @staticmethod
    def _rate_limited(exc: Exception) -> bool:
        resp = getattr(exc, "response", None)
        return resp is not None and getattr(resp, "status_code", 0) in (429, 503)

    def _post(self, messages: list) -> str:
        raise NotImplementedError

    def _first(self, jpeg: bytes) -> list:
        raise NotImplementedError

    def inspect(self, jpeg: bytes) -> Inspection:
        messages = self._first(jpeg)
        answer = with_backoff(lambda: self._post(messages), self._rate_limited, self.backoff_s)
        try:
            return parse_inspection(answer)
        except InspectionError:
            messages = messages + [{"role": "assistant", "content": answer or "(empty)"}, {"role": "user", "content": FIX}]
            return parse_inspection(with_backoff(lambda: self._post(messages), self._rate_limited, self.backoff_s))


class GroqInspector(_HttpInspector):
    """Groq's OpenAI-compatible API with a vision model. Needs GROQ_API_KEY (free tier has rate limits)."""

    mode = "groq"
    url = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, prompt: str):
        if not api_key:
            raise ValueError("AI_MODE=groq needs GROQ_API_KEY")
        super().__init__(prompt, timeout_s=60)
        self.api_key, self.model = api_key, model

    def _first(self, jpeg: bytes) -> list:
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        return [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": [{"type": "text", "text": ASK}, {"type": "image_url", "image_url": {"url": data_url}}]},
        ]

    def _post(self, messages: list) -> str:
        resp = self.http.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, json={
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": 2000,
            "response_format": {"type": "json_object"},
        })
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""


class OllamaInspector(_HttpInspector):
    """A local vision model through Ollama, e.g. `ollama pull qwen2.5vl:7b`. Free, offline, slower on a laptop."""

    mode = "ollama"

    def __init__(self, url: str, model: str, prompt: str):
        super().__init__(prompt, timeout_s=180)
        self.url, self.model = url.rstrip("/"), model

    def _first(self, jpeg: bytes) -> list:
        return [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": ASK, "images": [base64.b64encode(jpeg).decode()]},
        ]

    def _post(self, messages: list) -> str:
        resp = self.http.post(f"{self.url}/api/chat", json={
            "model": self.model, "messages": messages, "stream": False, "format": "json", "options": {"temperature": 0, "num_predict": 2000},
        })
        resp.raise_for_status()
        return resp.json()["message"]["content"] or ""


_FAKE_RESULTS = [
    {"hazard_type": "Pothole", "confidence": 0.9, "severity_score": 7.6, "urgency_level": "HIGH",
     "repair_recommendation": "Saw-cut, tack coat, hot-mix asphalt patch with roller compaction.",
     "estimated_repair_time_hours": 3, "estimated_dimensions": {"width_cm": 65, "depth_category": "Deep"},
     "bounding_box": {"ymin": 520, "xmin": 300, "ymax": 800, "xmax": 700}},
    {"hazard_type": "Open Manhole", "confidence": 0.95, "severity_score": 9.6, "urgency_level": "CRITICAL",
     "repair_recommendation": "Barricade now; install a heavy-duty cover and frame.",
     "estimated_repair_time_hours": 6, "estimated_dimensions": {"width_cm": 60, "depth_category": "Sub-base Breach"},
     "bounding_box": {"ymin": 530, "xmin": 370, "ymax": 790, "xmax": 640}},
    {"hazard_type": "Road Fissure", "confidence": 0.8, "severity_score": 4.3, "urgency_level": "MEDIUM",
     "repair_recommendation": "Rout and seal cracks with hot-poured bitumen sealant.",
     "estimated_repair_time_hours": 2, "estimated_dimensions": {"width_cm": 120, "depth_category": "Shallow"},
     "bounding_box": {"ymin": 400, "xmin": 150, "ymax": 700, "xmax": 850}},
    {"hazard_type": "None", "confidence": 0.88, "severity_score": 1.2, "urgency_level": "LOW",
     "repair_recommendation": "No repair needed.", "estimated_repair_time_hours": 0,
     "estimated_dimensions": {"width_cm": 0, "depth_category": "Shallow"},
     "bounding_box": {"ymin": 0, "xmin": 0, "ymax": 0, "xmax": 0}},
    {"detections": [
        {"hazard_type": "Pothole", "confidence": 0.9, "severity_score": 7.6, "urgency_level": "HIGH",
         "repair_recommendation": "Saw-cut, tack coat, hot-mix asphalt patch with roller compaction.",
         "estimated_repair_time_hours": 3, "estimated_dimensions": {"width_cm": 65, "depth_category": "Deep"},
         "bounding_box": {"ymin": 520, "xmin": 120, "ymax": 760, "xmax": 380}},
        {"hazard_type": "Pothole", "confidence": 0.85, "severity_score": 5.2, "urgency_level": "MEDIUM",
         "repair_recommendation": "Cold-mix asphalt patch and tamper compaction.",
         "estimated_repair_time_hours": 2, "estimated_dimensions": {"width_cm": 40, "depth_category": "Moderate"},
         "bounding_box": {"ymin": 600, "xmin": 560, "ymax": 780, "xmax": 760}},
        {"hazard_type": "Road Fissure", "confidence": 0.8, "severity_score": 4.1, "urgency_level": "MEDIUM",
         "repair_recommendation": "Rout and seal cracks with hot-poured bitumen sealant.",
         "estimated_repair_time_hours": 1, "estimated_dimensions": {"width_cm": 150, "depth_category": "Shallow"},
         "bounding_box": {"ymin": 300, "xmin": 200, "ymax": 450, "xmax": 800}},
    ]},
]


class FakeInspector:
    """Canned results picked by image hash. For local development and tests; never for the demo."""

    mode = "fake"
    model = "fake"

    def inspect(self, jpeg: bytes) -> Inspection:
        pick = hashlib.sha256(jpeg).digest()[0] % len(_FAKE_RESULTS)
        return parse_inspection(json.dumps(_FAKE_RESULTS[pick]))


def make_inspector(settings) -> Inspector:
    mode = settings.ai_mode
    if mode == "fake":
        return FakeInspector()
    prompt = load_prompt(settings.prompt_file)
    if mode == "bedrock":
        return BedrockInspector(settings.bedrock_model_id, settings.bedrock_region, prompt)
    if mode == "groq":
        return GroqInspector(settings.groq_api_key, settings.groq_model, prompt)
    if mode == "ollama":
        return OllamaInspector(settings.ollama_url, settings.ollama_model, prompt)
    raise ValueError(f"Unknown AI_MODE {mode!r}; use bedrock, groq, ollama or fake")
