# CAD Generator Backend

FastAPI service for executing CadQuery scripts and returning CAD exports as base64 data.

## API

`GET /health` returns:

```json
{ "status": "ok", "engine": "CadQuery" }
```

`POST /execute` accepts:

```json
{
  "code": "import cadquery as cq\\nresult = cq.Workplane('XY').box(10, 10, 10)",
  "export_format": "gltf"
}
```

Supported formats are `gltf` (binary GLB), `step`, `stl`, and `svg`. A script must assign either `result` to a `cq.Workplane`/shape or `assy` to a `cq.Assembly`. An empty `code` value runs the built-in sample cube.

Errors return HTTP 200 with `success: false` and an `error` object containing the original exception type, message, and formatted traceback. This keeps syntax, topology, missing-target, and export failures available to an LLM correction loop.

## Local virtual environment

From the repository root:

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 10000
```

Open `http://localhost:10000/docs` for the interactive API documentation.

## Docker

From the repository root:

```bash
docker build -t cad-generator-backend ./backend
docker run --rm -p 10000:10000 cad-generator-backend
```

## Render deployment

Create a Render **Web Service** connected to this repository. Set the root directory to `backend` if Render supports the monorepo setting, or use the repository root with Dockerfile path `backend/Dockerfile`. Use Docker deployment and expose port `10000`. The included image starts Uvicorn on `0.0.0.0:10000`, which matches Render's expected public service port.

The script runner uses an isolated `exec` namespace with restricted builtins and an import allowlist. Python `exec` is not a security boundary against a determined attacker; for untrusted public traffic, run this service in a separately hardened sandbox/container with resource, network, filesystem, and process limits.
