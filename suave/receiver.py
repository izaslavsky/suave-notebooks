"""
SuAVE parameter receiver for Binder.

Binder opens:  proxy/8765/receive?token=XXX&host=https://suave.server&nb=SuAVEDispatch.ipynb

This Flask app:
  1. Calls GET {host}/api/sessions/{token} to fetch the session params
  2. Writes them to ~/suave_params.json  (all notebooks in this session read from here)
  3. Redirects the browser to SuAVEDispatch.ipynb (or whatever nb= says)
"""

import json, pathlib, os
import requests
from flask import Flask, request, redirect, Response

app = Flask(__name__)

PARAMS_FILE = pathlib.Path.home() / "suave_params.json"


@app.route("/receive")
def receive():
    token = request.args.get("token", "")
    host  = request.args.get("host",  "")
    nb    = request.args.get("nb",    "SuAVEDispatch.ipynb")

    if not token or not host:
        return Response("Missing token or host parameter", status=400)

    try:
        resp = requests.get(f"{host}/api/sessions/{token}", timeout=10)
        resp.raise_for_status()
        params = resp.json()
    except Exception as exc:
        return Response(f"Could not retrieve SuAVE session: {exc}", status=502)

    PARAMS_FILE.write_text(json.dumps(params, indent=2))

    base = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
    return redirect(f"{base}lab/tree/{nb}")


if __name__ == "__main__":
    app.run(port=8765, host="0.0.0.0")
