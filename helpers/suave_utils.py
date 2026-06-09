"""
Shared utilities for SuAVE-launched Jupyter notebooks.

Usage in any notebook (Binder or Colab):
    import sys; sys.path.insert(0, 'helpers')
    import suave_utils as su

    params = su.load_params()           # Binder/JupyterHub: reads ~/suave_params.json
                                        # Colab: reads Drive or ~/suave_params.json;
                                        #        falls back to token + host form fields
    df     = su.fetch_survey_csv(params)
    df     = su.apply_filters(df, params['filters'])
"""

import json, pathlib, os, sys
import requests
import pandas as pd
from dataclasses import dataclass
from IPython.display import display, HTML, Markdown

PARAMS_FILE  = pathlib.Path.home() / "suave_params.json"
_DRIVE_PARAMS = pathlib.Path("/content/drive/MyDrive/.suave_params.json")


# ── Environment ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _Env:
    colab:      bool
    binder:     bool
    jupyterhub: bool

    @property
    def local(self) -> bool:
        return not (self.colab or self.binder or self.jupyterhub)

    def __str__(self) -> str:
        if self.colab:      return "Colab"
        if self.binder:     return "Binder"
        if self.jupyterhub: return "JupyterHub"
        return "local Jupyter"


ENV = _Env(
    colab      = "google.colab" in sys.modules,
    binder     = bool(os.environ.get("BINDER_REPO_URL") or os.environ.get("BINDER_LAUNCH_HOST")),
    jupyterhub = "JUPYTERHUB_SERVICE_PREFIX" in os.environ,
)

# Backward-compatible aliases
def in_colab()  -> bool: return ENV.colab
def in_binder() -> bool: return ENV.binder


def _skipped(label: str) -> None:
    """Display a small grey 'skipped' notice."""
    display(HTML(
        f'<p style="color:#9ca3af;font-size:11px;margin:2px 0">'
        f'&#9135;&nbsp;Skipped — {label} (current environment: {ENV}).</p>'
    ))


# ── Parameter loading ────────────────────────────────────────────────────────

def load_params(token: str = "", host: str = "",
                _silent: bool = False) -> dict | None:
    """
    Load SuAVE session parameters.

    Binder / JupyterHub:
        ~/suave_params.json was written before the notebook opened — just reads it.

    Colab (in order):
        1. ~/suave_params.json  — cached from a previous call in this runtime.
        2. Google Drive          — written by SuAVEDispatch when Drive was mounted.
        3. Session API           — fetched with the supplied token + host.

    _silent=True returns None instead of raising when Drive has no session
    and no token/host were supplied.  Used by notebooks to probe Drive
    without showing an error when credentials will be requested separately.
    """
    if PARAMS_FILE.exists():
        params = json.loads(PARAMS_FILE.read_text())
        _persist_to_drive(params)   # retroactively save to Drive if now mounted
        return params

    if ENV.colab and _DRIVE_PARAMS.exists():
        display(HTML('<p style="color:green">&#10003; Session parameters loaded from Google Drive.</p>'))
        params = json.loads(_DRIVE_PARAMS.read_text())
        PARAMS_FILE.write_text(json.dumps(params, indent=2))
        return params

    if ENV.colab and not (token and host):
        if _silent:
            return None
        drive_mounted = pathlib.Path('/content/drive/MyDrive').exists()
        if drive_mounted:
            msg = ('Drive is mounted but no session file was found. '
                   'Re-run SuAVEDispatch with Drive mounted, then open this notebook again.')
        else:
            msg = ('Google Drive is not mounted. '
                   'Mount Drive first, or enter SUAVE_TOKEN and SUAVE_HOST above and re-run.')
        display(HTML(f'<p style="color:#e07000">{msg}</p>'))
        raise RuntimeError(msg)

    if token and host:
        if not host.startswith(("http://", "https://")):
            host = "https://" + host
        resp = requests.get(f"{host}/api/sessions/{token}", timeout=10)
        if resp.status_code == 200:
            params = resp.json()
            params["_token"] = token
            params["_host"]  = host
            PARAMS_FILE.write_text(json.dumps(params, indent=2))
            _persist_to_drive(params)
            return params
        raise RuntimeError(
            f"SuAVE session API returned {resp.status_code}. "
            "The token may have expired (30-minute TTL). Relaunch from SuAVE."
        )
    return None


def _persist_to_drive(params: dict) -> None:
    """Write params to Google Drive if mounted. Silent on failure."""
    try:
        if _DRIVE_PARAMS.parent.exists():
            _DRIVE_PARAMS.write_text(json.dumps(params, indent=2))
    except Exception:
        pass


# ── GitHub repo config (needed to build Colab links) ────────────────────────

def get_repo_config() -> dict:
    """Return {owner, repo, ref} used to construct Colab notebook URLs."""
    binder_url = os.environ.get("BINDER_REPO_URL", "")
    if binder_url:
        parts = binder_url.rstrip("/").split("/")
        return {
            "owner": parts[-2] if len(parts) >= 2 else "",
            "repo":  parts[-1] if len(parts) >= 1 else "",
            "ref":   os.environ.get("BINDER_REF", "main"),
        }
    config_path = pathlib.Path(__file__).parent.parent / "repo_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text())
    return {}


# ── URL generation for operation notebooks ──────────────────────────────────

def make_nb_url(nb_path: str) -> str:
    """Build the URL to open an operation notebook in the current environment."""
    if ENV.binder or (not ENV.colab and "JUPYTERHUB_SERVICE_PREFIX" in os.environ):
        base = os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/")
        return f"{base}lab/tree/{nb_path}"

    if ENV.colab:
        cfg = get_repo_config()
        if cfg.get("owner") and cfg.get("repo"):
            return (
                f"https://colab.research.google.com/github/"
                f"{cfg['owner']}/{cfg['repo']}/blob/{cfg['ref']}/{nb_path}"
            )

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
    import re
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


# ── HuggingFace helpers ──────────────────────────────────────────────────────

def get_hf_client(token: str = ""):
    """
    Return a HuggingFace InferenceClient.
    Token priority: argument → HF_TOKEN env var → unauthenticated (rate-limited).
    """
    from huggingface_hub import InferenceClient
    tok = token or os.environ.get("HF_TOKEN", "")
    return InferenceClient(token=tok or None)


def batch_apply(series, fn, desc="Processing"):
    """Apply fn(value) to each element of a pandas Series with a tqdm progress bar."""
    from tqdm.auto import tqdm
    tqdm.pandas(desc=desc)
    return series.progress_apply(fn)


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
    token = params.get("_token", "")
    host  = params.get("_host",  "")
    if token and host and ENV.colab:
        drive_saved = _DRIVE_PARAMS.exists()
        drive_note  = (
            "Saved to Google Drive — operation notebooks will load automatically."
            if drive_saved else
            "Mount Google Drive before running this cell to persist credentials "
            "across notebooks automatically: "
            "<code>from google.colab import drive; drive.mount('/content/drive')</code>"
        )
        display(HTML(
            '<details style="margin-top:6px;font-size:12px">'
            '<summary style="cursor:pointer;color:#888">Session credentials '
            '(needed in each operation notebook unless Drive is mounted)</summary>'
            f'<pre style="margin:6px 0;padding:6px;background:#f5f5f5;border-radius:4px">'
            f'SUAVE_TOKEN = "{token}"\nSUAVE_HOST  = "{host}"</pre>'
            f'<span style="color:#888">{drive_note}</span>'
            '</details>'
        ))
