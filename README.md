# KRVE Digital Twin API

Backend scaffold for the KRVE customer Digital Twin flow.

## What this repository does now

- accepts a front full-body image
- accepts a side full-body image
- accepts customer height
- validates uploads
- creates a reconstruction session
- runs reconstruction asynchronously
- exposes session status
- serves the generated `.glb` avatar
- reads real measurements from the reconstruction engine when available
- does **not** fabricate a fake mannequin when no real engine is configured

## API contract

### Create Digital Twin

`POST /v1/reconstruct`

`multipart/form-data`

Fields:

- `frontPhoto`
- `sidePhoto`
- `heightCm`

Initial response:

```json
{
  "success": true,
  "sessionId": "twin_...",
  "status": "queued",
  "avatarUrl": null,
  "measurements": null,
  "confidence": null,
  "message": "Digital Twin reconstruction queued."
}
```

### Poll status

`GET /v1/sessions/{sessionId}`

Completed response:

```json
{
  "success": true,
  "sessionId": "twin_...",
  "status": "completed",
  "avatarUrl": "https://YOUR-SERVICE/generated/twin_....glb",
  "measurements": {
    "heightCm": 170,
    "shoulderCm": 43.2,
    "chestCm": 94.1,
    "waistCm": 80.4,
    "hipCm": 96.0,
    "inseamCm": 78.8,
    "torsoCm": 53.1
  },
  "confidence": 0.86,
  "message": "Digital Twin ready.",
  "error": null
}
```

## Local run

1. Copy `.env.example` to `.env`.
2. Install dependencies.
3. Start:

```bash
uvicorn app:app --reload --port 8000
```

Open:

`http://localhost:8000/docs`

## Reconstruction engine

This repository intentionally separates the web API from the actual GPU/model engine.

Set:

`DIGITAL_TWIN_ENGINE_COMMAND`

Supported placeholders:

- `{front}`
- `{side}`
- `{height}`
- `{output}`
- `{session}`

The command must create a valid `.glb` at `{output}`.

It can optionally create:

`{session}/measurements.json`

Example:

```json
{
  "heightCm": 170,
  "shoulderCm": 43.2,
  "chestCm": 94.1,
  "waistCm": 80.4,
  "hipCm": 96.0,
  "inseamCm": 78.8,
  "torsoCm": 53.1,
  "confidence": 0.86
}
```

## Website connection

The KRVE Next.js route should point its:

`DIGITAL_TWIN_RECONSTRUCTION_URL`

to:

`https://YOUR-BACKEND/v1/reconstruct`

and its:

`DIGITAL_TWIN_RECONSTRUCTION_API_KEY`

to the same value used here as:

`DIGITAL_TWIN_API_KEY`.

## Production note

The included session store is file-based. Use a persistent volume for deployment. When scaling to multiple workers/instances, replace it with durable object storage + a database/queue.
