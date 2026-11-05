"""Sends a prepared photo to a vision model and returns a validated Inspection.

Providers, chosen by AI_MODE: bedrock (Amazon Nova), groq (free key, hosted vision model), azure (a vision model
deployed in Azure) and fake (canned answers for
tests and UI work). Every provider gets the same prompt and the same JSON validation; the server, not the model,
decides urgency afterwards.
"""
import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Callable, Protocol

from pydantic import ValidationError

from .pixels import analyze
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


def _why(exc: Exception) -> str:
    resp = getattr(exc, "response", None)
    if isinstance(resp, dict):  # botocore ClientError: {"Error": {"Code": ..., "Message": ...}}
        err = resp.get("Error", {})
        return f"{err.get('Code', 'AWS error')}: {err.get('Message', '')}"[:300]
    if resp is None:
        return str(exc)[:200]
    try:
        body = resp.text[:300]
    except Exception:  # noqa: BLE001 - a streamed or closed response has no text
        body = ""
    return f"HTTP {getattr(resp, 'status_code', '?')} {body}".strip()


def _pause(exc: Exception, default_s: float) -> float:
    """Seconds to wait before retrying: the provider's Retry-After when it sends one (at most 15), else the default."""
    resp = getattr(exc, "response", None)
    try:
        return min(15.0, max(0.0, float(resp.headers["retry-after"])))
    except (AttributeError, KeyError, TypeError, ValueError):
        return default_s


def with_backoff(call: Callable[[], str], is_rate_limit: Callable[[Exception], bool], wait_s: float, retries: int = 2) -> str:
    """Retry rate-limit refusals up to `retries` times; still refused → InspectorBusy that says why."""
    for attempt in range(retries + 1):
        try:
            return call()
        except Exception as exc:
            if not is_rate_limit(exc):
                raise
            if attempt == retries:
                raise InspectorBusy(f"the AI provider is rate limiting requests ({_why(exc)})") from exc
            time.sleep(_pause(exc, wait_s * (attempt + 1)))
    raise AssertionError("unreachable")


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
        self.backoff_s = 4.0

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

    accepts_hint = True

    def inspect(self, jpeg: bytes, hint: str = "") -> Inspection:
        messages = [{
            "role": "user",
            "content": [
                {"image": {"format": "jpeg", "source": {"bytes": jpeg}}},
                {"text": f"{ASK} {hint}".strip()},
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
        self.timeout_s = timeout_s
        self.prompt = prompt
        self.backoff_s = 4.0

    def patient(self, timeout_s: float = 900):
        """A copy that waits much longer for an answer. The background worker uses it for slow local models."""
        import copy

        import httpx

        twin = copy.copy(self)
        twin.http = httpx.Client(timeout=timeout_s)
        twin.timeout_s = timeout_s
        return twin

    @staticmethod
    def _rate_limited(exc: Exception) -> bool:
        resp = getattr(exc, "response", None)
        return resp is not None and getattr(resp, "status_code", 0) in (429, 503)

    def _post(self, messages: list) -> str:
        raise NotImplementedError

    def _first(self, jpeg: bytes, hint: str = "") -> list:
        raise NotImplementedError

    accepts_hint = True

    def inspect(self, jpeg: bytes, hint: str = "") -> Inspection:
        import httpx

        try:
            return self._inspect(jpeg, hint)
        except httpx.TimeoutException as exc:
            raise InspectorBusy(f"the model did not answer within {self.timeout_s:.0f}s") from exc

    def _inspect(self, jpeg: bytes, hint: str = "") -> Inspection:
        messages = self._first(jpeg, hint)
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

    def _first(self, jpeg: bytes, hint: str = "") -> list:
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        return [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": [{"type": "text", "text": f"{ASK} {hint}".strip()}, {"type": "image_url", "image_url": {"url": data_url}}]},
        ]

    def _post(self, messages: list) -> str:
        resp = self.http.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, json={
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": 1200,
            "response_format": {"type": "json_object"},
        })
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""


class AzureInspector(_HttpInspector):
    """A vision model deployed in Azure (Foundry / Azure OpenAI), through its OpenAI-compatible v1 endpoint.

    Needs AZURE_ENDPOINT (like https://NAME.openai.azure.com/openai/v1), AZURE_KEY and AZURE_DEPLOYMENT, the name
    you gave the model when deploying it. Use a model that accepts images, such as gpt-4.1-mini.
    """

    mode = "azure"

    def __init__(self, endpoint: str, api_key: str, deployment: str, prompt: str):
        if not (endpoint and api_key and deployment):
            raise ValueError("AI_MODE=azure needs AZURE_ENDPOINT, AZURE_KEY and AZURE_DEPLOYMENT")
        super().__init__(prompt, timeout_s=60)
        self.url = endpoint.rstrip("/") + "/chat/completions"
        self.api_key, self.model = api_key, deployment

    def _first(self, jpeg: bytes, hint: str = "") -> list:
        data_url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
        return [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": [{"type": "text", "text": f"{ASK} {hint}".strip()}, {"type": "image_url", "image_url": {"url": data_url}}]},
        ]

    # Parameters a model may refuse. gpt-5 and o-series reasoning models reject temperature; the gpt-4 family rejects
    # reasoning_effort. On a 400 that names one, it is dropped and remembered, so only the first call pays for the retry.
    _optional = ("temperature", "reasoning_effort")

    def _post(self, messages: list) -> str:
        dropped = getattr(self, "_dropped", set())
        self._dropped = dropped
        headers = {"api-key": self.api_key}
        while True:
            body = {"model": self.model, "messages": messages, "max_completion_tokens": 2500,
                    "response_format": {"type": "json_object"}}
            if "temperature" not in dropped:
                body["temperature"] = 0
            if "reasoning_effort" not in dropped:
                body["reasoning_effort"] = "minimal"  # reasoning models: little hidden thinking, so the answer is not cut off
            resp = self.http.post(self.url, headers=headers, json=body)
            culprit = next((p for p in self._optional if p not in dropped and resp.status_code == 400 and p in resp.text), None)
            if culprit is None:
                break
            dropped.add(culprit)
        if resp.status_code == 404:
            raise RuntimeError(f"Azure has no deployment named '{self.model}'. AZURE_DEPLOYMENT must be the deployment NAME you "
                               f"typed when deploying the model (Foundry, Deployments), not the model name. Azure said: {resp.text[:200]}")
        if resp.status_code in (401, 403):
            raise RuntimeError(f"Azure rejected the key or endpoint (HTTP {resp.status_code}). Check AZURE_KEY belongs to this "
                               f"resource and AZURE_ENDPOINT is its /openai/v1 address. Azure said: {resp.text[:200]}")
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"] or ""


class GuidedInspector:
    """Analyses the photo's pixels first, asks the model with that as a hint, then checks the answer against the pixels.

    1. pixels.analyze finds the road surface and the patches on it that differ from the asphalt around them.
    2. Those patches go to the model as hints, so it looks in the right places.
    3. Every box the model returns is checked: boxes on cars, buildings or sky, or with nothing unusual inside, are dropped,
       and the rest are snapped onto the damaged patch under them.
    With tiles=True the model also sees four overlapping zoomed-in regions (60% of the photo each, in parallel), because a
    model places boxes much better on a small region and small far potholes only show up zoomed in. Region results are
    mapped back to the whole photo and merged. A failed region is skipped; a failed whole photo raises as usual.
    """

    SPAN, OFFSET = 600, 400  # each region covers 60% of the width and height; the two start points are 0% and 40%

    def __init__(self, base, tiles: bool = False, pixels: bool = True):
        self.base, self.tiles, self.pixels = base, tiles, pixels
        self.mode = base.mode
        self.model = getattr(base, "model", "")
        self.prompt = getattr(base, "prompt", "")

    def patient(self, timeout_s: float = 900):
        base = self.base.patient(timeout_s) if hasattr(self.base, "patient") else self.base
        return GuidedInspector(base, self.tiles, self.pixels)

    @staticmethod
    def _defects(result: Inspection) -> list[Detection]:
        """The real defects in a result, whether or not it carries a full list."""
        return result.detections or ([result] if result.hazard_type != "None" else [])

    def _ask(self, jpeg: bytes) -> Inspection:
        pm = analyze(jpeg) if self.pixels else None
        if pm is not None and getattr(self.base, "accepts_hint", False):
            return self.base.inspect(jpeg, hint=pm.hint())
        return self.base.inspect(jpeg)

    def _tile(self, jpeg: bytes, ox: int, oy: int) -> bytes:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(jpeg)).convert("RGB")
        w, h = img.size
        crop = img.crop((round(w * ox / 1000), round(h * oy / 1000), round(w * (ox + self.SPAN) / 1000), round(h * (oy + self.SPAN) / 1000)))
        out = io.BytesIO()
        crop.save(out, "JPEG", quality=88)
        return out.getvalue()

    def _to_whole(self, d: Detection, ox: int, oy: int) -> Detection:
        b = d.bounding_box
        scale = self.SPAN / 1000
        box = {"ymin": oy + round(b.ymin * scale), "xmin": ox + round(b.xmin * scale),
               "ymax": oy + round(b.ymax * scale), "xmax": ox + round(b.xmax * scale)}
        return d.model_copy(update={"bounding_box": type(b)(**{k: min(1000, max(0, v)) for k, v in box.items()})})

    def inspect(self, jpeg: bytes) -> Inspection:
        import logging
        from concurrent.futures import ThreadPoolExecutor

        if not self.tiles:
            whole = self._ask(jpeg)
            found = self._defects(whole)
        else:
            origins = [(ox, oy) for oy in (0, self.OFFSET) for ox in (0, self.OFFSET)]
            with ThreadPoolExecutor(max_workers=5) as pool:
                whole_f = pool.submit(self._ask, jpeg)
                tile_f = [(o, pool.submit(lambda o=o: self._ask(self._tile(jpeg, *o)))) for o in origins]
                whole = whole_f.result()
                found = self._defects(whole)
                for (ox, oy), fut in tile_f:
                    try:
                        found += [self._to_whole(d, ox, oy) for d in self._defects(fut.result())]
                    except Exception as exc:  # noqa: BLE001 - a missed region only costs some recall
                        logging.getLogger("rastescan").warning("region scan skipped: %s", exc)
        if not found:
            return whole
        if self.pixels:
            pm = analyze(jpeg)
            if pm is not None:
                found = pm.check(found)
        return combine(found)


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


def build_inspector(settings, provider: str, model: str | None = None) -> Inspector:
    """One inspector for a provider and (optionally) a specific model; used at start-up and by the admin Model lab.

    Every real provider is wrapped in GuidedInspector: pixel analysis before and after the model (PIXEL_CHECK=0 turns it
    off), plus a zoomed-region scan (SCAN_TILES=2; on by default for Azure, off elsewhere to spare free-tier limits).
    """
    inspector = _build_one(settings, provider, model)
    if provider == "fake":
        return inspector
    tiles = (settings.scan_tiles or ("2" if provider == "azure" else "1")) == "2"
    pixels = settings.pixel_check != "0"
    return GuidedInspector(inspector, tiles=tiles, pixels=pixels) if (tiles or pixels) else inspector


def _build_one(settings, provider: str, model: str | None) -> Inspector:
    if provider == "fake":
        return FakeInspector()
    prompt = load_prompt(settings.prompt_file)
    if provider == "bedrock":
        return BedrockInspector(model or settings.bedrock_model_id, settings.bedrock_region, prompt)
    if provider == "groq":
        return GroqInspector(settings.groq_api_key, model or settings.groq_model, prompt)
    if provider == "azure":
        return AzureInspector(settings.azure_endpoint, settings.azure_key, model or settings.azure_deployment, prompt)
    raise ValueError(f"Unknown AI_MODE {provider!r}; use bedrock, groq, azure or fake")


def make_inspector(settings) -> Inspector:
    return build_inspector(settings, settings.ai_mode)
