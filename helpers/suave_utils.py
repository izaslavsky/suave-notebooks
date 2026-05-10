"""
Shared utilities for SuAVE-launched Jupyter notebooks.

Usage in any notebook (Binder or Colab):
    import sys; sys.path.insert(0, 'helpers')
    import suave_utils as su

    params = su.load_params()           # Binder: reads ~/suave_params.json
                                        # Colab:  reads ~/suave_params.json if
                                        #         written by dispatcher, else needs token
    df     = su.fetch_survey_csv(params)
    df     = su.apply_filters(df, params['filters'])
"""

import json, pathlib, os, sys
import requests
import pandas as pd
from IPython.display import display, HTML, Markdown

PARAMS_FILE = pathlib.Path.home() / "suave_params.json"


# ── Environment detection ────────────────────────────────────────────────────

def in_colab() -> bool:
    return "google.colab" in sys.modules

def in_binder() -> bool:
    return "BINDER_REPO_URL" in os.environ or "BINDER_LAUNCH_HOST" in os.environ


# ── Parameter loading ────────────────────────────────────────────────────────

def load_params(token: str = "", host: str = "") -> dict | None:
    """
    Load SuAVE session parameters.

    On Binder:  ~/suave_params.json was written by receiver.py before this
                notebook opened — just reads the file.
    On Colab:   the dispatcher writes ~/suave_params.json after fetching from
                the session API; subsequent operation notebooks find it here too.
    Fallback:   if the file is absent, fetch from SuAVE session API using
                the supplied token + host.
    """
    if PARAMS_FILE.exists():
        return json.loads(PARAMS_FILE.read_text())

    if token and host:
        resp = requests.get(f"{host}/api/sessions/{token}", timeout=10)
        if resp.status_code == 200:
            params = resp.json()
            # Write so that operation notebooks opened later can read it
            PARAMS_FILE.write_text(json.dumps(params, indent=2))
            return params
        raise RuntimeError(
            f"SuAVE session API returned {resp.status_code}. "
            "The token may have expired (10-minute TTL). Relaunch from SuAVE."
        )
    return None


# ── GitHub repo config (needed to build Colab links) ────────────────────────

def get_repo_config() -> dict:
    """
    Return {owner, repo, ref} used to construct Colab notebook URLs.

    On Binder:  derived from BINDER_REPO_URL environment variable.
    On Colab:   read from repo_config.json at the repo root.
    """
    binder_url = os.environ.get("BINDER_REPO_URL", "")
    if binder_url:
        parts = binder_url.rstrip("/").split("/")
        return {
            "owner": parts[-2] if len(parts) >= 2 else "",
            "repo":  parts[-1] if len(parts) >= 1 else "",
            "ref":   os.environ.get("BINDER_REF", "main"),
        }
    # Walk up from helpers/ to repo root to find repo_config.json
    config_path = pathlib.Path(__file__).parent.parent / "repo_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


# ── URL generation for operation notebooks ──────────────────────────────────

def make_nb_url(nb_path: str) -> str:
    """
    Build the URL to open an operations notebook in the current environment.

    nb_path examples:
        'operations/stats/DescriptiveStats.ipynb'
        'operations/arithmetic/SuaveArithmetic.ipynb'
    """
    if in_binder() or (not in_colab() and "JUPYTERHUB_SERVICE_PREFIX" in os.environ):
        base = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
        return f"{base}lab/tree/{nb_path}"

    if in_colab():
        cfg = get_repo_config()
        if cfg.get("owner") and cfg.get("repo"):
            return (
                f"https://colab.research.google.com/github/"
                f"{cfg['owner']}/{cfg['repo']}/blob/{cfg['ref']}/{nb_path}"
            )

    # Local JupyterLab fallback
    return f"/lab/tree/{nb_path}"


# ── Survey capability detection ──────────────────────────────────────────────

def detect_capabilities(params: dict) -> dict:
    """
    Return survey capabilities by querying GET /getSurvey and checking local NFS paths.

    Keys returned:
      has_images       — full-size images exist on NFS storage
      has_netvis       — survey has network visualization data files
      has_largedataset — /lib-nfs/largedatasets is accessible (e.g. SDG)
      views            — list of enabled view names from the survey record
      localdzc         — NFS path to the .dzc file (empty string if unavailable)
      full_images      — NFS path to the full_images/ directory (empty if unavailable)
    """
    import os, re
    from urllib.parse import urlparse

    dzc        = params.get('dzc', '')
    views      = []
    has_netvis = False

    try:
        origin = urlparse(params.get('surveyurl', ''))
        host   = f"{origin.scheme}://{origin.netloc}"
        resp   = requests.get(
            f"{host}/getSurvey",
            params={'name': params.get('survey', ''), 'user': params.get('user', '')},
            timeout=10,
        )
        if resp.status_code == 200:
            rec        = resp.json()
            dzc        = rec.get('dzc') or dzc
            has_netvis = len(rec.get('netvis', [])) > 0
            views      = rec.get('views', [])
    except Exception:
        pass

    # Full-size images require an NFS-mounted path derived from the DZC URL.
    # Pattern: .../dzgen/lib-staging-uploads/<hash>/content.dzc
    #          → /lib-nfs/dzgen/<hash>/content.dzc
    #          → /lib-nfs/dzgen/<hash>/full_images/
    localdzc    = ''
    full_images = ''
    has_images  = False
    if dzc and len(dzc) > 20:
        m = re.search(r'/dzgen/lib-staging-uploads/(.+)', dzc)
        if m:
            localdzc    = f"/lib-nfs/dzgen/{m.group(1)}"
            full_images = localdzc.replace('/content.dzc', '/full_images/')
            has_images  = os.path.isfile(localdzc) and os.path.isdir(full_images)

    return {
        'has_images':       has_images,
        'has_netvis':       has_netvis,
        'has_largedataset': os.path.isdir('/lib-nfs/largedatasets'),
        'views':            views,
        'localdzc':         localdzc,
        'full_images':      full_images,
    }


# ── Data helpers ─────────────────────────────────────────────────────────────

def fetch_survey_csv(params: dict) -> pd.DataFrame:
    """Download the survey CSV from the SuAVE server."""
    from urllib.parse import urlparse
    origin = urlparse(params["surveyurl"])
    host   = f"{origin.scheme}://{origin.netloc}"
    url    = f"{host}/surveys/{params['csv']}"
    resp   = requests.get(url, timeout=30)
    resp.raise_for_status()
    import io
    return pd.read_csv(io.StringIO(resp.text))


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Reproduce the SuAVE filter state on a pandas DataFrame."""
    mask = pd.Series([True] * len(df), index=df.index)

    for col_raw, allowed in filters.get("string", {}).items():
        col = col_raw.split("#")[0]
        if col in df.columns:
            # Multi-value columns use | separator; check for any match
            def _matches(cell):
                vals = [v.strip() for v in str(cell).split("|")]
                return any(v in allowed for v in vals)
            mask &= df[col].apply(_matches)

    for col_raw, f in filters.get("numeric", {}).items():
        col = col_raw.split("#")[0]
        if col in df.columns:
            num = pd.to_numeric(df[col], errors="coerce")
            mask &= (num >= f["min"]) & (num <= f["max"])

    for col_raw, f in filters.get("datetime", {}).items():
        col = col_raw.split("#")[0]
        if col in df.columns:
            dt = pd.to_datetime(df[col], errors="coerce")
            mask &= (dt >= f["start"]) & (dt <= f["end"])

    return df[mask].copy()


# ── Display helpers ──────────────────────────────────────────────────────────

def show_params(params: dict):
    """Print a compact summary of the loaded SuAVE session."""
    filters = params.get("filters", {})
    n_str  = len(filters.get("string",   {}))
    n_num  = len(filters.get("numeric",  {}))
    n_date = len(filters.get("datetime", {}))
    n_f    = n_str + n_num + n_date
    display(Markdown(
        f"**Survey:** `{params.get('survey', '—')}`  \n"
        f"**User:** `{params.get('user', '—')}`  \n"
        f"**Active filters:** {n_f} "
        f"({n_str} categorical, {n_num} numeric, {n_date} date)"
    ))
