# Choose your AI provider

The inspector sends each (blurred) photo with `prompts/inspection-prompt.md` to a vision model and gets JSON back.
The server validates it, recomputes urgency from the severity score, and sends unsure answers to a person.
Pick the provider with `AI_MODE`.

| `AI_MODE` | Cost | Needs | Good for |
|---|---|---|---|
| `bedrock` | Pay per call (cents per photo with Nova Lite/Pro) | AWS account with Bedrock access; the EC2 role does auth | Production on AWS |
| `groq` | Free tier with rate limits | `GROQ_API_KEY` from console.groq.com | Demos, the expo, low volume |
| `ollama` | Free | A laptop or server running Ollama with a vision model | Fully offline demos, privacy |
| `fake` | Free | Nothing | UI work and tests only; the portal shows a "Test mode" banner |

## Bedrock (Amazon Nova)
```bash
AI_MODE=bedrock AWS_REGION=ap-south-1 BEDROCK_MODEL_ID=apac.amazon.nova-pro-v1:0 make api
```
If your AWS Organization blocks a region, use one it allows (for example `eu-north-1` with `eu.amazon.nova-pro-v1:0`)
and run one real call first; see `docs/aws-setup.md`. Deploy: `RASTESCAN_AI_MODE=bedrock make deploy` (the default).

## Groq (free key)
```bash
export GROQ_API_KEY=gsk_...
AI_MODE=groq make api
```
Default model `meta-llama/llama-4-scout-17b-16e-instruct`. If Groq has retired it, pick a current vision model on
console.groq.com and set `GROQ_MODEL=...`. Deploy: `RASTESCAN_AI_MODE=groq GROQ_API_KEY=gsk_... make deploy`.

## Ollama (local, free)
```bash
ollama pull qwen2.5vl:7b
AI_MODE=ollama make api                 # OLLAMA_URL=http://localhost:11434, OLLAMA_MODEL=qwen2.5vl:7b
```
A 7B vision model takes several seconds per photo on a laptop CPU; a GPU helps. On the EC2 t4g.small it is too slow;
run Ollama on a bigger machine and point `OLLAMA_URL` at it, or use Groq/Bedrock there.

## Rate limits and failures
- The same photo is never inspected twice: results are cached by image hash.
- On HTTP 429 (or Bedrock throttling) the server waits two seconds and retries once.
- If the provider still refuses, the report is saved as **Waiting for a check** and the citizen is told
  "The AI inspector is busy right now… a ward engineer will check the photo". Nothing is lost and nothing
  unchecked is published.
- An answer that is not valid JSON for the schema is retried once with a reminder; then the citizen is asked to try again.

## Compare providers with evidence
1. Put 20–30 photos of real road damage, and a few good roads, in `test-photos/`.
2. Fill `test-photos/labels.csv`:
   ```
   file,hazard_type,urgency,severity
   ihs-gate-pothole.jpg,Pothole,HIGH,7.5
   service-road.jpg,None,LOW,1
   ```
3. Run:
   ```bash
   PROVIDERS=groq,ollama,bedrock PAUSE=2 make evaluate
   ```
It prints one table per provider: hazard accuracy, urgency accuracy, mean absolute severity error, JSON failure rate,
rate-limited share and median seconds per photo, and writes `test-photos/results-<provider>.csv` with every answer.
Choose the cheapest provider whose accuracy is good enough; urgency errors on open manholes matter most.
