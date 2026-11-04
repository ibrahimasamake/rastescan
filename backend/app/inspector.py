"""Sends a prepared photo to the vision model and returns a validated Inspection."""
import hashlib
import json
import base64
import re
import urllib.request
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from .schema import Inspection


class InspectionError(Exception):
    """The model's answer could not be turned into a valid Inspection."""


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
        return Inspection.model_validate(json.loads(cleaned[start : end + 1]))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise InspectionError(str(exc)) from exc


class Inspector(Protocol):
    mode: str

    def inspect(self, jpeg: bytes) -> Inspection: ...


class BedrockInspector:
    """Amazon Nova through the Bedrock Converse API. Credentials come from the EC2 IAM role."""

    mode = "bedrock"

    def __init__(self, model_id: str, region: str, prompt: str):
        import boto3

        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.model_id = model_id
        self.prompt = prompt

    def _ask(self, messages: list) -> str:
        resp = self.client.converse(
            modelId=self.model_id,
            system=[{"text": self.prompt}],
            messages=messages,
            inferenceConfig={"maxTokens": 800, "temperature": 0},
        )
        return "".join(block.get("text", "") for block in resp["output"]["message"]["content"])

    def inspect(self, jpeg: bytes) -> Inspection:
        messages = [{
            "role": "user",
            "content": [
                {"image": {"format": "jpeg", "source": {"bytes": jpeg}}},
                {"text": "Inspect this road photo. Return only the JSON object."},
            ],
        }]
        answer = self._ask(messages)
        try:
            return parse_inspection(answer)
        except InspectionError:
            messages += [
                {"role": "assistant", "content": [{"text": answer or "(empty)"}]},
                {"role": "user", "content": [{"text": "That answer did not match the schema. Reply with only one valid JSON object that matches it exactly."}]},
            ]
            return parse_inspection(self._ask(messages))


class OpenAICompatInspector:
    """Any vision model behind an OpenAI-style /chat/completions endpoint: Groq (free tier) or a local Ollama."""

    def __init__(self, mode: str, base_url: str, model_id: str, prompt: str, api_key: str = "", timeout: float = 60):
        self.mode = mode
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model_id = model_id
        self.prompt = prompt
        self.api_key = api_key
        self.timeout = timeout

    def _ask(self, messages: list) -> str:
        body = json.dumps({"model": self.model_id, "messages": messages, "temperature": 0, "max_tokens": 800}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.load(resp)
        return data["choices"][0]["message"]["content"] or ""

    def inspect(self, jpeg: bytes) -> Inspection:
        image = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": image}},
                {"type": "text", "text": "Inspect this road photo. Return only the JSON object."},
            ]},
        ]
        answer = self._ask(messages)
        try:
            return parse_inspection(answer)
        except InspectionError:
            messages += [
                {"role": "assistant", "content": answer or "(empty)"},
                {"role": "user", "content": "That answer did not match the schema. Reply with only one valid JSON object that matches it exactly."},
            ]
            return parse_inspection(self._ask(messages))


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
]


class FakeInspector:
    """Canned results picked by image hash. For local development and tests; never for the demo."""

    mode = "fake"

    def inspect(self, jpeg: bytes) -> Inspection:
        pick = hashlib.sha256(jpeg).digest()[0] % len(_FAKE_RESULTS)
        return Inspection.model_validate(_FAKE_RESULTS[pick])
