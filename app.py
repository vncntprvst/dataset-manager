import io
import os
import re
import json
import subprocess
import sys
from datetime import datetime
from typing import List, Dict, Tuple, Set, Any
from textwrap import dedent

import streamlit as st
import yaml

from dataset_manager.schema import (
    get_supported_experiment_types,
    collect_required_fields,
    split_user_vs_auto,
    get_nwb_subject_fields,
    get_dandi_required_fields,
    get_field_descriptions,
    get_field_category,
    extract_brainstem_values,
)
from dataset_manager.export import build_workbook_bytes, build_csv_bytes
from dataset_manager.validation import (
    run_pynwb_validation,
    run_nwb_inspector,
    check_template_columns,
    get_minimum_template_requirements,
)


st.set_page_config(page_title="U19 Dataset Manager", page_icon="📄", layout="wide")


def _set_mode(new_mode: str):
    st.session_state["mode"] = new_mode


# ------------------------------
# Dataset repository catalog and helpers
# ------------------------------

def _repository_catalog() -> Dict[str, Dict[str, Any]]:
    """Static catalog of supported data repositories with fields and help.

    Returns a dict keyed by display name. Each entry contains:
    - site: Main website URL
    - description: One-line description
    - howto: Markdown string with account + API/token instructions
    - config_fields: list of field specs: {key,label,type}
    - expected_metadata_fields: list of metadata field names expected when publishing
    """
    return {
        "DANDI Archive": {
            "site": "https://dandiarchive.org",
            "description": "Archive for neurophysiology data with NWB focus.",
            "howto": (
                "Prerequisites\n\n"
                "- Register for DANDI and obtain an API key.\n"
                "- Production: https://dandiarchive.org – Sandbox: https://sandbox.dandiarchive.org (keys/logins differ).\n\n"
                "Creating a new Dandiset\n\n"
                "- Log in and click NEW DANDISET (top-right).\n"
                "- Fill in title and description; an identifier is assigned.\n"
                "- Once the draft is created, you can edit the metadata (License, Keywords ...).\n\n"
                "Docs: https://docs.dandiarchive.org/user-guide-sharing/creating-dandiset/"
            ),
            "config_fields": [
                {"key": "api_key", "label": "DANDI API key", "type": "password"},
                {"key": "dandiset_id", "label": "Dandiset ID (if exists)", "type": "text"},
                {"key": "server", "label": "Server (production/sandbox URL)", "type": "text"},
            ],
            "expected_metadata_fields": [
                "license", "keywords", "contributor", "affiliation", "funding", "citation",
            ],
        },
        "Dryad": {
            "site": "https://datadryad.org",
            "description": "General-purpose data repository for research data.",
            "howto": (
                "- Create a Dryad account.\n"
                "- Obtain an API token if using API-based uploads.\n"
                "Docs: https://datadryad.org/stash/help"
            ),
            "config_fields": [
                {"key": "api_token", "label": "Dryad API token", "type": "password"},
                {"key": "doi", "label": "Dataset DOI (if exists)", "type": "text"},
            ],
            "expected_metadata_fields": ["license", "keywords", "contributor", "affiliation", "funding"],
        },
        "Dataverse": {
            "site": "https://dataverse.org",
            "description": "Open-source data repository platform used by many institutions.",
            "howto": (
                "- Create an account on a Dataverse instance (typically Harvard's - https://dataverse.harvard.edu/).\n"
                "- Generate a personal API token (Account → API Token).\n"
                "Docs: https://guides.dataverse.org/en/latest/user/account.html#api-tokens"
            ),
            "config_fields": [
                {"key": "base_url", "label": "Dataverse base URL", "type": "text"},
                {"key": "api_token", "label": "API token", "type": "password"},
                {"key": "doi", "label": "Dataset DOI (if exists)", "type": "text"},
            ],
            "expected_metadata_fields": ["license", "keywords", "contributor", "affiliation", "funding"],
        },
        "Zenodo": {
            "site": "https://zenodo.org",
            "description": "General-purpose open research repository by CERN.",
            "howto": (
                "- Log in (GitHub/ORCID/Google) and create a personal access token.\n"
                "- Sandbox: https://sandbox.zenodo.org for testing.\n"
                "Docs: https://developers.zenodo.org/#api-access"
            ),
            "config_fields": [
                {"key": "api_token", "label": "Zenodo API token", "type": "password"},
                {"key": "doi", "label": "DOI (if exists)", "type": "text"},
                {"key": "server", "label": "Server (production/sandbox URL)", "type": "text"},
            ],
            "expected_metadata_fields": ["license", "keywords", "contributor", "affiliation", "funding"],
        },
        "Figshare": {
            "site": "https://figshare.com",
            "description": "Repository for papers, datasets, and figures.",
            "howto": (
                "- Create a Figshare account.\n"
                "- Generate a personal token (Applications → Create personal token).\n"
                "Docs: https://docs.figshare.com/"
            ),
            "config_fields": [
                {"key": "api_token", "label": "Figshare API token", "type": "password"},
                {"key": "article_id", "label": "Article ID / DOI (if exists)", "type": "text"},
            ],
            "expected_metadata_fields": ["license", "keywords", "contributor", "affiliation", "funding"],
        },
        "OSF": {
            "site": "https://osf.io",
            "description": "Open Science Framework project and data hosting.",
            "howto": (
                "- Create an OSF account.\n"
                "- Generate a personal access token (Settings → Personal access tokens).\n"
                "Docs: https://developer.osf.io/"
            ),
            "config_fields": [
                {"key": "access_token", "label": "OSF access token", "type": "password"},
                {"key": "project_id", "label": "Project ID / DOI (if exists)", "type": "text"},
            ],
            "expected_metadata_fields": ["license", "keywords", "contributor", "affiliation", "funding"],
        },
    }


def _repo_expected_fields(ds: Dict[str, Any]) -> List[str]:
    repo = (ds or {}).get("repository", {})
    name = repo.get("name")
    if not name:
        return []
    cat = _repository_catalog()
    entry = cat.get(name, {})
    return list(entry.get("expected_metadata_fields", []))


def _ecephys_acq_types() -> List[str]:
    """Best-effort retrieval of Extracellular acquisition types from NeuroConv.

    Inspects neuroconv.datainterfaces.ecephys for available acquisition system modules.
    Returns vendor/source names like 'Blackrock', 'SpikeGLX', 'OpenEphys'.
    """
    try:
        import inspect  # type: ignore
        from neuroconv.datainterfaces import ecephys as nwb_ecephys  # type: ignore

        acq: Set[str] = set()
        # Get module names that represent acquisition systems
        for name, obj in inspect.getmembers(nwb_ecephys):
            # Skip special attributes and base classes
            if name.startswith('_') or name.startswith('base'):
                continue
            # Check if it's a module (subpackage) representing an acquisition system
            if inspect.ismodule(obj) and hasattr(obj, '__path__'):
                # Capitalize first letter for display
                display_name = name.capitalize()
                # Handle special cases for better readability
                if name == 'spikeglx':
                    display_name = 'SpikeGLX'
                elif name == 'openephys':
                    display_name = 'OpenEphys'
                elif name == 'neuralynx':
                    display_name = 'Neuralynx'
                elif name == 'whitematter':
                    display_name = 'White Matter'
                elif name == 'alphaomega':
                    display_name = 'AlphaOmega'
                elif name == 'spikegadgets':
                    display_name = 'SpikeGadgets'
                elif name == 'mcsraw':
                    display_name = 'MCS Raw'
                elif name == 'edf':
                    display_name = 'EDF'
                elif name == 'tdt':
                    display_name = 'TDT'
                acq.add(display_name)
        
        return sorted(acq) if acq else []
    except Exception:
        return []


def _intracellular_acq_types() -> List[str]:
    """Best-effort retrieval of Intracellular acquisition types from NeuroConv.

    Inspects neuroconv.datainterfaces.icephys for available intracellular interfaces.
    Returns patch-clamp technique names like 'Axon', 'HEKA', etc.
    """
    try:
        import inspect  # type: ignore
        from neuroconv.datainterfaces import icephys as nwb_icephys  # type: ignore

        acq: Set[str] = set()
        # Get available interfaces
        for name, obj in inspect.getmembers(nwb_icephys):
            # Skip special attributes and base classes
            if name.startswith('_') or name.lower().startswith('base'):
                continue
            # Look for interface classes
            if inspect.isclass(obj) and "Interface" in name:
                # Extract the acquisition system name
                base = name.replace("RecordingInterface", "").replace("Interface", "")
                if base and base not in ["Base"]:
                    # Handle special cases for better readability
                    if base.lower() == "axon":
                        acq.add("Axon Instruments")
                    elif base.lower() == "heka":
                        acq.add("HEKA")
                    else:
                        acq.add(base)
        
        return sorted(acq) if acq else []
    except Exception:
        pass
    # Fallback to common intracellular techniques
    return ["Patch-clamp", "Current clamp", "Voltage clamp", "Whole-cell", "Cell-attached"]


def _ophys_acq_types() -> List[str]:
    """Retrieve Optical Physiology acquisition types from NeuroConv when available.

    Inspects neuroconv.datainterfaces.ophys for available optical physiology modules.
    Returns vendor/source names like 'Tiff', 'Bruker', 'ScanImage', 'Miniscope'.
    """
    try:
        import inspect  # type: ignore
        from neuroconv.datainterfaces import ophys as nwb_ophys  # type: ignore

        acq: Set[str] = set()
        # Get module names that represent optical physiology systems
        for name, obj in inspect.getmembers(nwb_ophys):
            # Skip special attributes and base classes
            if name.startswith('_') or name.startswith('base'):
                continue
            # Check if it's a module (subpackage) representing an optical system
            if inspect.ismodule(obj) and hasattr(obj, '__path__'):
                # Create display name with proper capitalization
                display_name = name.capitalize()
                # Handle special cases for better readability
                if name == 'brukertiff':
                    display_name = 'Bruker'
                elif name == 'scanimage':
                    display_name = 'ScanImage'
                elif name == 'miniscope':
                    display_name = 'Miniscope'
                elif name == 'micromanagertiff':
                    display_name = 'MicroManager'
                elif name == 'inscopix':
                    display_name = 'Inscopix'
                elif name == 'femtonics':
                    display_name = 'Femtonics'
                elif name == 'tdt_fp':
                    display_name = 'TDT Fiber Photometry'
                elif name == 'sbx':
                    display_name = 'Scanbox'
                elif name == 'thor':
                    display_name = 'ThorLabs'
                elif name == 'tiff':
                    display_name = 'TIFF'
                elif name == 'hdf5':
                    display_name = 'HDF5'
                elif name in ['extract', 'cnmfe', 'cnmf', 'suite2p', 'caiman', 'sima']:
                    # Skip processed data modules
                    continue
                acq.add(display_name)
        
        return sorted(acq) if acq else []
    except Exception:
        pass
    return ["TIFF", "Bruker", "ScanImage", "Miniscope", "ThorLabs", "Inscopix"]

def _behavior_acq_types() -> List[str]:
    """Retrieval of Behavioral acquisition types from NeuroConv.

    Inspects neuroconv.datainterfaces.behavior for available acquisition system modules.
    """
    try:
        import inspect  # type: ignore
        from neuroconv.datainterfaces import behavior as nwb_behavior  # type: ignore

        acq: Set[str] = set()
        # Get module names that represent acquisition systems
        for name, obj in inspect.getmembers(nwb_behavior):
            # Skip special attributes and base classes
            if name.startswith('_') or name.startswith('base'):
                continue
            # Check if it's a module (subpackage) representing an acquisition system
            if inspect.ismodule(obj) and hasattr(obj, '__path__'):
                # Handle special cases to map to desired output format
                if name == 'video':
                    acq.add("Video")
                elif name == 'audio':
                    acq.add("Audio")
                elif name == 'medpc':
                    acq.add("MedPC")
                elif name in ['deeplabcut', 'sleap', 'neuralynx']:
                    if name == 'neuralynx':
                        acq.add("Neuralynx NVT")
                    else:
                        acq.add("Real-time tracking")
                elif name == 'fictrac':
                    acq.add("FicTrac")
                elif name == 'lightningpose':
                    # Lightning Pose is only for offline tracking data processing
                    continue
                elif name == 'miniscope':
                    acq.add("Miniscope Inertial Measurement Unit (IMU)")
                else:
                    # For any other modules, add as-is with capitalization
                    acq.add(name.capitalize())
        
        # Add standard analog measurement option
        acq.add("Analog measurement")
        acq.add("Other")
        
        return sorted(acq) if acq else []
    except Exception:
        pass
    # Fallback to desired output list
    return ["Video", "Audio", "Analog measurement", "MedPC", "Neuralynx NVT", "Real-time tracking", "Other"]

def _acq_options() -> Dict[str, List[str]]:
    """Unified acquisition type options per experiment type.

    Combines electrophysiology split and optical physiology category.
    """
    return {
        "Electrophysiology – Extracellular": _ecephys_acq_types() or [
            "Blackrock",
            "SpikeGLX",
            "OpenEphys",
            "Intan",
            "Neuralynx",
            "Plexon",
            "TDT",
        ],
        "Electrophysiology – Intracellular": _intracellular_acq_types(),
        "Optical Physiology": _ophys_acq_types(),
        # Align with schema.EXPERIMENT_TYPE_FIELDS key
        "Behavior and physiological measurements": _behavior_acq_types(),
        "Stimulations": ["Optogenetics", "Electrical stimulation", "Other"],
        "Sync and Task events or parameters": ["TTL events", "Bpod", "Bonsai", "Harp", "Other behavioral task files"],
        # Always present modality; no specific acquisition subtypes required
        "Experimental metadata and notes": ["General"],
    }


# ------------------------------
# Project + IO helpers
# ------------------------------

def _project_root() -> str:
    return os.environ.get("DM_PROJECT_ROOT", os.getcwd())


def _ingestion_dir(root: str) -> str:
    return os.path.join(root, "ingestion_scripts")


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _sanitize_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s.strip())


def _normalize_field_name(name: str) -> str:
    """Normalize synonymous field names to a canonical identifier.

    Currently de-duplicates variants of session_start_time like
    "session_start_time(YYYY-MM-DD HH:MM)" to "session_start_time".
    """
    s = str(name).strip()
    if re.match(r"^session_start_time\b", s):
        return "session_start_time"
    return s


def _dedupe_fields(fields: List[str]) -> List[str]:
    """Return fields with normalization and stable de-duplication."""
    out: List[str] = []
    seen: Set[str] = set()
    for f in fields:
        cf = _normalize_field_name(f)
        if cf not in seen:
            out.append(cf)
            seen.add(cf)
    return out


def _placeholder_to_regex(placeholder: str) -> str:
    """Convert a placeholder string like '<SUBJECT_ID>_<SESSION_ID>' to a regex pattern.

    Anchors with ^...$ so it must match the whole name. Supports common date tokens.
    """
    s = str(placeholder).strip()
    if not s:
        return r"^.+$"

    def repl(m: re.Match[str]) -> str:
        tok = m.group(1).upper()
        # Date formats
        if tok == "YYYY_MM_DD":
            return r"20\d{2}_\d{2}_\d{2}"
        if tok == "YYYY-MM-DD":
            return r"20\d{2}-\d{2}-\d{2}"
        if tok == "YYYYMMDD":
            return r"20\d{6}"
        if tok == "YYMMDD":
            return r"\d{6}"
        if tok in {"SUBJECT_ID", "SESSION_ID", "CUSTOM"} or tok.startswith("LEVEL_"):
            return r"[A-Za-z0-9._-]+"
        # Generic: accept one path segment
        return r"[^/\\]+"

    # Replace all <...> tokens
    body = re.sub(r"<([^>]+)>", repl, s)
    return f"^{body}$"


def _name_matches_placeholder(placeholder: str, name: str) -> bool:
    try:
        pat = _placeholder_to_regex(placeholder)
        return re.fullmatch(pat, name) is not None
    except Exception:
        return bool(name)


def _compose_script_name(project_name: str, experimenter: str, modalities: List[str]) -> str:
    # Keep filenames short: avoid embedding modality names which can be long
    stamp = datetime.now().strftime("%Y%m%d")
    base = f"{_sanitize_name(project_name)}__{_sanitize_name(experimenter)}__ingest_{stamp}.py"
    return base


def _discover_sessions_by_levels(
    root: str,
    level_configs: List[Dict[str, str]],
    depth_override: int | None = None,
) -> List[Dict[str, str]]:
    """Discover session folders by traversing directory levels as defined in Project.

    Returns a list of dicts with keys: session_id, subject_id, path, date (if available).
    """
    depth = depth_override if isinstance(depth_override, int) and depth_override > 0 else (
        len(level_configs) if isinstance(level_configs, list) and len(level_configs) > 0 else 1
    )
    # Traverse down to the session level while enforcing placeholder patterns at each level
    current: List[str] = [root]
    for i in range(depth):
        placeholder = "<LEVEL>"
        if isinstance(level_configs, list) and i < len(level_configs):
            placeholder = str(level_configs[i].get("placeholder") or "<LEVEL>")
        nxt: List[str] = []
        for parent in current:
            try:
                for e in os.scandir(parent):
                    if not e.is_dir():
                        continue
                    name = e.name
                    # Skip non-data files
                    if name.endswith('.json') or name in ['brainstem_config.yaml', 'dataset.yaml', 'project.json']:
                        continue
                    if _name_matches_placeholder(placeholder, name):
                        nxt.append(e.path)
            except Exception:
                continue
        current = sorted(nxt)
        if not current:
            break
    sessions: List[Dict[str, str]] = []
    # Identify indices for subject and date levels
    types = [str(lc.get("type", "")) for lc in (level_configs or [])]
    try:
        subj_idx = types.index("Subject ID")
    except ValueError:
        subj_idx = None  # type: ignore
    try:
        date_idx = types.index("Session day")
    except ValueError:
        date_idx = None  # type: ignore

    from pathlib import Path
    for p in current:
        try:
            rel_parts = Path(p).resolve().relative_to(Path(root).resolve()).parts
        except Exception:
            # Fallback: split manually (may be less accurate on Windows)
            rel_parts = os.path.relpath(p, root).split(os.sep)
        if not rel_parts:
            continue
        session_id = rel_parts[-1]
        subject_id = rel_parts[subj_idx] if subj_idx is not None and subj_idx < len(rel_parts) else ""
        date_val = rel_parts[date_idx] if date_idx is not None and date_idx < len(rel_parts) else ""
        sessions.append({
            "session_id": session_id,
            "subject_id": subject_id,
            "date": date_val,
            "path": p,
        })
    return sessions


def _open_in_file_manager(path: str, *, select: bool = False) -> None:
    """Open a folder (or reveal a file) in the system file manager.

    select=True attempts to highlight the file when supported by the OS.
    """
    try:
        if os.name == "nt":
            if select and os.path.exists(path):
                subprocess.Popen(["explorer", "/select,", path])
            else:
                os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            if select and os.path.exists(path):
                subprocess.Popen(["open", "-R", path])
            else:
                subprocess.Popen(["open", path])
        else:
            target = path if os.path.isdir(path) else os.path.dirname(path)
            subprocess.Popen(["xdg-open", target])
    except Exception as e:
        st.error(f"Failed to open file manager: {e}")


def _load_dataset_yaml(root: str) -> Dict[str, Any]:
    path = os.path.join(root, "dataset.yaml")
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _save_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)


def _read_json(path: str) -> Any:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ------------------------------
# Script generation (NeuroConv-first template)
# ------------------------------

def _generate_conversion_script_text(cfg: Dict[str, Any]) -> str:
    project = cfg.get("project_name", "U19_Project")
    experimenter = cfg.get("experimenter", "Experimenter")
    exp_types: List[str] = cfg.get("experimental_modalities", [])
    acq_types: Dict[str, List[str]] = cfg.get("acquisition_types", {})

    # Best-effort mapping from acquisition labels to NeuroConv interfaces
    # Users will need to finalize data file paths and specific interface choices.
    ecephys_map = {
        "SpikeGLX": "SpikeGLXRecordingInterface",
        "OpenEphys": "OpenEphysBinaryRecordingInterface",
        "Blackrock": "BlackrockRecordingInterface",
        "Intan": "IntanRecordingInterface",
        "Neuralynx": "NeuralynxRecordingInterface",
        "Plexon": "PlexonRecordingInterface",
        "TDT": "TdtRecordingInterface",
        "EDF": "EDFRecordingInterface",
        "White Matter": "WhiteMatterRecordingInterface",
    }
    icephys_map = {
        "Axon Instruments": "ABFInterface",
        "HEKA": "HEKAInterface",
    }
    ophys_map = {
        "TIFF": "TiffImagingInterface",
        "Tiff": "TiffImagingInterface",
        "Bruker": "BrukerTiffImagingInterface",
        "ScanImage": "ScanImageImagingInterface",
        "Miniscope": "MiniscopeImagingInterface",
        "HDF5": "HDF5ImagingInterface",
    }
    behavior_map = {
        "Video": "VideoInterface",
        "Audio": "AudioInterface",
        "MedPC": "MedPCInterface",
    }

    # Determine modality blocks to include
    include_ecephys = any(et.startswith("Electrophysiology – Extracellular") for et in exp_types)
    include_icephys = any(et.startswith("Electrophysiology – Intracellular") for et in exp_types)
    include_ophys = any(et == "Optical Physiology" for et in exp_types)
    include_behavior = any(et == "Behavior and physiological measurements" for et in exp_types)

    e_labels = acq_types.get("Electrophysiology – Extracellular", []) or ["SpikeGLX"]
    i_labels = acq_types.get("Electrophysiology – Intracellular", []) or ["Axon Instruments"]
    o_labels = acq_types.get("Optical Physiology", []) or ["Tiff"]
    b_labels = acq_types.get("Behavior and physiological measurements", []) or ["Video"]

    ecephys_patterns = {
        "SpikeGLX": ["*.ap.meta", "*.bin"],
        "OpenEphys": ["structure.oebin"],
        "Blackrock": ["*.ns*", "*.nev"],
        "Intan": ["*.rhd", "*.rhs"],
        "Neuralynx": ["*.ncs", "*.nse", "*.nev"],
        "Plexon": ["*.pl2", "*.plx"],
        "TDT": ["*.tsq", "*.tev"],
        "EDF": ["*.edf"],
        "White Matter": ["*.xml"],
    }
    icephys_patterns = {
        "Axon Instruments": ["*.abf"],
        "HEKA": ["*.dat", "*.h5"],
    }
    ophys_patterns = {
        "TIFF": ["*.tif", "*.tiff"],
        "Tiff": ["*.tif", "*.tiff"],
        "Bruker": ["*.tif", "*.tiff"],
        "ScanImage": ["*.tif", "*.tiff"],
        "Miniscope": ["*.avi", "*.mp4", "*.hdf5"],
        "HDF5": ["*.h5", "*.hdf5"],
    }
    behavior_patterns = {
        "Video": ["*.mp4", "*.avi", "*.mov", "*.mkv"],
        "Audio": ["*.wav", "*.flac", "*.mp3"],
        "MedPC": ["*.txt", "*.medpc", "*.csv"],
    }

    detect_lines: List[str] = []
    detect_lines.append("        source_root = pathlib.Path(args.source)")
    detect_lines.append("        source_data: Dict[str, Any] = {}")
    detect_lines.append("")
    detect_lines.append("        def _find_first(patterns):")
    detect_lines.append("            for pat in patterns:")
    detect_lines.append("                hits = list(source_root.rglob(pat))")
    detect_lines.append("                if hits:")
    detect_lines.append("                    return hits")
    detect_lines.append("            return []")
    detect_lines.append("")

    if include_ecephys:
        for lab in e_labels:
            key = f"ecephys__{_sanitize_name(lab)}"
            patterns = repr(ecephys_patterns.get(lab, ['*']))
            detect_lines.extend([
                f"        if '{key}' in ProjectConverter.data_interface_classes:",
                f"            hits = _find_first({patterns})",
                "            if hits:",
                f"                source_data['{key}'] = dict(folder_path=str(hits[0].parent))",
                "",
            ])

    if include_icephys:
        for lab in i_labels:
            key = f"icephys__{_sanitize_name(lab)}"
            patterns = repr(icephys_patterns.get(lab, ['*']))
            detect_lines.extend([
                f"        if '{key}' in ProjectConverter.data_interface_classes:",
                f"            hits = _find_first({patterns})",
                "            if hits:",
                f"                source_data['{key}'] = dict(file_paths=[str(h) for h in hits])",
                "",
            ])

    if include_ophys:
        for lab in o_labels:
            key = f"ophys__{_sanitize_name(lab)}"
            patterns = repr(ophys_patterns.get(lab, ['*']))
            detect_lines.extend([
                f"        if '{key}' in ProjectConverter.data_interface_classes:",
                f"            hits = _find_first({patterns})",
                "            if hits:",
                f"                source_data['{key}'] = dict(file_paths=[str(h) for h in hits])",
                "",
            ])

    if include_behavior:
        for lab in b_labels:
            key = f"behavior__{_sanitize_name(lab)}"
            patterns = repr(behavior_patterns.get(lab, ['*']))
            if lab == "MedPC":
                detect_lines.extend([
                    f"        if '{key}' in ProjectConverter.data_interface_classes:",
                    f"            hits = _find_first({patterns})",
                    "            if hits:",
                    f"                source_data['{key}'] = dict(",
                    "                    file_path=str(hits[0]),",
                    "                    session_conditions={},  # TODO: fill in MedPC session conditions",
                    "                    start_variable='Start',  # TODO: adjust",
                    "                    metadata_medpc_name_to_info_dict={},",
                    "                )",
                    "",
                ])
            else:
                detect_lines.extend([
                    f"        if '{key}' in ProjectConverter.data_interface_classes:",
                    f"            hits = _find_first({patterns})",
                    "            if hits:",
                    f"                source_data['{key}'] = dict(file_paths=[str(h) for h in hits])",
                    "",
                ])

    detect_block = "\n".join(detect_lines)

    lines: List[str] = []
    lines.append("#!/usr/bin/env python")
    lines.append("# Auto-generated by Dataset Manager – NeuroConv-based conversion skeleton")
    lines.append("import os, argparse, datetime, json, pathlib")
    lines.append("from typing import Dict, Any")
    lines.append("import yaml")
    lines.append("import pandas as pd")
    lines.append("try:")
    lines.append("    import brainstem_python_api_tools as bs  # type: ignore")
    lines.append("except Exception:")
    lines.append("    bs = None")
    lines.append("\n# NeuroConv imports (install: pip install neuroconv)")
    lines.append("from neuroconv import NWBConverter")
    if include_ecephys:
        lines.append("from neuroconv.datainterfaces import ecephys as ncv_ecephys")
    if include_icephys:
        lines.append("from neuroconv.datainterfaces import icephys as ncv_icephys")
    if include_ophys:
        lines.append("from neuroconv.datainterfaces import ophys as ncv_ophys")
    if include_behavior:
        for lab in b_labels:
            submod = lab.lower()
            mod_var = f"ncv_behavior_{_sanitize_name(lab).lower()}"
            lines.append(f"from neuroconv.datainterfaces.behavior import {submod} as {mod_var}")
    lines.append("")

    # Build converter class
    lines.append("class ProjectConverter(NWBConverter):")
    lines.append("    data_interface_classes = {}")

    # Add interface class references per modality
    if include_ecephys:
        for lab in e_labels:
            cls = ecephys_map.get(lab, None)
            if cls:
                lines.append(f"    data_interface_classes['ecephys__{_sanitize_name(lab)}'] = getattr(ncv_ecephys, '{cls}', None)")
            else:
                lines.append(f"    # TODO: map '{lab}' to a NeuroConv ecephys interface")
    if include_icephys:
        for lab in i_labels:
            cls = icephys_map.get(lab, None)
            if cls:
                lines.append(f"    data_interface_classes['icephys__{_sanitize_name(lab)}'] = getattr(ncv_icephys, '{cls}', None)")
            else:
                lines.append(f"    # TODO: map '{lab}' to a NeuroConv icephys interface")
    if include_ophys:
        for lab in o_labels:
            cls = ophys_map.get(lab, None)
            if cls:
                lines.append(f"    data_interface_classes['ophys__{_sanitize_name(lab)}'] = getattr(ncv_ophys, '{cls}', None)")
            else:
                lines.append(f"    # TODO: map '{lab}' to a NeuroConv ophys interface")
    if include_behavior:
        for lab in b_labels:
            cls = behavior_map.get(lab, None)
            mod_var = f"ncv_behavior_{_sanitize_name(lab).lower()}"
            if cls:
                lines.append(f"    data_interface_classes['behavior__{_sanitize_name(lab)}'] = getattr({mod_var}, '{cls}', None)")
            else:
                lines.append(f"    # TODO: map '{lab}' to a NeuroConv behavior interface")

    lines.append("")
    lines.append(dedent(f"""
    def main():
        parser = argparse.ArgumentParser(description='Conversion script for {project} ({experimenter}).')
        parser.add_argument('--source', required=True, help='Path to source data root for this session')
        parser.add_argument('--output', required=True, help='Path to output .nwb file')
        parser.add_argument('--session-id', required=True, help='Session identifier')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing output file')
        args = parser.parse_args()

        root = pathlib.Path(__file__).resolve().parents[1]

        # Load project description from dataset.yaml
        project_cfg = {{}}
        ds_path = root / 'dataset.yaml'
        if ds_path.exists():
            with ds_path.open('r', encoding='utf-8') as f:
                project_cfg = yaml.safe_load(f) or {{}}

        # Load template file (CSV or Excel) for per-session metadata
        template_df = pd.DataFrame()
        for ext in ('csv', 'xlsx', 'xls'):
            matches = list(root.glob(f"*recordings*.{{ext}}"))
            if matches:
                tmpl = matches[0]
                template_df = pd.read_csv(tmpl) if ext == 'csv' else pd.read_excel(tmpl)
                break
        session_row = {{}}
        if not template_df.empty and 'session_id' in template_df.columns:
            sel = template_df[template_df['session_id'].astype(str) == args.session_id]
            if not sel.empty:
                session_row = sel.iloc[0].to_dict()

        # Optionally fetch metadata from brainSTEM if API key/config available
        brainstem_vals = {{}}
        cfg_path = root / 'brainstem_config.yaml'
        if bs and cfg_path.exists():
            try:
                with cfg_path.open('r', encoding='utf-8') as f:
                    bs_cfg = yaml.safe_load(f) or {{}}
                # TODO: instantiate brainSTEM client and populate brainstem_vals
            except Exception:
                pass

{detect_block}

        converter = ProjectConverter(source_data=source_data)

        # Fetch and enrich metadata
        metadata = converter.get_metadata()
        metadata.setdefault('NWBFile', {{}})
        metadata['NWBFile'].update({{
            'session_id': args.session_id,
            'session_start_time': datetime.datetime.now().astimezone(),
            'identifier': f"{_sanitize_name(project)}__{{args.session_id}}",
            'experimenter': [project_cfg.get('experimenter', '{experimenter}')],
            'institution': project_cfg.get('institution', ''),
            'lab': project_cfg.get('lab', ''),
        }})

        # Merge template and brainSTEM auto-filled values
        for key, val in session_row.items():
            if key not in metadata['NWBFile'] or not metadata['NWBFile'][key]:
                metadata['NWBFile'][key] = val
        for key, val in brainstem_vals.items():
            if key not in metadata['NWBFile'] or not metadata['NWBFile'][key]:
                metadata['NWBFile'][key] = val
        if not metadata['NWBFile'].get('session_description'):
            metadata['NWBFile']['session_description'] = f'Session {{args.session_id}}'

        # Best-effort derivation of additional fields from source data
        derived: Dict[str, Any] = {{}}
        try:
            # Ephys acquisition system from selected interface keys
            ephys_keys = [k for k in (source_data.keys() if isinstance(source_data, dict) else []) if k.startswith('ecephys__')]
            if ephys_keys:
                # Take first key suffix as system label
                derived['ephys_acq_system'] = ephys_keys[0].split('__', 1)[-1]
                # Attempt to parse SpikeGLX/OpenEphys metadata for sample rate and channels
                import re as _re
                from pathlib import Path as _P
                folder = source_data[ephys_keys[0]].get('folder_path')
                if folder:
                    p = _P(folder)
                    meta_files = list(p.glob('*.meta')) + list(p.glob('*.ap.meta'))
                    if meta_files:
                        try:
                            txt = meta_files[0].read_text(encoding='utf-8', errors='ignore')
                            m = _re.search(r'(?m)^imSampRate=(\d+(?:\.\d+)?)', txt) or _re.search(r'(?m)^acqRate=(\d+(?:\.\d+)?)', txt)
                            if m:
                                derived['sampling_rate_hz'] = float(m.group(1))
                            m2 = _re.search(r'(?m)^nSavedChans=(\d+)', txt)
                            if m2:
                                derived['num_channels'] = int(m2.group(1))
                        except Exception:
                            pass

            # Behavior/video frame rate and camera count
            beh_keys = [k for k in (source_data.keys() if isinstance(source_data, dict) else []) if k.startswith('behavior__')]
            if beh_keys:
                derived['behavior_modality'] = ', '.join(sorted(set(k.split('__', 1)[-1] for k in beh_keys)))
                # Count video files and try to read fps
                from pathlib import Path as _P
                vids = []
                exts = ('*.mp4','*.avi','*.mov','*.mkv')
                # Source may be file_paths list
                for k in beh_keys:
                    files = source_data[k].get('file_paths') or []
                    for f in files:
                        if any(str(f).lower().endswith(e[1:]) for e in exts):
                            vids.append(f)
                if not vids:
                    # fall back to scanning
                    try:
                        for e in exts:
                            vids += [str(p) for p in _P(args.source).rglob(e)]
                    except Exception:
                        pass
                if vids:
                    derived['camera_count'] = len(vids)
                    fps = None
                    try:
                        import cv2  # type: ignore
                        cap = cv2.VideoCapture(vids[0])
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        cap.release()
                    except Exception:
                        try:
                            import imageio.v2 as imageio  # type: ignore
                            r = imageio.get_reader(vids[0])
                            fps = r.get_meta_data().get('fps')
                            r.close()
                        except Exception:
                            fps = None
                    if fps:
                        derived['frame_rate_fps'] = float(fps)
        except Exception:
            pass

        converter.run_conversion(
            metadata=metadata,
            nwbfile_path=args.output,
            overwrite=args.overwrite,
        )

        # Record simple provenance JSON alongside the NWB
        prov = {{
            'project': '{project}',
            'experimenter': '{experimenter}',
            'session_id': args.session_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'interfaces': list(ProjectConverter.data_interface_classes.keys()),
            'auto_fields': derived,
        }}
        with open(args.output + '.provenance.json', 'w', encoding='utf-8') as f:
            json.dump(prov, f, indent=2)

    if __name__ == '__main__':
        main()
    """))

    return "\n".join(lines) + "\n"


# ------------------------------
# Conversion runs tracking
# ------------------------------

def _runs_index_path(root: str) -> str:
    return os.path.join(_ingestion_dir(root), "conversions.json")


def _load_runs(root: str) -> List[Dict[str, Any]]:
    data = _read_json(_runs_index_path(root))
    return data if isinstance(data, list) else []


def _save_runs(root: str, runs: List[Dict[str, Any]]) -> None:
    _ensure_dir(_ingestion_dir(root))
    _save_json(_runs_index_path(root), runs)


def _append_run(root: str, run: Dict[str, Any]) -> None:
    runs = _load_runs(root)
    runs.append(run)
    _save_runs(root, runs)


def _delete_run(root: str, idx: int) -> None:
    runs = _load_runs(root)
    if 0 <= idx < len(runs):
        runs.pop(idx)
        _save_runs(root, runs)


def _spawn_process(cmd: List[str]) -> subprocess.Popen:
    # Non-blocking spawn; leave stdout/stderr to file handles managed by caller if desired
    return subprocess.Popen(cmd)


def _run_script_and_log(script_path: str, source: str, output: str, session_id: str, log_path: str, overwrite: bool = False) -> int:
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"Running: {script_path}\n")
        log.write(f"Session: {session_id}\n")
        log.write(f"Source: {source}\nOutput: {output}\n\n")
        log.flush()
        cmd = ["python", script_path, "--source", source, "--output", output, "--session-id", session_id]
        if overwrite:
            cmd.append("--overwrite")
        try:
            proc = subprocess.Popen(cmd, stdout=log, stderr=log)
            ret = proc.wait()
            log.write(f"\nExit code: {ret}\n")
            return ret
        except Exception as e:
            log.write(f"\nFailed to run script: {e}\n")
            return -1


# def _default_acq_types() -> Dict[str, List[str]]:
#     return {
#         "Electrophysiology – Extracellular": _ecephys_acq_types() or [
#             "Blackrock",
#             "SpikeGLX",
#             "OpenEphys",
#             "Intan",
#             "Neuralynx",
#             "Plexon",
#             "TDT",
#         ],
#         "Electrophysiology – Intracellular": _intracellular_acq_types(),
#         "Behavior tracking": ["Video", "Analog measurement", "Other"],
#         "Optogenetics": ["Stimulation"],
#         "Miniscope imaging": ["Miniscope V4", "UCLA Miniscope", "Other"],
#         "Fiber photometry": ["Doric", "Other"],
#         "2p imaging": ["Resonant", "Galvo", "Other"],
#         "Widefield imaging": ["sCMOS", "Other"],
#         "Experimental metadata": ["General"],
#         "Notes": ["General"],
#     }


def _suggest_raw_formats(exp_types: List[str], acq_map: Dict[str, List[str]]) -> List[Dict[str, str]]:
    """Build suggested Raw data formats rows based on selected experimental types and acquisition types."""
    suggestions: List[Dict[str, str]] = []

    # Enhanced format hints for extracellular vendors based on NeuroConv documentation
    # NOTE: Only raw recording formats, no processed/sorted data
    ecephys_formats = {
        "Blackrock": "Blackrock `.nsx`, `.ccf`, `.nev` files",
        "SpikeGLX": "SpikeGLX `.bin`, `.meta` files (Neuropixels)",
        "OpenEphys": "OpenEphys `.dat`, `.npy`, `.json` or `.continuous`, `.events`, `.spikes` or `.nwb`",
        "Intan": "Intan `.rhd` / `.rhs` files",
        "Neuralynx": "Neuralynx `.ncs`, `.nev`, `.nse`, `.ntt` files", 
        "Plexon": "Plexon `.pl2` / `.plx` files",
        "TDT": "TDT tank files (`.tbk`, `.tev`, `.tsq`, `.sev`)",
        "EDF": "European Data Format `.edf` files",
        "White Matter": "White Matter `.bin` files",
        "Spike2": "Spike2 `.smr` / `.smrx` files",
        "AlphaOmega": "AlphaOmega `.mpx` files",
        "Spikegadgets": "SpikeGadgets `.rec` files",
        "Axon": "Axon Binary Format `.abf` files",
        "Axona": "Axona `.bin`, `.set` files",
        "Biocam": "Biocam `.bwr` files", 
        "Cellexplorer": "CellExplorer `.dat`, `.session.mat` files",
        "Maxwell": "Maxwell `.raw.h5` files",
        "Mearec": "MEArec `.h5` files",
        "Neuroscope": "NeuroScope `.dat`, `.xml` files",
        "Mcsraw": "MCS Raw files",
    }

    # Intracellular format hints
    icephys_formats = {
        "Axon Instruments": "Axon Binary Format `.abf` files",
        "HEKA": "HEKA binary `.dat` files",
        "Patch-clamp": "ABF, HDF5, or custom patch-clamp files",
        "Current clamp": "Current clamp recording files",
        "Voltage clamp": "Voltage clamp recording files", 
        "Whole-cell": "Whole-cell patch recording files",
        "Cell-attached": "Cell-attached recording files",
    }

    # Optical physiology format hints
    ophys_formats = {
        "Tiff": "TIFF stacks (.tif/.tiff) with metadata",
        "Bruker": "Bruker PrairieView raw imaging directories with 'cycle' files, .txt, .xml, and converted .ome.tif files",
        "ScanImage": "ScanImage TIFFs with header metadata",
        "Miniscope": "Miniscope videos (.avi/.mp4) + timestamps",
        "Widefield": "Widefield imaging TIFFs/videos",
        "Photometry": "Fiber photometry CSV/MAT time series",
    }

    for et in exp_types:
        acqs = acq_map.get(et, [])
        if et.startswith("Electrophysiology – Extracellular"):
            for a in acqs or ["Unknown vendor"]:
                fmt = ecephys_formats.get(a, f"{a} electrophysiology files")
                suggestions.append({
                    "Data type": f"Extracellular ephys – {a}",
                    "Format": fmt,
                })
        elif et.startswith("Electrophysiology – Intracellular"):
            for a in acqs or ["Patch-clamp"]:
                fmt = icephys_formats.get(a, "Intracellular recording files")
                suggestions.append({
                    "Data type": f"Intracellular ephys – {a}",
                    "Format": fmt,
                })
        elif et == "Optical Physiology":
            for a in acqs or ["Tiff"]:
                fmt = ophys_formats.get(a, "Imaging files")
                suggestions.append({
                    "Data type": f"Optical physiology – {a}",
                    "Format": fmt,
                })
        elif et == "Stimulations":
            # Twofold data: timestamps and parameters
            suggestions.append({
                "Data type": "Stimulation pulse timestamps",
                "Format": "Timestamps recorded by main acquisition system (e.g., Intan) or separate record of timestamps (e.g., `.csv`/`.mat`/`.txt`)",
            })
            if a.lower() == "optogenetics":
                suggestions.append({
                    "Data type": "Stimulation parameters",
                    "Format": "Include details in metadata/notes (e.g., `.xlsx`/`.json`) with wavelength/power/frequency/duration/etc.",
                })
            elif a.lower() == "electrical stimulation":
                suggestions.append({
                    "Data type": "Stimulation parameters",
                    "Format": "Include details in metadata/notes (e.g., `.xlsx`/`.json`) with current/frequency/duration/etc.",
                })
            else:
                suggestions.append({
                    "Data type": "Stimulation parameters",
                    "Format": "Include details in metadata/notes (e.g., `.xlsx`/`.json`)",
                })
        elif et == "Sync and Task events or parameters":    
            for a in acqs or ["TTL events"]:
                if a.lower() == "ttl events":
                    fmt = "TTL events recorded by acquisition (e.g., Intan) or separate record of timestamps (e.g., `.csv`/`.mat`/`.txt`)"
                    suggestions.append({
                        "Data type": "Synchronization TTL events",
                        "Format": fmt,
                    })
                elif a.lower() in ["bpod", "bonsai", "harp"]:
                    fmt = f"{a} task files (`.csv`, `.mat`, `.json`)"
                    suggestions.append({
                        "Data type": f"Task events, conditions and parameters – {a}",
                        "Format": fmt,
                    })
                else:
                    suggestions.append({
                        "Data type": f"Task events and parameters – {a}",
                        "Format": "Behavioral task files if present (`.csv`, `.mat`, `.json`)",
                    })
        elif et == "Behavior and physiological measurements":
            for a in acqs or ["Video"]:
                if a.lower() == "video":
                    suggestions.append({
                        "Data type": "Behavior videos",
                        "Format": "MP4/MPEG/AVI videos with optional timestamps",
                    })
                elif a.lower() == "audio":
                    suggestions.append({
                        "Data type": "Behavior audio",
                        "Format": "WAV, MP3 or NI audio recordings with optional timestamps. May be recorded within the main modality files",
                    })
                elif a.lower() == "analog measurement":
                    suggestions.append({
                        "Data type": "Behavior analog sensors",
                        "Format": "CSV/MAT/DAT time series data. May be recorded within the main modality files",
                    })
                elif a.lower() == "medpc":
                    suggestions.append({
                        "Data type": "MedPC behavioral data",
                        "Format": "MedPC operant conditioning files (.mpc)",
                    })
                elif a.lower() == "neuralynx nvt":
                    suggestions.append({
                        "Data type": "Neuralynx position tracking",
                        "Format": "Neuralynx .nvt position files",
                    })
                elif a.lower() == "real-time tracking":
                    suggestions.append({
                        "Data type": "Real-time tracking data",
                        "Format": "DeepLabCut/SLEAP pose estimation files (.h5/.csv)",
                    })
                else:
                    suggestions.append({
                        "Data type": f"Behavior tracking – {a}",
                        "Format": "Digital/analog behavioral data",
                    })
        # elif et == "Miniscope imaging":
        #     suggestions.append({
        #         "Data type": "Miniscope imaging", 
        #         "Format": "Raw `.avi`/`.mp4` videos with timestamp files"
        #     })
        #     suggestions.append({
        #         "Data type": "Miniscope metadata",
        #         "Format": "Camera settings and calibration files"
        #     })
        # elif et == "Fiber photometry":
        #     suggestions.append({
        #         "Data type": "Fiber photometry signals", 
        #         "Format": "Time-series CSV/MAT with fluorescence data"
        #     })
        #     suggestions.append({
        #         "Data type": "Photometry hardware settings",
        #         "Format": "Excitation/emission wavelength parameters"
        #     })
        # elif et == "2p imaging":
        #     suggestions.append({
        #         "Data type": "Two-photon imaging", 
        #         "Format": "TIFF stacks/HDF5 with acquisition metadata"
        #     })
        #     suggestions.append({
        #         "Data type": "2p microscope settings",
        #         "Format": "Laser power, objective, and timing parameters"
        #     })
        # elif et == "Widefield imaging":
        #     suggestions.append({
        #         "Data type": "Widefield imaging", 
        #         "Format": "TIFF stacks/videos with illumination metadata"
        #     })
        # elif et == "Experimental metadata and notes":
        #     suggestions.append({
        #         "Data type": "Experimental metadata and notes", 
        #         "Format": "`.xlsx`, `.json`, and text notes"
        #     })


    # # # Always include task/stimulus parameters if Stimulations is selected
    # if "Stimulations" in exp_types:
    #     # suggestions.append({
    #     #     "Data type": "Task/stimulus parameters",
    #     #     "Format": "TTL stimulus events. Other TTLs and behavioral task files if present (`.csv`, `.mat`, `.json`)",
    #     # })
    #     # Check if already added above
    #     if not any(row.get("Data type", "") == "Task/stimulus parameters" for row in suggestions):
    #         suggestions.append({
    #             "Data type": "Task/stimulus parameters",
    #             "Format": "TTL events recorded by acquisition (e.g., Intan) or separate record of timestamps (e.g., `.csv`/`.mat`/`.txt`)",
    #         })
    #     else:
    #         # Update existing entry to include stimulus events
    #         for row in suggestions:
    #             if row.get("Data type", "") == "Task/stimulus parameters":
    #                 existing_format = row.get("Format", "")
    #                 if "TTL stimulus events" not in existing_format:
    #                     row["Format"] = existing_format + "; TTL events recorded by acquisition (e.g., Intan) or separate record of timestamps (e.g., `.csv`/`.mat`/`.txt`)"
    #                 break
    
    # # Add common analysis outputs if multiple modalities selected
    # if len(exp_types) > 1:
    #     suggestions.append({
    #         "Data type": "Cross-modal synchronization",
    #         "Format": "Timing/trigger files for multi-modal alignment",
    #     })
    # Always include metadata/notes (even if no modalities selected)
    suggestions.append({
        "Data type": "Experimental metadata and notes",
        "Format": "`.xlsx`, `.json`, and text notes (may be fetched from brainSTEM)"
    })

    # Deduplicate while preserving order
    seen: Set[Tuple[str, str]] = set()
    dedup: List[Dict[str, str]] = []
    for row in suggestions:
        key = (row.get("Data type", ""), row.get("Format", ""))
        if key not in seen:
            seen.add(key)
            dedup.append(row)
    return dedup


def _suggest_processed_formats(exp_types: List[str], acq_map: Dict[str, List[str]]) -> List[Dict[str, str]]:
    """Build suggested processed data formats for future-proofing.
    
    These are outputs from analysis pipelines, not raw acquisition data.
    """
    suggestions: List[Dict[str, str]] = []

    # Spike sorting outputs
    sorting_formats = {
        "Phy": "Phy sorting `.npy` files (spike times, clusters)",
        "Kilosort": "KiloSort output `.npy` files (templates, spike times)",
        "SpyKing Circus": "Spike sorting results and cluster data",
        "MountainSort": "MountainSort spike sorting outputs",
        "Tridesclous": "Tridesclous spike sorting results",
    }

    # Analysis outputs by modality
    for et in exp_types:
        if et.startswith("Electrophysiology – Extracellular"):
            # Add spike sorting suggestions
            suggestions.extend([
                {"Data type": "Spike sorting - Phy", "Format": sorting_formats["Phy"]},
                {"Data type": "Spike sorting - KiloSort", "Format": sorting_formats["Kilosort"]},
                {"Data type": "LFP analysis", "Format": "Processed LFP spectrograms, power spectra"},
                {"Data type": "Spike train analysis", "Format": "PSTH, raster plots, firing rate data"},
            ])
        elif et.startswith("Electrophysiology – Intracellular"):
            suggestions.extend([
                {"Data type": "Patch-clamp analysis", "Format": "IV curves, membrane properties"},
                {"Data type": "Synaptic analysis", "Format": "EPSCs, IPSCs, paired-pulse ratios"},
            ])
        elif et == "Behavior tracking":
            suggestions.extend([
                {"Data type": "Position tracking", "Format": "Extracted animal positions and trajectories"},
                {"Data type": "Behavioral scoring", "Format": "Automated behavior classification results"},
            ])
        elif et == "Optical Physiology":
            suggestions.extend([
                {"Data type": "Motion correction", "Format": "Motion-corrected imaging stacks"},
                {"Data type": "ROI segmentation", "Format": "Cell masks and fluorescence traces"},
                {"Data type": "dF/F analysis", "Format": "Calcium signal analysis and statistics"},
            ])
        elif et == "2p imaging":
            suggestions.extend([
                {"Data type": "Motion correction", "Format": "Motion-corrected imaging stacks"},
                {"Data type": "ROI segmentation", "Format": "Cell masks and fluorescence traces"},
                {"Data type": "dF/F analysis", "Format": "Calcium signal analysis and statistics"},
            ])
        elif et == "Miniscope imaging":
            suggestions.extend([
                {"Data type": "Miniscope analysis", "Format": "Cell identification and calcium traces"},
                {"Data type": "Place cell analysis", "Format": "Spatial firing maps and statistics"},
            ])
        elif et == "Fiber photometry":
            suggestions.extend([
                {"Data type": "Photometry analysis", "Format": "Processed fluorescence signals and events"},
            ])
        elif et == "Widefield imaging":
            suggestions.extend([
                {"Data type": "Widefield analysis", "Format": "Hemodynamic response maps and time series"},
            ])

    # Cross-modal analysis suggestions
    if len([et for et in exp_types if et.startswith("Electrophysiology")]) > 0 and (
        "Optical Physiology" in exp_types
    ):
        suggestions.append({
            "Data type": "Multi-modal analysis",
            "Format": "Electrophysiology-imaging correlation analysis"
        })

    # Deduplicate while preserving order
    seen: Set[Tuple[str, str]] = set()
    dedup: List[Dict[str, str]] = []
    for row in suggestions:
        key = (row.get("Data type", ""), row.get("Format", ""))
        if key not in seen:
            seen.add(key)
            dedup.append(row)
    return dedup


def _build_tree_text(exp_types: List[str], data_formats: List[Dict[str, str]]) -> str:
    """Construct a folder tree with nodes based on selected experiment types and data formats.

    See also: _build_tree_text_v2 which uses <placeholders>.
    """
    children: List[str] = []

    has_video = any(
        (row.get("Data type", "") + " " + row.get("Format", "")).lower().find("video") >= 0
        for row in data_formats
    )

    if any(et.startswith("Electrophysiology") for et in exp_types):
        children.append("raw_ephys_data")
    if "Behavior and physiological measurements" in exp_types and has_video:
        children.append("raw_behavior_video")
    if "Optical Physiology" in exp_types:
        children.append("raw_imaging_ophys")
    # if "Optogenetics" in exp_types:
    #     children.append("opto_stim_settings")
    # if "Experimental metadata and notes" in exp_types:
    #     children.append("metadata")
    #     children.append("notes")
    #  Experimental metadata and notes may be files in the 
    # experiment, subject or session directories rather than folders

    # Always include processed data placeholder
    children.extend(["processed_data"]) #"task_data",

    # Unique and stable order
    ordered: List[str] = []
    for name in [
        "raw_ephys_data",
        "raw_behavior_video",
        "raw_imaging_ophys",
        "opto_stim_settings",
        "metadata",
        "notes",
        "task_data",
        "processed_data",
    ]:
        if name in children and name not in ordered:
            ordered.append(name)

    tree = (
        "SUBJECT_ID\n"
        "├── YYYY_MM_DD\n"
        "│   ├── SESSION_ID\n"
    )
    for i, c in enumerate(ordered):
        connector = "│   │   ├── " if i < len(ordered) - 1 else "│   │   └── "
        tree += connector + c + "\n"
    return tree


def _build_tree_text_v2(exp_types: List[str], data_formats: List[Dict[str, str]]) -> str:
    """Construct a default folder tree spec using <placeholders>.

    Placeholders:
    - <SUBJECT_ID>: top-level subject folder name
    - <YYYY_MM_DD> or <YYYYMMDD>: date folder name format
    - <SESSION_ID>: session folder name
    """
    children: List[str] = []

    has_video = any(
        (row.get("Data type", "") + " " + row.get("Format", "")).lower().find("video") >= 0
        for row in data_formats
    )
    if any(et.startswith("Electrophysiology") for et in exp_types):
        children.append("raw_ephys_data")
    if "Behavior and physiological measurements" in exp_types and has_video:
        children.append("raw_behavior_video")
    if "Optical Physiology" in exp_types:
        children.append("raw_imaging_ophys")

    # Always include processed data placeholder
    children.extend(["processed_data"])  # "task_data",

    ordered: List[str] = []
    for name in [
        "raw_ephys_data",
        "raw_behavior_video",
        "raw_imaging_ophys",
        "opto_stim_settings",
        "metadata",
        "notes",
        "task_data",
        "processed_data",
    ]:
        if name in children and name not in ordered:
            ordered.append(name)

    lines: List[str] = []
    lines.append("<SUBJECT_ID>")
    lines.append("├── <YYYY_MM_DD>")
    lines.append("│   ├── <SESSION_ID>")
    for i, c in enumerate(ordered):
        is_last = i == len(ordered) - 1
        prefix = "│   │   └── " if is_last else "│   │   ├── "
        lines.append(prefix + c)
    return "\n".join(lines)


def _build_tree_from_levels(level_configs: List[Dict[str, str]], data_folders: List[str]) -> str:
    """Build a tree structure from user-configured directory levels."""
    if not level_configs:
        return "<PROJECT_ROOT>"
    
    lines: List[str] = []
    
    # Build the hierarchy
    for i, config in enumerate(level_configs):
        level_type = config["type"]
        placeholder = config["placeholder"]
        
        if i == 0:
            # First level (root)
            lines.append(placeholder)
        else:
            # Calculate indentation based on level
            indent = "│   " * (i - 1)
            if i == len(level_configs) - 1:
                # Last directory level
                connector = "└── "
            else:
                connector = "├── "
            lines.append(indent + connector + placeholder)
    
    # Add data folders under the last directory level
    if data_folders and level_configs:
        last_level_indent = "│   " * (len(level_configs) - 1)
        for j, folder in enumerate(data_folders):
            is_last_folder = j == len(data_folders) - 1
            folder_connector = "└── " if is_last_folder else "├── "
            lines.append(last_level_indent + "│   " + folder_connector + folder)
    
    return "\n".join(lines)


def _get_data_folders(exp_types: List[str], data_formats: List[Dict[str, str]]) -> List[str]:
    """Get data folders based on experimental modalities."""
    children: List[str] = []

    has_video = any(
        (row.get("Data type", "") + " " + row.get("Format", "")).lower().find("video") >= 0
        for row in data_formats
    )
    if any(et.startswith("Electrophysiology") for et in exp_types):
        children.append("raw_ephys_data")
    if "Behavior and physiological measurements" in exp_types and has_video:
        children.append("raw_behavior_video")
    if "Optical Physiology" in exp_types:
        children.append("raw_imaging_ophys")

    # Always include processed data placeholder
    children.extend(["processed_data"])

    ordered: List[str] = []
    for name in [
        "raw_ephys_data",
        "raw_behavior_video", 
        "raw_imaging_ophys",
        "opto_stim_settings",
        "metadata",
        "notes",
        "task_data",
        "processed_data",
    ]:
        if name in children and name not in ordered:
            ordered.append(name)
    
    return ordered
def _project_form(initial: Dict[str, Any]) -> Dict[str, Any]:
    """Render the project definition form and return values."""

    project_name = st.text_input(
        "Project Name", value=initial.get("project_name", ""), key=f"pn_{initial.get('_mode', '')}"
    )
    experimenter = st.text_input(
        "Experimenter", value=initial.get("experimenter", ""), key=f"ex_{initial.get('_mode', '')}"
    )

    # Hide 'Experimental metadata and notes' from selection; it's always included implicitly
    options_all = [t for t in get_supported_experiment_types() if t != "Experimental metadata and notes"]
    exp_types = st.multiselect(
        "Experimental modalities",
        options=options_all,
        default=initial.get("experimental_modalities", []),
        key=f"et_{initial.get('_mode', '')}",
    )

    ACQ_OPTIONS = _acq_options()
    init_acq = initial.get("acquisition_types", {})
    selected_acq: Dict[str, List[str]] = {}
    for et in exp_types:
        acq = st.multiselect(
            f"Acquisition type – {et}",
            options=ACQ_OPTIONS.get(et, ["Other"]),
            default=init_acq.get(et, []),
            key=f"acq_{initial.get('_mode', '')}_{et}",
        )
        selected_acq[et] = acq

    st.subheader("Raw data formats")
    st.caption("Enter the data types and formats relevant to your project. Add/modify rows as needed.")
    signature = (tuple(sorted(exp_types)), tuple((k, tuple(v)) for k, v in sorted(selected_acq.items())))
    sig_key = f"_formats_signature_{initial.get('_mode', '')}"
    rows_key = f"data_formats_rows_{initial.get('_mode', '')}"
    
    # Force update if experimental types or acquisition types changed
    needs_update = (
        rows_key not in st.session_state or 
        signature != st.session_state.get(sig_key)
    )
    
    if needs_update:
        st.session_state[rows_key] = _suggest_raw_formats(exp_types, selected_acq)
        st.session_state[sig_key] = signature
    data_formats = st.data_editor(
        st.session_state[rows_key],
        hide_index=True,
        num_rows="dynamic",
        column_config={
            "Data type": st.column_config.TextColumn(required=True),
            "Format": st.column_config.TextColumn(required=True),
        },
        key=f"data_formats_editor_{initial.get('_mode', '')}",
    )
    st.session_state[rows_key] = data_formats

    st.subheader("Data organization")
    st.caption(
        "Configure your directory structure. The recording session level defines how deep your session folders are nested."
    )
    
    # Two-column layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Directory structure**")
        
        # Level depth selector
        depth = st.number_input(
            "Level depth for Recording session, with respect to Project root",
            min_value=1,
            max_value=5,
            value=3,
            key=f"depth_{initial.get('_mode', '')}"
        )
        
        # Initialize level configurations if not exist
        level_key = f"level_configs_{initial.get('_mode', '')}"
        if level_key not in st.session_state or len(st.session_state[level_key]) != depth:
            # Default configuration
            default_configs = [
                {"type": "Subject ID", "placeholder": "<SUBJECT_ID>"},
                {"type": "Session day", "placeholder": "<YYYY_MM_DD>"},
                {"type": "Recording session", "placeholder": "<SESSION_ID>"}
            ]
            # Extend or trim to match depth
            while len(default_configs) < depth:
                default_configs.append({"type": "Other", "placeholder": f"<LEVEL_{len(default_configs) + 1}>"})
            st.session_state[level_key] = default_configs[:depth]
        
        level_configs = st.session_state[level_key]
        
        # All available level options
        all_level_options = [
            "Subject ID", 
            "Session day", 
            "Recording session",
            "Other"
        ]
        
        # Default placeholders based on type
        default_placeholders = {
            "Subject ID": "<SUBJECT_ID>",
            "Session day": "<YYYY_MM_DD>", 
            "Recording session": "<SESSION_ID>",
            "Other": "<CUSTOM>"
        }
        
        # Track selected types to filter options for lower levels
        selected_types = []
        
        for i in range(depth):
            current_config = level_configs[i]
            
            # Filter available options - remove already selected types from higher levels
            # but allow "Other" to be selected multiple times
            available_options = []
            for opt in all_level_options:
                if opt == "Other":
                    available_options.append(opt)
                elif opt not in selected_types:
                    available_options.append(opt)
                else:
                    # Add as disabled option to show it's been used
                    available_options.append(f"{opt} (used above)")
            
            # Level type selector
            current_type = current_config["type"]
            # Handle case where current type might be disabled
            if current_type not in available_options:
                if f"{current_type} (used above)" in available_options:
                    display_index = available_options.index(f"{current_type} (used above)")
                elif current_type in all_level_options:
                    # Reset to first available option
                    current_type = available_options[0] if available_options else "Other"
                    display_index = 0
                else:
                    display_index = 0
            else:
                display_index = available_options.index(current_type)
            
            # Create side-by-side layout for each level
            level_col1, level_col2 = st.columns([1, 1])
            
            with level_col1:
                selected_type = st.selectbox(
                    f"Level {i + 1}",
                    options=available_options,
                    index=display_index,
                    key=f"level_type_{i}_{initial.get('_mode', '')}"
                )
            
            # Clean the selected type (remove " (used above)" suffix)
            clean_selected_type = selected_type.replace(" (used above)", "")
            
            # Update placeholder when type changes
            current_placeholder = current_config.get("placeholder", "")
            expected_placeholder = default_placeholders.get(clean_selected_type, f"<LEVEL_{i + 1}>")
            
            # If the placeholder matches the default for the old type, update to new default
            old_type = current_config.get("type", "")
            if current_placeholder == default_placeholders.get(old_type, "") or not current_placeholder:
                new_placeholder = expected_placeholder
            else:
                new_placeholder = current_placeholder
            
            with level_col2:
                placeholder = st.text_input(
                    f"Edit placeholder",
                    value=new_placeholder,
                    key=f"placeholder_{i}_{initial.get('_mode', '')}",
                    help=f"Default for {clean_selected_type}: {expected_placeholder}"
                )
            
            # Update the config
            level_configs[i] = {"type": clean_selected_type, "placeholder": placeholder}
            
            # Add to selected types (but not "Other" since it can be reused)
            if clean_selected_type != "Other" and selected_type not in [opt for opt in available_options if "(used above)" in opt]:
                selected_types.append(clean_selected_type)
        
        st.session_state[level_key] = level_configs
    
    with col2:
        st.markdown("**Tree editor**")
        
        # Get data folders based on experimental modalities
        data_folders = _get_data_folders(exp_types, data_formats)
        
        # Build tree from level configurations
        generated_tree = _build_tree_from_levels(level_configs, data_folders)
        
        # Allow user to edit the generated tree
        tree_text = st.text_area(
            "Generated structure (editable)",
            value=generated_tree,
            height=300,
            key=f"tree_editor_{initial.get('_mode', '')}",
            help="This tree is generated from your level selections. You can edit it directly if needed."
        )
    
    # Full-width preview section
    st.caption("Preview (spec with <placeholders>)")
    st.code(tree_text)

    # Validate actual folders against the spec (generalized level-driven validator)
    def _validate_folder_structure(spec_text: str, base_dir: str, level_cfgs: List[Dict[str, str]]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Validate the project directory structure against user-defined level configurations.

        Rules:
        - Each level has an associated placeholder pattern (may be composite like <SUBJECT_ID>_<SESSION_ID>).
        - A directory at that level must match the placeholder regex produced by _placeholder_to_regex.
        - Directories that do not match are reported as warnings (typo / unexpected folder).
        - If a directory matches a deeper level's placeholder (e.g. a session folder where a date was expected),
          we produce a specific 'misplaced' warning.
        - Whitelisted non-structure directories/files at any level are ignored (config, outputs, etc.).
        - If no valid directory is found for a non-terminal level (and depth > 1), we warn.
        """
        ok = True
        messages: List[str] = []
        stats: Dict[str, Any] = {
            "level_counts": [],  # list of dicts per level
            "invalid": 0,
            "misplaced": 0,
            "recording_sessions": 0,
            "recording_level_index": None,
        }
        if not os.path.isdir(base_dir):
            return False, [f"Base directory does not exist: {base_dir}"]

        # Pre-compute regex patterns for each level placeholder
        level_patterns: List[Tuple[str, re.Pattern[str]]] = []
        for cfg in level_cfgs:
            placeholder = cfg.get("placeholder", "<CUSTOM>")
            try:
                pat = re.compile(_placeholder_to_regex(placeholder))
            except Exception:
                # Fallback broad pattern if malformed
                pat = re.compile(r"^.+$")
            level_patterns.append((placeholder, pat))

        all_placeholders = [cfg.get("placeholder", "") for cfg in level_cfgs]
        recording_level_idx = None
        for i, cfg in enumerate(level_cfgs):
            if cfg.get("type") == "Recording session":
                recording_level_idx = i
                break

        whitelist_dirs = {"ingestion_scripts", "nwb_files", "__pycache__"}
        whitelist_files_ext = {"xlsx", "json", "yaml", "yml", "lock"}

        # Traverse breadth-first over valid parents per level
        parents = [base_dir]
        cumulative_valid_paths: List[List[str]] = []  # store valid names per level
        for level_index, (placeholder, pattern) in enumerate(level_patterns):
            next_parents: List[str] = []
            valid_names: List[str] = []
            invalid_names: List[str] = []
            misplaced_names: List[str] = []

            deeper_patterns = [re.compile(_placeholder_to_regex(ph)) for ph in all_placeholders[level_index + 1 :]] if level_index + 1 < len(all_placeholders) else []

            for parent in parents:
                try:
                    entries = [e for e in os.scandir(parent) if e.is_dir()]
                except FileNotFoundError:
                    continue
                for entry in entries:
                    name = entry.name
                    # Skip hidden / whitelist
                    if name.startswith('.'):
                        continue
                    if name in whitelist_dirs:
                        continue
                    # Skip whitelisted file stems accidentally interpreted as dirs (rare) or meta dirs
                    lower = name.lower()
                    if any(lower.endswith(f".{ext}") for ext in whitelist_files_ext):
                        continue
                    # Core project config directories often at root
                    if name in {".git", "venv", "env", "__pycache__"}:
                        continue

                    if pattern.fullmatch(name):
                        valid_names.append(os.path.join(parent, name))
                        next_parents.append(os.path.join(parent, name))
                    else:
                        # Check for misplaced (matches a deeper level pattern)
                        misplaced = False
                        for dp in deeper_patterns:
                            if dp.fullmatch(name):
                                misplaced = True
                                break
                        if misplaced:
                            misplaced_names.append(name)
                        else:
                            invalid_names.append(name)

            cumulative_valid_paths.append(valid_names)
            stats["level_counts"].append({
                "level": level_index + 1,
                "type": level_cfgs[level_index].get("type"),
                "placeholder": placeholder,
                "valid": len(valid_names),
                "invalid": len(invalid_names),
                "misplaced": len(misplaced_names),
            })
            stats["invalid"] += len(invalid_names)
            stats["misplaced"] += len(misplaced_names)

            # Report issues for this level
            level_label = level_cfgs[level_index].get("type", f"Level {level_index + 1}")
            placeholder_disp = placeholder
            if valid_names:
                messages.append(
                    f"Level {level_index + 1} ({level_label}) – found {len(valid_names)} matching folder(s) for pattern {placeholder_disp}."
                )
            else:
                messages.append(
                    f"Level {level_index + 1} ({level_label}) – no folders matched pattern {placeholder_disp}."
                )
                ok = False

            if misplaced_names:
                ok = False
                preview = ", ".join(misplaced_names[:6]) + (" ..." if len(misplaced_names) > 6 else "")
                messages.append(
                    f"Level {level_index + 1}: {len(misplaced_names)} folder(s) look like deeper-level entries (misplaced): {preview}"
                )
            if invalid_names:
                ok = False
                preview = ", ".join(invalid_names[:6]) + (" ..." if len(invalid_names) > 6 else "")
                messages.append(
                    f"Level {level_index + 1}: {len(invalid_names)} folder(s) do not match expected pattern {placeholder_disp}: {preview}"
                )

            # Stop descending if no valid parents for deeper levels
            if not next_parents:
                # If this is not the final level we expected, remaining levels cannot be validated
                if level_index < len(level_patterns) - 1:
                    messages.append(
                        f"Stopped at level {level_index + 1}; deeper levels cannot be validated because no matching parent folders were found."
                    )
                break
            parents = next_parents

        # Additional recording session presence check
        if recording_level_idx is not None:
            stats["recording_level_index"] = recording_level_idx
            if recording_level_idx < len(cumulative_valid_paths):
                stats["recording_sessions"] = len(cumulative_valid_paths[recording_level_idx])
            if recording_level_idx >= len(cumulative_valid_paths) or not cumulative_valid_paths[recording_level_idx]:
                ok = False
                messages.append("No recording session folders detected at the configured recording level.")

        if ok:
            messages.append("Folder structure looks consistent with the spec.")
        return ok, messages, stats

    check_root = os.environ.get("DM_PROJECT_ROOT", os.getcwd())
    st.caption(f"Structure check base: {check_root}")
    if st.button("Check folder structure against spec", key=f"check_folder_{initial.get('_mode','')}"):
        ok, messages, stats = _validate_folder_structure(tree_text, check_root, level_configs)
        # Summary counts first
        if stats:
            lvl_summ = ", ".join(
                f"L{lc['level']} {lc.get('type') or ''}: {lc['valid']} valid" + (f", {lc['invalid']} invalid" if lc['invalid'] else "") + (f", {lc['misplaced']} misplaced" if lc['misplaced'] else "")
                for lc in stats.get('level_counts', [])
            )
            summary = f"Summary – {lvl_summ}. Total invalid: {stats.get('invalid',0)}, misplaced: {stats.get('misplaced',0)}. Recording sessions: {stats.get('recording_sessions',0)}."
            (st.success if ok else st.warning)(summary)
        for m in messages:
            (st.success if ok else st.warning)(m)

    # In 'Create new dataset', allow selecting the project root directory
    project_root_dir: str | None = None
    if initial.get("_mode") == "new":
        st.subheader("Project root directory")
        st.caption("Select the folder that contains your project's data. The dataset.yaml will be created there.")
        default_root = os.environ.get("DM_PROJECT_ROOT", os.getcwd())
        project_root_dir = st.text_input(
            "Folder path",
            value=str(default_root),
            placeholder="C:/path/to/project or /path/to/project",
            key=f"rootdir_{initial.get('_mode', '')}",
        )

    return {
        "project_name": project_name,
        "experimenter": experimenter,
        "experimental_modalities": exp_types,
        "acquisition_types": selected_acq,
        "data_formats": data_formats,
        "data_organization": tree_text,
        "recording_level_depth": int(depth),
        "level_configs": level_configs,
        "project_root_dir": project_root_dir,
    }


def main() -> None:
    st.title("Dataset Manager for U19 Projects")
    # st.caption("Describe your project and create scripts to package and publish your data.")

    # Sidebar: primary actions
    with st.sidebar:
        st.header("Actions")
        st.button("Project overview", width="stretch", on_click=_set_mode, args=("project",))
        st.button("Dataset repository", width="stretch", on_click=_set_mode, args=("repo",))
        st.button("Data description", width="stretch", on_click=_set_mode, args=("template",))
        st.button("Create conversion scripts", width="stretch", on_click=_set_mode, args=("scripts",))
        st.button("Conversion runs", width="stretch", on_click=_set_mode, args=("runs",))
        st.button("NWB Validation", width="stretch", on_click=_set_mode, args=("validate",))
        st.button("Neurosift Viewer", width="stretch", on_click=_set_mode, args=("neurosift",))
        st.divider()
        if st.button("Quit", type="secondary", width="stretch"):
            os._exit(0)

    # Default to project page on first load
    mode = st.session_state.get("mode", "project")

    if mode == "project":
        st.header("Project overview")
        st.caption("Describe your project organization and data formats.")

        project_root = os.environ.get("DM_PROJECT_ROOT", os.getcwd())
        dataset_path = os.path.join(project_root, "dataset.yaml")
        has_yaml = os.path.exists(dataset_path)

        # Auto-select default tab by ordering: the first tab is active on load
        if has_yaml:
            tab_edit, tab_new = st.tabs(["Edit existing dataset", "Create new dataset"])
        else:
            tab_new, tab_edit = st.tabs(["Create new dataset", "Edit existing dataset"])

        with tab_new:
            data = _project_form({"_mode": "new"})
            if st.button("Save dataset", key="save_new"):
                if not data["project_name"] or not data["experimenter"]:
                    st.error("Project Name and Experimenter are required.")
                else:
                    # Use the chosen root directory if provided
                    target_root = data.get("project_root_dir") or project_root
                    target_path = os.path.join(target_root, "dataset.yaml")
                    os.makedirs(target_root, exist_ok=True)
                    with open(target_path, "w", encoding="utf-8") as f:
                        yaml.safe_dump(data, f)
                    st.success(f"Saved to {target_path}")

        with tab_edit:
            # Allow user to adjust project root unless provided via launcher
            provided_env = "DM_PROJECT_ROOT" in os.environ
            edit_root = st.text_input(
                "Project root directory",
                value=project_root,
                help=(
                    "Folder containing dataset.yaml. "
                    + ("Set by launcher; you can still change it here." if provided_env else "")
                ),
                key="edit_root_dir",
            )
            dataset_path = os.path.join(edit_root, "dataset.yaml")
            if os.path.exists(dataset_path):
                try:
                    with open(dataset_path, "r", encoding="utf-8") as f:
                        loaded = yaml.safe_load(f) or {}
                except Exception:
                    loaded = {}
                loaded["_mode"] = "edit"
                data = _project_form(loaded)
                if st.button("Save changes", key="save_edit"):
                    if not data["project_name"] or not data["experimenter"]:
                        st.error("Project Name and Experimenter are required.")
                    else:
                        # Preserve repository settings and other keys not managed by Project form
                        try:
                            with open(dataset_path, "r", encoding="utf-8") as f:
                                existing_all = yaml.safe_load(f) or {}
                        except Exception:
                            existing_all = {}
                        if isinstance(existing_all, dict) and "repository" in existing_all:
                            data["repository"] = existing_all.get("repository")
                        with open(dataset_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(data, f)
                        st.success(f"Updated {dataset_path}")
            else:
                st.info(f"No dataset.yaml found in {edit_root}.")
        return

    if mode == "repo":
        st.header("Dataset repository")
        st.caption("Select where you plan to publish, and provide credentials and required metadata.")

        root = _project_root()
        ds = _load_dataset_yaml(root)
        repo_cfg = ds.get("repository", {}) if isinstance(ds, dict) else {}

        catalog = _repository_catalog()
        options = list(catalog.keys())
        current = repo_cfg.get("name") if isinstance(repo_cfg, dict) else None
        try:
            idx = options.index(current) if current in options else None
        except Exception:
            idx = None

        sel = st.selectbox("Select a repository", options=options, index=idx if idx is not None else None, placeholder="Choose.")
        if not sel:
            st.info("Choose a repository to see details and settings.")
            return

        entry = catalog.get(sel, {})
        with st.expander(f"About {sel}", expanded=False):
            st.write(entry.get("description", ""))
            site = entry.get("site")
            if site:
                st.markdown(f"Website: [{site}]({site})")

        howto = entry.get("howto")
        if howto:
            st.info(howto)

        st.subheader("Repository settings")
        cfg = dict(repo_cfg.get("config", {})) if isinstance(repo_cfg, dict) else {}
        new_cfg: Dict[str, Any] = {}
        for f in entry.get("config_fields", []):
            key = str(f.get("key"))
            label = str(f.get("label", key))
            ftype = str(f.get("type", "text"))
            default_val = cfg.get(key, "")
            wkey = f"repo_cfg_{sel}_{key}"
            if wkey not in st.session_state:
                st.session_state[wkey] = default_val
            if ftype == "password":
                st.text_input(label, key=wkey, type="password")
            else:
                st.text_input(label, key=wkey)
            new_cfg[key] = st.session_state.get(wkey, "")

        st.subheader("Repository metadata")
        # Apply any prefill captured from a previous fetch before instantiating widgets
        _prefill_key = f"_repo_prefill_meta_{sel}"
        _prefill = st.session_state.pop(_prefill_key, None)
        if isinstance(_prefill, dict):
            for mk, mv in _prefill.items():
                st.session_state[f"repo_meta_{sel}_{mk}"] = mv

        meta = dict(repo_cfg.get("metadata", {})) if isinstance(repo_cfg, dict) else {}
        new_meta: Dict[str, Any] = {}
        for mkey in entry.get("expected_metadata_fields", []):
            label = mkey.capitalize()
            placeholder = "Comma-separated" if mkey == "keywords" else ""
            wkey = f"repo_meta_{sel}_{mkey}"
            if wkey not in st.session_state:
                st.session_state[wkey] = meta.get(mkey, "")
            if mkey in ("citation",):
                st.text_area(label, key=wkey)
            else:
                st.text_input(label, key=wkey, placeholder=placeholder)
            new_meta[mkey] = st.session_state.get(wkey, "")

        # Fetch metadata from repository APIs (DANDI supported)
        if sel == "DANDI Archive":
            if st.button("Fetch Dandiset metadata"):
                api_key = new_cfg.get("api_key") or st.session_state.get(f"repo_cfg_{sel}_api_key", "")
                dandiset_id = new_cfg.get("dandiset_id") or st.session_state.get(f"repo_cfg_{sel}_dandiset_id", "")
                server = new_cfg.get("server") or st.session_state.get(f"repo_cfg_{sel}_server", "")
                if not dandiset_id:
                    st.error("Please enter a Dandiset ID in Repository settings.")
                else:
                    try:
                        import requests  # type: ignore
                        base = "https://api.dandiarchive.org"
                        s = (server or "").lower()
                        if s:
                            if "api.sandbox" in s or "sandbox" in s:
                                base = "https://api.sandbox.dandiarchive.org"
                            elif s.startswith("http") and "api.dandiarchive" in s:
                                base = s.rstrip("/")
                        headers = {}
                        if api_key:
                            headers["Authorization"] = f"token {api_key}"

                        # Try draft first, then fallback to latest published
                        md_obj = None
                        url = f"{base}/api/dandisets/{dandiset_id}/versions/draft"
                        r = requests.get(url, headers=headers, timeout=20)
                        if r.status_code == 200:
                            md_obj = r.json()
                        else:
                            # List versions and pick latest published
                            r2 = requests.get(f"{base}/api/dandisets/{dandiset_id}/versions", headers=headers, timeout=20)
                            r2.raise_for_status()
                            versions = r2.json() or []
                            pub = None
                            for v in versions:
                                if str(v.get("status", "")).lower() == "published":
                                    pub = v
                            if pub and pub.get("version"):
                                vurl = f"{base}/api/dandisets/{dandiset_id}/versions/{pub['version']}"
                                r3 = requests.get(vurl, headers=headers, timeout=20)
                                r3.raise_for_status()
                                md_obj = r3.json()
                        if not md_obj:
                            st.error("Failed to retrieve Dandiset metadata. Check Dandiset ID, server, and permissions.")
                        else:
                            meta_src = md_obj.get("metadata") or md_obj
                            # Map to our fields
                            fetched: Dict[str, str] = {}
                            # license
                            lic = meta_src.get("license")
                            if isinstance(lic, list):
                                fetched["license"] = ", ".join(str(x.get("name") if isinstance(x, dict) else x) for x in lic)
                            elif isinstance(lic, dict):
                                fetched["license"] = str(lic.get("name") or lic.get("spdx") or lic)
                            elif lic:
                                fetched["license"] = str(lic)
                            # keywords
                            kws = meta_src.get("keywords")
                            if isinstance(kws, list):
                                fetched["keywords"] = ", ".join(map(str, kws))
                            elif isinstance(kws, str):
                                fetched["keywords"] = kws
                            # contributors -> contributor names
                            contrib = meta_src.get("contributor") or meta_src.get("contributors")
                            if isinstance(contrib, list):
                                names = []
                                affs: Set[str] = set()
                                for c in contrib:
                                    if isinstance(c, dict):
                                        n = c.get("name") or c.get("fullname") or c.get("email")
                                        if n:
                                            names.append(str(n))
                                        a = c.get("affiliation")
                                        if isinstance(a, list):
                                            for ai in a:
                                                if isinstance(ai, dict):
                                                    nm = ai.get("name")
                                                    if nm:
                                                        affs.add(str(nm))
                                                elif isinstance(ai, str):
                                                    affs.add(ai)
                                        elif isinstance(a, dict):
                                            nm = a.get("name")
                                            if nm:
                                                affs.add(str(nm))
                                        elif isinstance(a, str):
                                            affs.add(a)
                                if names:
                                    fetched["contributor"] = "; ".join(names)
                                if affs:
                                    fetched["affiliation"] = "; ".join(sorted(affs))
                            # funding
                            fund = meta_src.get("funding")
                            if isinstance(fund, list):
                                fetched["funding"] = "; ".join(map(str, fund))
                            elif isinstance(fund, str):
                                fetched["funding"] = fund
                            # citation
                            cit = meta_src.get("citation") or meta_src.get("howToCite")
                            if cit:
                                fetched["citation"] = str(cit)

                            # Queue prefill for the next run to avoid modifying widget state post-instantiation
                            st.session_state[_prefill_key] = fetched
                            # Save into dataset.yaml
                            ds = ds if isinstance(ds, dict) else {}
                            ds.setdefault("repository", {})
                            ds["repository"].setdefault("metadata", {})
                            ds["repository"]["metadata"].update(fetched)
                            try:
                                with open(os.path.join(root, "dataset.yaml"), "w", encoding="utf-8") as f:
                                    yaml.safe_dump(ds, f)
                                st.success("Fetched Dandiset metadata and saved to dataset.yaml")
                                try:
                                    st.rerun()  # Streamlit >= 1.30
                                except Exception:
                                    st.experimental_rerun()
                            except Exception as e:
                                st.error(f"Fetched but failed to save metadata: {e}")
                    except Exception as e:
                        st.error(f"Failed to fetch from DANDI API: {e}")

        if st.button("Save repository settings", type="primary"):
            ds = ds if isinstance(ds, dict) else {}
            ds.setdefault("project_name", ds.get("project_name", ""))
            ds["repository"] = {
                "name": sel,
                "config": new_cfg,
                "metadata": new_meta,
            }
            try:
                os.makedirs(root, exist_ok=True)
                with open(os.path.join(root, "dataset.yaml"), "w", encoding="utf-8") as f:
                    yaml.safe_dump(ds, f)
                st.success("Saved repository settings to dataset.yaml")
            except Exception as e:
                st.error(f"Failed to save repository settings: {e}")
        return

    if mode == "template":
        import glob
        import pandas as pd

        st.header("Data description")
        st.caption("Create a new data description template, or load and edit an existing one.")

        tab_create, tab_load = st.tabs(["Create new", "Load existing"])

        with tab_create:
            # Experimental types are defined on the Project page; show them read-only here
            root = _project_root()
            ds = _load_dataset_yaml(root)
            exp_types: List[str] = list(ds.get("experimental_modalities", [])) if ds else []
            st.write("Metadata will be extracted from these experimental modalities:")
            st.write(", ".join(exp_types) if exp_types else "(none)")
            if not ds:
                st.info("No dataset.yaml found in the project root. Define modalities on the Project page.")
                if st.button("Open Project page", key="go_project_from_template"):
                    _set_mode("project")
                    st.experimental_rerun()
            st.write("Notes and other metadata")
            # Optional: fetch metadata from brainSTEM.org
            # Persist preference across page switches by separating widget state from stored value
            # Persist preference in dataset.yaml (key: use_brainstem)
            ds_cfg_for_brainstem = ds if isinstance(ds, dict) else _load_dataset_yaml(root)
            stored_pref = False
            if isinstance(ds_cfg_for_brainstem, dict):
                stored_pref = bool(ds_cfg_for_brainstem.get("use_brainstem", False))
            # Session state mirrors stored value unless user changes checkbox this render
            if "use_brainstem" not in st.session_state:
                st.session_state["use_brainstem"] = stored_pref
            _use_bs_pref = st.session_state.get("use_brainstem", False)
            _use_bs_checked = st.checkbox(
                "Fetch notes/metadata from brainSTEM.org",
                value=_use_bs_pref,
                key="use_brainstem_widget",
                help="If enabled, subject/session fields will be auto-populated from brainSTEM where possible. Preference saved in dataset.yaml.",
            )
            # If user changed the value, persist it immediately
            if _use_bs_checked != _use_bs_pref:
                st.session_state["use_brainstem"] = _use_bs_checked
                try:
                    merged_ds = _load_dataset_yaml(root)
                    if not isinstance(merged_ds, dict):
                        merged_ds = {}
                    merged_ds["use_brainstem"] = _use_bs_checked
                    with open(os.path.join(root, "dataset.yaml"), "w", encoding="utf-8") as f:
                        yaml.safe_dump(merged_ds, f)
                    st.caption("brainSTEM preference saved to dataset.yaml")
                except Exception as e:
                    st.warning(f"Could not persist brainSTEM preference: {e}")
            if st.session_state.get("use_brainstem"):
                root = _project_root()
                cfg_path = os.path.join(root, "brainstem_config.yaml")
                api_key: str | None = None
                if os.path.exists(cfg_path):
                    try:
                        with open(cfg_path, "r", encoding="utf-8") as f:
                            api_key = (yaml.safe_load(f) or {}).get("api_key")
                    except Exception:
                        api_key = None
                api_key_in = st.text_input(
                    "brainSTEM API key",
                    type="password",
                    value="" if api_key is None else api_key,
                    help="Stored (unencrypted) in brainstem_config.yaml at the project root.",
                )
                if st.button("Save brainSTEM API key"):
                    try:
                        with open(cfg_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump({"api_key": api_key_in}, f)
                        st.success(f"Saved API key to {cfg_path}")
                        api_key = api_key_in
                    except Exception as e:
                        st.error(f"Failed to save config: {e}")
                st.caption("Test fetching metadata for a specific Session ID (case-sensitive).")
                test_col1, test_col2 = st.columns([2,1])
                with test_col1:
                    session_id_input = st.text_input("Session ID to test", key="brainstem_test_session_id")
                with test_col2:
                    limit = st.number_input("Max notes", min_value=1, max_value=200, value=50, step=1, help="Limit notes fetched for inspection.")
                if st.button("Test brainSTEM fetch", disabled=not bool(api_key)):
                    if not api_key:
                        st.error("API key required to fetch metadata.")
                    elif not session_id_input.strip():
                        st.warning("Enter a Session ID to test.")
                    else:
                        try:
                            import requests  # type: ignore
                            sid = session_id_input.strip()
                            headers = {"Authorization": f"Bearer {api_key}"}
                            base = "https://www.brainstem.org/api"
                            # Prefer private portal (requires token); fallback to public if 403/401
                            params = {
                                "filter{name}": sid,
                                "limit": int(limit),
                            }
                            url_private = f"{base}/private/stem/session/"
                            resp = requests.get(url_private, headers=headers, params=params, timeout=20)
                            if resp.status_code in (401, 403):
                                url_public = f"{base}/public/stem/session/"
                                resp = requests.get(url_public, params=params, timeout=20)
                            resp.raise_for_status()
                            payload = resp.json()
                            # Normalize list of sessions
                            if isinstance(payload, dict):
                                if "sessions" in payload and isinstance(payload["sessions"], list):
                                    sessions = payload["sessions"]
                                elif "results" in payload and isinstance(payload["results"], list):
                                    sessions = payload["results"]
                                else:
                                    # If detail view (single session)
                                    if "session" in payload and isinstance(payload["session"], dict):
                                        sessions = [payload["session"]]
                                    else:
                                        # Fallback: treat as unknown structure
                                        sessions = []
                            elif isinstance(payload, list):
                                sessions = payload
                            else:
                                sessions = []
                            # If filter didn't return anything, optionally attempt direct ID lookup
                            if not sessions and len(sid) > 10:  # heuristic: looks like a UUID
                                detail_url = f"{url_private}{sid}/"
                                detail_resp = requests.get(detail_url, headers=headers, timeout=20)
                                if detail_resp.status_code in (401, 403):
                                    detail_url = f"{base}/public/stem/session/{sid}/"
                                    detail_resp = requests.get(detail_url, timeout=20)
                                if detail_resp.ok:
                                    detail_payload = detail_resp.json()
                                    if isinstance(detail_payload, dict):
                                        if "session" in detail_payload and isinstance(detail_payload["session"], dict):
                                            sessions = [detail_payload["session"]]
                                        else:
                                            sessions = [detail_payload]
                            # Extract field candidates from sessions
                            st.session_state["brainstem_metadata"] = payload
                            st.session_state["brainstem_fields"] = extract_brainstem_values(sessions if sessions else payload)
                            if sessions:
                                st.success(f"Fetched {len(sessions)} session record(s) matching '{sid}'.")
                            else:
                                st.warning("No sessions matched the provided name/ID.")
                            with st.expander("Raw session payload (truncated)"):
                                try:
                                    st.code(json.dumps(payload, indent=2)[:4000])
                                except Exception:
                                    st.write(payload)
                            mapped = st.session_state.get("brainstem_fields", {})
                            if mapped:
                                st.caption("Extracted/mapped candidate field values:")
                                st.json(mapped)
                        except Exception as e:
                            st.error(f"Failed to fetch brainSTEM metadata: {e}")

            # DANDI/NWB always included
            fields = collect_required_fields(experiment_types=exp_types, include_dandi=True, include_nwb=True)
            fields = _dedupe_fields(fields)
            
            # Use brainSTEM-aware field splitting if brainSTEM is enabled
            use_brainstem = st.session_state.get("use_brainstem", False)
            user_fields, auto_fields = split_user_vs_auto(fields, use_brainstem=use_brainstem)

            # If using brainSTEM, prefer auto-populating Subject and Session-related fields
            if st.session_state.get("use_brainstem"):
                try:
                    req = get_minimum_template_requirements(exp_types)
                except Exception:
                    req = {"core_any": [], "subject_all": set(), "subject_any_one_of": []}
                # Subject fields from validation rules + dynamic NWB Subject args
                subject_fields = set(req.get("subject_all", set()))
                for group in req.get("subject_any_one_of", []):
                    subject_fields.update(group)
                try:
                    subject_fields.update(get_nwb_subject_fields())
                except Exception:
                    pass
                # Session fields: core groups that look like session_* fields
                session_fields = set()
                for group in req.get("core_any", []):
                    group = set(group)
                    if any(str(name).startswith("session_") for name in group):
                        session_fields.update(group)
                # Also populate experimenter from project configuration if present
                project_derived = {"experimenter", "experimenters"}
                # Reassign to auto if present in fields
                must_auto = [
                    f for f in fields if (f in subject_fields) or (f in session_fields) or (f in project_derived)
                ]
                # Remove from user_fields and ensure in auto_fields, preserving order
                user_fields = [f for f in user_fields if f not in must_auto]
                # Keep existing order and append any missing
                auto_set = set(auto_fields)
                for f in must_auto:
                    if f not in auto_set:
                        auto_fields.append(f)
                        auto_set.add(f)

            # Ensure repository-required fields are auto-populated (not in the XLSX template)
            try:
                ds_for_repo = _load_dataset_yaml(_project_root())
            except Exception:
                ds_for_repo = {}
            repo_auto = set(_repo_expected_fields(ds_for_repo))
            if repo_auto:
                must_auto = [f for f in fields if f in repo_auto]
                user_fields = [f for f in user_fields if f not in must_auto]
                auto_set = set(auto_fields)
                for f in must_auto:
                    if f not in auto_set:
                        auto_fields.append(f)
                        auto_set.add(f)

            # If repository configured, move all Dataset-category fields to auto
            try:
                repo_cfg = (ds_for_repo or {}).get("repository", {})
            except Exception:
                repo_cfg = {}
            if isinstance(repo_cfg, dict) and repo_cfg.get("name"):
                dataset_fields = [f for f in fields if get_field_category(f) == "Dataset"]
                if dataset_fields:
                    user_fields = [f for f in user_fields if f not in dataset_fields]
                    auto_set = set(auto_fields)
                    for f in dataset_fields:
                        if f not in auto_set:
                            auto_fields.append(f)
                            auto_set.add(f)

            # Always treat known derived-from-data fields as auto-populated
            derived_auto = {
                "behavior_modality",
                "camera_count",
                "electrode_configuration",
                "ephys_acq_system",
                "event_timing_precision_ms",
                "frame_rate_fps",
                "num_channels",
                "probe_model",
                "reference_scheme",
                "sampling_rate_hz",
                "stimulus_type",
                "sync_system",
                "task_protocol",
                "tracking_software",
            }
            must_auto = [f for f in fields if f in derived_auto]
            if must_auto:
                user_fields = [f for f in user_fields if f not in must_auto]
                auto_set = set(auto_fields)
                for f in must_auto:
                    if f not in auto_set:
                        auto_fields.append(f)
                        auto_set.add(f)

            st.subheader("Metadata fields preview")
            desc_map = get_field_descriptions()
            brainstem_vals = st.session_state.get("brainstem_fields", {})

            def build_field_df(fields: List[str], show_values: bool = False) -> pd.DataFrame:
                rows = []
                for f in fields:
                    row = {
                        "Field": f,
                        "Category": get_field_category(f),
                        "Description": desc_map.get(f, ""),
                    }
                    if show_values:
                        row["Value"] = brainstem_vals.get(f, "")
                    rows.append(row)
                # Ensure we always have expected columns even if no rows
                base_cols = ["Field", "Category", "Description"] + (["Value"] if show_values else [])
                df = pd.DataFrame(rows, columns=base_cols)
                if df.empty:
                    return df
                # Priority order: Dataset, Subject, Session, Experiment, then others alphabetically
                priority = {"Dataset": 0, "Subject": 1, "Session": 2, "Experiment": 3}
                df["CatRank"] = df["Category"].map(priority).fillna(9_999).astype(int)
                df = df.sort_values(["CatRank", "Category", "Field"]).drop(columns=["CatRank"]).reset_index(drop=True)
                return df

            color_map = {
                "Subject": "#e6f7ff",
                "Session": "#fff5e6",
                "Experiment": "#e6ffe6",
                "Institution": "#f9e6ff",
                "Dataset": "#ffe6e6",
                "Other": "#f0f0f0",
            }

            def style_df(df: pd.DataFrame) -> Any:
                def _color_row(row):
                    color = color_map.get(row["Category"], "#ffffff")
                    return [f"background-color: {color}"] * len(row)

                return df.style.apply(_color_row, axis=1)

            c1, c2 = st.columns(2)
            with c1:
                st.caption("User-provided fields")
                uf_df = build_field_df(user_fields)
                uf_edit = st.data_editor(
                    style_df(uf_df),
                    hide_index=True,
                    column_config={
                        "Field": st.column_config.TextColumn("Field", width="large"),
                        "Category": st.column_config.TextColumn("Category", disabled=True, width="small"),
                        "Description": st.column_config.TextColumn("Description", disabled=True, width="large"),
                    },
                    width="stretch",
                )
                try:
                    user_fields = uf_edit["Field"].tolist()
                except Exception:
                    user_fields = uf_df["Field"].tolist()
            with c2:
                st.caption("Auto-populated fields")
                if st.session_state.get("use_brainstem"):
                    st.caption(
                        "ℹ️ Subject/session metadata will be fetched from brainSTEM. Dataset fields from project configuration."
                    )
                else:
                    st.caption(
                        "ℹ️ These fields can be auto-filled from file names, project configuration, or timestamps."
                    )
                af_df = build_field_df(auto_fields, show_values=bool(brainstem_vals))
                af_col_cfg = {
                    "Field": st.column_config.TextColumn("Field", width="large"),
                    "Category": st.column_config.TextColumn("Category", disabled=True, width="small"),
                    "Description": st.column_config.TextColumn("Description", disabled=True, width="large"),
                }
                if "Value" in af_df.columns:
                    af_col_cfg["Value"] = st.column_config.TextColumn("Value", disabled=True, width="large")
                af_edit = st.data_editor(
                    style_df(af_df),
                    hide_index=True,
                    column_config=af_col_cfg,
                    width="stretch",
                )
                try:
                    auto_fields = af_edit["Field"].tolist()
                except Exception:
                    auto_fields = af_df["Field"].tolist()

            # Accurate session counting using level_configs (recording level depth) if present in dataset.yaml
            dataset_dir = st.text_input(
                "Dataset root directory (for session counting)",
                value=_project_root(),
                placeholder="Root folder containing subject/session hierarchy",
            )
            n_rows = 1
            if dataset_dir and os.path.isdir(dataset_dir):
                try:
                    ds_cfg_for_count = _load_dataset_yaml(_project_root())
                    level_cfgs = []
                    rec_depth = None
                    if isinstance(ds_cfg_for_count, dict):
                        level_cfgs = ds_cfg_for_count.get("level_configs", []) or []
                        try:
                            rec_depth = int(ds_cfg_for_count.get("recording_level_depth")) if ds_cfg_for_count.get("recording_level_depth") is not None else None
                        except Exception:
                            rec_depth = None
                    if level_cfgs:
                        discovered = _discover_sessions_by_levels(dataset_dir, level_cfgs, rec_depth)
                        n_rows = max(1, len(discovered))
                        st.info(f"Detected {n_rows} recording session folder(s) via configured hierarchy.")
                    else:
                        # Fallback: simple immediate subdirectory count
                        n_rows = sum(1 for e in os.scandir(dataset_dir) if e.is_dir()) or 1
                        st.info(f"Detected {n_rows} top-level session folder(s) (no level configuration found).")
                except Exception as e:
                    st.warning(f"Could not count session folders ({e}); defaulting to 1 row.")
            else:
                st.caption("Provide the dataset root to count session folders automatically.")

            final_fields = user_fields + [f for f in auto_fields if f not in user_fields]

            # Help for DANDI-required fields that are obscure
            try:
                dandi_required = set(get_dandi_required_fields())
            except Exception:
                dandi_required = set()
            obscure = [
                "assetsSummary",
                "citation",
                "contributor",
                "id",
                "license",
                "manifestLocation",
                "name",
                "version",
            ]
            present_obscure_required = [f for f in obscure if f in dandi_required and f in final_fields]
            if present_obscure_required:
                with st.expander("About some required DANDI fields"):
                    st.caption("These are part of the DANDI metadata model. Many are auto-managed by DANDI on publish; include only what you reasonably know.")
                    help_map = {
                        # Legacy obscure fields (should rarely appear now due to filtering)
                        "assetsSummary": "Auto-generated summary of assets in the dandiset (counts/sizes). Usually managed by DANDI.",
                        "citation": "Recommended citation text for the dandiset.",
                        "contributor": "People/organizations who contributed; typically a list with name, role, and identifiers.",
                        "id": "DANDI identifier (e.g., DANDI:000123). Often assigned by DANDI.",
                        "license": "License under which the data are shared (e.g., CC-BY-4.0).",
                        "manifestLocation": "Location(s) of the manifest used by DANDI. Usually auto-managed.",
                        "name": "Title of the dandiset (project name).",
                        "version": "Dandiset version (e.g., draft or 0.230915). Managed by DANDI.",
                        # New descriptive field names
                        "dataset_name": "Name/title of your dataset (auto-populated from project name).",
                        "dataset_description": "Description of your dataset (auto-populated from project description).", 
                        "contributor_name": "Name of the principal investigator or main contributor.",
                        "contributor_role": "Role of the contributor (e.g., 'ContactPerson', 'Creator', 'Researcher').",
                        "keywords": "Research keywords describing your study (e.g., 'electrophysiology', 'behavior', 'mouse').",
                        "protocol": "Description of experimental protocols used.",
                    }
                    for f in present_obscure_required:
                        st.write(f"- {f}: {help_map.get(f, '')}")

            # Minimal completeness check for NWB mapping
            chk = check_template_columns(final_fields, exp_types)
            if chk.get("ok"):
                st.success("Minimum template fields present for NWB mapping.")
            else:
                st.warning("Missing required fields:")
                if chk.get("missing_core"):
                    st.write("- Core NWBFile: missing " + ", ".join(chk["missing_core"]))
                if chk.get("missing_subject"):
                    st.write("- Subject: missing " + ", ".join(chk["missing_subject"]))
                miss_mod = chk.get("missing_by_modality", {})
                for mod, missing in miss_mod.items():
                    st.write(f"- {mod}: missing " + ", ".join(missing))

            st.subheader("Download a template session metadata spreadsheet")
            st.caption("Generate a blank template XLSX or CSV file with all required fields as column headers. Edit as needed. Fields in the 'Auto-populated' list above will be filled automatically (when possible) by the conversion script, either from your project configuration, from brainSTEM.org metadata (if enabled), or from the data files themselves.")
            bytes_xlsx = None
            bytes_csv = None
            try:
                bytes_xlsx = build_workbook_bytes(columns=final_fields, n_rows=int(n_rows))
            except Exception as e:
                st.warning("Could not build .xlsx; falling back to CSV.")
                st.debug(str(e)) if hasattr(st, "debug") else None
            try:
                bytes_csv = build_csv_bytes(columns=final_fields, n_rows=int(n_rows))
            except Exception as e:
                st.error(f"Failed to build CSV template: {e}")
                st.stop()

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            ds_for_name = _load_dataset_yaml(_project_root())
            _pn = _sanitize_name(ds_for_name.get("project_name", "project")) if isinstance(ds_for_name, dict) else "project"
            _ex = _sanitize_name(ds_for_name.get("experimenter", "user")) if isinstance(ds_for_name, dict) else "user"
            base_name = f"{_pn}__{_ex}__template"
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Save .xlsx to project root", key="save_xlsx_to_root", disabled=(bytes_xlsx is None)):
                    try:
                        root = _project_root()
                        out_path = os.path.join(root, f"{base_name}_{timestamp}.xlsx")
                        with open(out_path, "wb") as f:
                            f.write(bytes_xlsx.getvalue())  # type: ignore[arg-type]
                        st.success(f"Saved to {out_path}")
                        st.session_state["last_saved_template_path"] = out_path
                    except Exception as e:
                        st.error(f"Failed to save .xlsx: {e}")
            with c2:
                if st.button("Save .csv to project root", key="save_csv_to_root", disabled=(bytes_csv is None)):
                    try:
                        root = _project_root()
                        out_path = os.path.join(root, f"{base_name}_{timestamp}.csv")
                        with open(out_path, "wb") as f:
                            f.write(bytes_csv.getvalue())  # type: ignore[arg-type]
                        st.success(f"Saved to {out_path}")
                        st.session_state["last_saved_template_path"] = out_path
                    except Exception as e:
                        st.error(f"Failed to save .csv: {e}")
            with c3:
                if st.button("Open project folder", key="open_folder_new_any"):
                    target = st.session_state.get("last_saved_template_path")
                    if isinstance(target, str) and os.path.isfile(target):
                        _open_in_file_manager(target, select=True)
                    else:
                        _open_in_file_manager(_project_root())

        with tab_load:
            tmpl_paths = sorted(glob.glob("templates/*.xlsx"))
            if not tmpl_paths:
                st.warning("No templates found in ./templates.")
                return
            labels = [os.path.basename(p) for p in tmpl_paths]
            choice = st.selectbox("Select a template file", options=labels, index=None, placeholder="Choose…")
            if not choice:
                return
            path = tmpl_paths[labels.index(choice)]
            try:
                df = pd.read_excel(path, sheet_name=0, nrows=0)
                columns = _dedupe_fields(list(df.columns))
            except Exception as e:
                st.error(f"Failed to read columns from template: {e}")
                return

            st.subheader("Columns Preview (editable)")
            # Use brainSTEM-aware field splitting if brainSTEM is enabled  
            use_brainstem = st.session_state.get("use_brainstem", False)
            user_fields, auto_fields = split_user_vs_auto(columns, use_brainstem=use_brainstem)
            # Move repository-required fields to auto
            try:
                ds_for_repo = _load_dataset_yaml(_project_root())
            except Exception:
                ds_for_repo = {}
            repo_auto = set(_repo_expected_fields(ds_for_repo))
            if repo_auto:
                must_auto = [f for f in columns if f in repo_auto]
                user_fields = [f for f in user_fields if f not in must_auto]
                auto_set = set(auto_fields)
                for f in must_auto:
                    if f not in auto_set:
                        auto_fields.append(f)
                        auto_set.add(f)
            # If repository configured, move all Dataset-category fields to auto
            if isinstance(ds_for_repo, dict) and isinstance(ds_for_repo.get("repository"), dict) and ds_for_repo["repository"].get("name"):
                dataset_fields = [c for c in columns if get_field_category(c) == "Dataset"]
                if dataset_fields:
                    user_fields = [f for f in user_fields if f not in dataset_fields]
                    auto_set = set(auto_fields)
                    for f in dataset_fields:
                        if f not in auto_set:
                            auto_fields.append(f)
                            auto_set.add(f)
            # Always treat known derived-from-data fields as auto-populated
            derived_auto = {
                "behavior_modality",
                "camera_count",
                "electrode_configuration",
                "ephys_acq_system",
                "event_timing_precision_ms",
                "frame_rate_fps",
                "num_channels",
                "probe_model",
                "reference_scheme",
                "sampling_rate_hz",
                "stimulus_type",
                "sync_system",
                "task_protocol",
                "tracking_software",
            }
            must_auto = [f for f in columns if f in derived_auto]
            if must_auto:
                user_fields = [f for f in user_fields if f not in must_auto]
                auto_set = set(auto_fields)
                for f in must_auto:
                    if f not in auto_set:
                        auto_fields.append(f)
                        auto_set.add(f)
            c1, c2 = st.columns(2)
            with c1:
                st.caption("User-provided fields")
                uf_df = pd.DataFrame({"Column": user_fields})
                uf_edit = st.data_editor(uf_df, hide_index=True)
                try:
                    user_fields = uf_edit["Column"].tolist()
                except Exception:
                    user_fields = uf_df["Column"].tolist()
            with c2:
                st.caption("Auto-populated fields")
                if use_brainstem:
                    st.caption("ℹ️ Subject/session metadata will be fetched from brainSTEM. Dataset fields from project configuration.")
                else:
                    st.caption("ℹ️ These fields can be auto-filled from file names, project configuration, or timestamps.")
                af_df = pd.DataFrame({"Column": auto_fields})
                af_edit = st.data_editor(af_df, hide_index=True)
                try:
                    auto_fields = af_edit["Column"].tolist()
                except Exception:
                    auto_fields = af_df["Column"].tolist()

            dataset_dir = st.text_input(
                "Dataset directory (to count sessions)",
                value=_project_root(),
                placeholder="Folder with one subfolder per session",
            )
            n_rows = 1
            if dataset_dir and os.path.isdir(dataset_dir):
                try:
                    n_rows = sum(1 for e in os.scandir(dataset_dir) if e.is_dir()) or 1
                    st.info(f"Detected {n_rows} session folders in selected directory.")
                except Exception:
                    st.warning("Could not count subdirectories; defaulting to 1 row.")
            else:
                st.caption("Provide a dataset directory to set the number of rows automatically.")

            final_fields = user_fields + [f for f in auto_fields if f not in user_fields]

            st.subheader("Download Template")
            bytes_xlsx = None
            bytes_csv = None
            try:
                bytes_xlsx = build_workbook_bytes(columns=final_fields, n_rows=int(n_rows))
            except Exception as e:
                st.warning("Could not build .xlsx; falling back to CSV.")
                st.debug(str(e)) if hasattr(st, "debug") else None
            try:
                bytes_csv = build_csv_bytes(columns=final_fields, n_rows=int(n_rows))
            except Exception as e:
                st.error(f"Failed to build CSV template: {e}")
                st.stop()

            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            base_name = os.path.splitext(choice)[0]
            c1m, c2m, c3m = st.columns(3)
            with c1m:
                if st.button("Save modified .xlsx to project root", key="save_modified_xlsx_to_root", disabled=(bytes_xlsx is None)):
                    try:
                        root = _project_root()
                        out_path = os.path.join(root, f"{base_name}_modified_{timestamp}.xlsx")
                        with open(out_path, "wb") as f:
                            f.write(bytes_xlsx.getvalue())  # type: ignore[arg-type]
                        st.success(f"Saved to {out_path}")
                        st.session_state["last_saved_template_path"] = out_path
                    except Exception as e:
                        st.error(f"Failed to save .xlsx: {e}")
            with c2m:
                if st.button("Save modified .csv to project root", key="save_modified_csv_to_root", disabled=(bytes_csv is None)):
                    try:
                        root = _project_root()
                        out_path = os.path.join(root, f"{base_name}_modified_{timestamp}.csv")
                        with open(out_path, "wb") as f:
                            f.write(bytes_csv.getvalue())  # type: ignore[arg-type]
                        st.success(f"Saved to {out_path}")
                        st.session_state["last_saved_template_path"] = out_path
                    except Exception as e:
                        st.error(f"Failed to save .csv: {e}")
            with c3m:
                if st.button("Open project folder", key="open_folder_mod_any"):
                    target = st.session_state.get("last_saved_template_path")
                    if isinstance(target, str) and os.path.isfile(target):
                        _open_in_file_manager(target, select=True)
                    else:
                        _open_in_file_manager(_project_root())
        return

    if mode == "validate":
        st.header("NWB Validation")
        st.caption(
            "Upload an .nwb file or specify a local file path to run PyNWB validation and NWB Inspector checks."
        )

        # Remember last-used local path in session state
        local_key = "validate_local_path"
        default_local = st.session_state.get(local_key, "")
        local_path = st.text_input(
            "Path to .nwb file",
            value=default_local,
            placeholder="C:/path/to/file.nwb or /path/to/file.nwb",
        )
        # OS file dialog (local only)
        if st.button("Browse…", key="browse_local_nwb"):
            try:
                import tkinter as tk  # type: ignore
                from tkinter import filedialog  # type: ignore
                root = tk.Tk(); root.withdraw()
                sel = filedialog.askopenfilename(title="Select NWB file", filetypes=[("NWB files", "*.nwb"), ("All files", "*.*")])
                if sel:
                    st.session_state[local_key] = sel
                    local_path = sel
            except Exception as e:
                st.warning(f"Browse not available: {e}")
        config_upload = st.file_uploader("Optional: NWB Inspector config (YAML)", type=["yml", "yaml"], key="inspector_cfg")
        cfg_text: str | None = None
        if config_upload is not None:
            try:
                cfg_text = config_upload.getvalue().decode("utf-8", errors="ignore")
                st.caption("Inspector config loaded.")
            except Exception:
                st.warning("Could not read config; proceeding without it.")
        target_path: str | None = None
        tmp_path: str | None = None
        if local_path:
            if os.path.isfile(local_path):
                target_path = local_path
            else:
                st.warning("Local path does not exist or is not a file.")

        if target_path is not None:
            try:
                # Always run both checks
                st.write("Running PyNWB validation…")
                vres = run_pynwb_validation(target_path)
                if vres.get("status") == "missing":
                    st.warning("PyNWB not installed; skipping PyNWB validation.")
                elif vres.get("ok"):
                    st.success("PyNWB: No validation errors found.")
                else:
                    st.error(f"PyNWB: Found {vres.get('error_count', 0)} issues.")
                    if vres.get("errors"):
                        st.code("\n".join(vres["errors"])[:4000])

                st.write("Running NWB Inspector…")
                ires = run_nwb_inspector(target_path, config_text=cfg_text)
                if ires.get("status") == "missing":
                    detail = ires.get("detail", "")
                    py = ires.get("python", "")
                    msg = "nwbinspector not available in this Python environment."
                    if py:
                        msg += f" Using: {py}"
                    if detail:
                        msg += f" ({detail})"
                    st.warning(msg)
                else:
                    total = ires.get("count", 0)
                    by_sev = ires.get("by_severity", {})
                    st.info(
                        f"Inspector messages: {total} ("
                        + ", ".join(f"{k}: {v}" for k, v in by_sev.items())
                        + ")"
                    )
                    msgs = ires.get("messages", [])
                    if msgs:
                        st.dataframe(
                            [
                                {
                                    "severity": m.get("severity"),
                                    "check": m.get("check_name"),
                                    "location": m.get("location"),
                                    "message": m.get("message"),
                                }
                                for m in msgs[:500]
                            ]
                        )
            finally:
                if tmp_path is not None:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        else:
            st.info("Upload a file or provide a local path to start validation.")
        return

    if mode == "scripts":
        st.header("Create conversion scripts")
        st.caption("Generate NeuroConv-based conversion scripts using your project configuration.")

        root = _project_root()
        ds = _load_dataset_yaml(root)
        if not ds:
            st.warning("No dataset.yaml found. Create or edit your project definition first.")
            return

        st.write(f"Project: {ds.get('project_name','')} · Experimenter: {ds.get('experimenter','')}")
        st.write("Modalities:", ", ".join(ds.get("experimental_modalities", [])) or "(none)")

        ing_dir = _ingestion_dir(root)
        exists = os.path.isdir(ing_dir) and any(p.endswith(".py") for p in os.listdir(ing_dir))
        allow_overwrite = False
        if exists:
            st.warning(f"Existing scripts detected in {ing_dir}.")
            allow_overwrite = st.checkbox("Allow overwriting existing scripts", value=False)

        script_name = _compose_script_name(
            ds.get("project_name", "project"),
            ds.get("experimenter", "user"),
            ds.get("experimental_modalities", []),
        )
        st.text_input("Script filename", value=script_name, key="script_filename")

        if st.button("Generate script", type="primary"):
            try:
                _ensure_dir(ing_dir)
                out_path = os.path.join(ing_dir, st.session_state.get("script_filename", script_name))
                if os.path.exists(out_path) and not allow_overwrite:
                    st.error("File exists. Enable overwrite to proceed.")
                else:
                    text = _generate_conversion_script_text(ds)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(text)
                    st.success(f"Saved script to {out_path}")
                    st.caption("You may edit the script to point to your actual data locations and interfaces.")
            except Exception as e:
                st.error(f"Failed to write script: {e}")
        return

    if mode == "runs":
        import glob
        import pandas as pd

        st.header("Conversion runs")
        st.caption("Track, run, and manage conversions for the current project.")
        root = _project_root()
        ing_dir = _ingestion_dir(root)
        _ensure_dir(ing_dir)

        # --- Session file (template/registry) handling ---
        ds_cfg = _load_dataset_yaml(root)
        persisted_template = ds_cfg.get("session_registry_template") if isinstance(ds_cfg, dict) else None

        def _detect_latest_template(r: str) -> str | None:
            candidates: List[str] = []
            for ext in ("csv", "xlsx", "xls"):
                candidates.extend(glob.glob(os.path.join(r, f"*recordings*.{ext}")))
            if not candidates:
                return None
            candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return candidates[0]

        latest_auto = _detect_latest_template(root)
        # Build dropdown list: persisted + any xlsx/csv in root
        root_files = [p for p in glob.glob(os.path.join(root, "*.xlsx")) + glob.glob(os.path.join(root, "*.csv"))]
        # Deduplicate while preserving order
        seen: Set[str] = set()
        session_file_options: List[str] = []
        for p in ([persisted_template] if persisted_template else []) + [latest_auto] + sorted(root_files):
            if p and os.path.exists(p) and p not in seen:
                session_file_options.append(p)
                seen.add(p)

        # Determine default selection logic
        default_session_file = None
        if persisted_template and os.path.exists(persisted_template):
            default_session_file = persisted_template
        elif latest_auto and os.path.exists(latest_auto):
            default_session_file = latest_auto

        # Persist selection in session state
        sel_key = "session_file_path"
        if sel_key not in st.session_state:
            st.session_state[sel_key] = default_session_file or ""

        # st.subheader("Run a conversion")
        sf_col1, sf_col2 = st.columns([3,2])
        with sf_col1:
            picked_session_file = st.selectbox(
                "Session metadata spreadsheet",
                options=session_file_options or ["(none detected)"] ,
                index=(session_file_options.index(st.session_state[sel_key]) if (st.session_state.get(sel_key) in session_file_options) else 0) if session_file_options else None,
            ) if session_file_options else None
            if picked_session_file and picked_session_file != st.session_state.get(sel_key):
                st.session_state[sel_key] = picked_session_file
        with sf_col2:
            custom_path = st.text_input("Custom path", value=st.session_state.get(sel_key, "") or "", placeholder="/path/to/recordings.xlsx or .csv")
            if custom_path and custom_path != st.session_state.get(sel_key):
                st.session_state[sel_key] = custom_path
        effective_session_file = st.session_state.get(sel_key, "")

        # Validate existence; auto-fallback to latest_auto if needed
        if effective_session_file and not os.path.exists(effective_session_file):
            st.warning("Selected session file not found on disk – attempting fallback to most recent auto-detected file.")
            if latest_auto and os.path.exists(latest_auto):
                effective_session_file = latest_auto
                st.session_state[sel_key] = latest_auto
                st.info(f"Fell back to latest detected file: {os.path.basename(latest_auto)}")
            else:
                st.warning("No session file available. Create one from the Data description page.")
                effective_session_file = ""

        # Persist chosen file into dataset.yaml when changed
        if isinstance(ds_cfg, dict):
            prev = ds_cfg.get("session_registry_template")
            if effective_session_file and effective_session_file != prev:
                try:
                    ds_cfg["session_registry_template"] = effective_session_file
                    with open(os.path.join(root, "dataset.yaml"), "w", encoding="utf-8") as f:
                        yaml.safe_dump(ds_cfg, f)
                    st.caption("Session file path saved to dataset.yaml")
                except Exception as e:
                    st.warning(f"Could not save session file path: {e}")

        # --- Build session list (directories + optional spreadsheet) ---
        df_tmpl = None
        if effective_session_file:
            try:
                df_tmpl = pd.read_csv(effective_session_file) if effective_session_file.endswith('.csv') else pd.read_excel(effective_session_file)
            except Exception:
                df_tmpl = None

        # Build session list from project-defined directory levels; fallback to spreadsheet if provided
        session_rows: List[Dict[str, Any]] = []
        level_cfgs = ds_cfg.get("level_configs") if isinstance(ds_cfg, dict) else None
        if isinstance(level_cfgs, list) and level_cfgs:
            # Discover via level config traversal (use recorded depth if present)
            rec_depth = None
            if isinstance(ds_cfg, dict):
                try:
                    rec_depth = int(ds_cfg.get("recording_level_depth")) if ds_cfg.get("recording_level_depth") is not None else None
                except Exception:
                    rec_depth = None
            session_rows = _discover_sessions_by_levels(root, level_cfgs, rec_depth)
        elif df_tmpl is not None and not df_tmpl.empty and "session_id" in df_tmpl.columns:
            for _, r in df_tmpl.iterrows():
                sid = str(r.get("session_id", "")).strip()
                if not sid:
                    continue
                sub = str(r.get("subject_id") or r.get("subject") or "").strip()
                session_rows.append({"session_id": sid, "subject_id": sub, "path": os.path.join(root, sid), "date": str(r.get('session_start_time', ''))})
        else:
            # Heuristic fallback: try depth=3 session discovery
            try:
                depth3 = _discover_sessions_by_levels(root, [{}, {}, {}])
            except Exception:
                depth3 = []
            if depth3:
                session_rows = depth3
            else:
                try:
                    for entry in os.scandir(root):
                        if entry.is_dir():
                            session_rows.append({"session_id": entry.name, "subject_id": "", "path": entry.path, "date": ""})
                except Exception:
                    pass

        # Script selection and session table (integrated)
        scripts = [p for p in sorted(os.listdir(ing_dir)) if p.endswith('.py')]
        if not scripts:
            st.info("No scripts in ingestion_scripts. Create one in 'Create conversion scripts'.")
        else:
            sel = st.selectbox("Script", scripts, index=0, key="run_script_sel")
            # Build run status table first and allow picking a row
            runs = _load_runs(root)
            run_map: Dict[str, List[Dict[str, Any]]] = {}
            for r in runs:
                sid = str(r.get("session_id", ""))
                run_map.setdefault(sid, []).append(r)
            rows_display: List[Dict[str, Any]] = []
            for row in session_rows:
                sid = str(row.get("session_id", ""))
                subj = row.get("subject_id", "")
                date = row.get("date", "")
                run_list = run_map.get(sid, [])
                last = run_list[-1] if run_list else None
                script_used = os.path.basename(last.get("script", "")) if last else ""
                ts = last.get("timestamp", "") if last else ""
                status = last.get("status", "") if last else ""
                out_path = last.get("output", "") if last else ""
                nwb_exists = bool(out_path) and os.path.exists(out_path)
                converted = bool(last) and status == "success" and nwb_exists
                rows_display.append({
                    "select": False,
                    "subject": subj,
                    "date": date,
                    "session_id": sid,
                    "converted": converted,
                    "script": script_used,
                    "run_time": ts,
                    "status": status,
                    "nwb_present": nwb_exists,
                    "path": row.get("path", ""),
                })
            if rows_display:
                df_runs = pd.DataFrame(rows_display)
                # Provide selection via checkbox column
                edited = st.data_editor(
                    df_runs,
                    hide_index=True,
                    column_config={
                        "select": st.column_config.CheckboxColumn("Use", help="Select exactly one session"),
                        "converted": st.column_config.CheckboxColumn("Converted", disabled=True),
                        "nwb_present": st.column_config.CheckboxColumn("NWB File", disabled=True),
                    },
                    disabled=["subject", "date", "session_id", "script", "run_time", "status", "nwb_present", "converted", "path"],
                    height=min(500, 40 + 28 * len(rows_display)),
                    key="runs_session_table",
                )
                # Determine selected row
                selected_rows = edited[edited["select"]] if "select" in edited else edited.iloc[0:0]
                if len(selected_rows) > 1:
                    st.warning("Multiple sessions selected; using the first.")
                picked_row = selected_rows.iloc[0] if len(selected_rows) >= 1 else None
            else:
                st.info("No sessions discovered. Ensure your directory structure or session file is set up.")
                picked_row = None

            session_id = str(picked_row.get("session_id", "")) if picked_row is not None else ""
            subject_id = str(picked_row.get("subject", "")) if picked_row is not None else ""
            selected_path = str(picked_row.get("path", "")) if picked_row is not None else ""

            # Defaults derived from selection
            default_source = selected_path or (os.path.join(root, session_id) if session_id else "")
            nwb_dir = os.path.join(root, "nwb_files")
            _ensure_dir(nwb_dir)
            base_name = "_".join([_sanitize_name(v) for v in (subject_id, session_id) if v]) or _sanitize_name(session_id)
            default_output = os.path.join(nwb_dir, f"{base_name}.nwb") if session_id else ""

            c1, c2 = st.columns(2)
            with c1:
                source = st.text_input("Source folder", value=default_source, placeholder="Path to session folder", key="run_source")
            with c2:
                output = st.text_input("Output NWB path", value=default_output, placeholder=os.path.join(nwb_dir, "<SUBJECT>_<SESSION>.nwb"), key="run_output")
                overwrite = st.checkbox("Overwrite output if exists", value=False, key="run_overwrite")
            if st.button("Run conversion", type="primary"):
                if not session_id:
                    st.error("Please select a session in the table (check 'Use').")
                elif not source or not output:
                    st.error("Provide source, output, and session ID.")
                else:
                    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
                    log_path = os.path.join(ing_dir, f"run_{ts}_{_sanitize_name(session_id)}.log")
                    script_path = os.path.join(ing_dir, sel)
                    st.info("Starting conversion; check the log for progress.")
                    code = _run_script_and_log(script_path, source, output, session_id, log_path, overwrite)
                    status = "success" if code == 0 else ("failed" if code > 0 else "error")
                    _append_run(root, {
                        "session_id": session_id,
                        "timestamp": ts,
                        "script": script_path,
                        "output": output,
                        "status": status,
                        "log": log_path,
                    })
                    if status == "success":
                        st.success("Conversion finished successfully.")
                    else:
                        st.error(f"Conversion {status}. See log.")

        return
        runs = _load_runs(root)
        if not runs:
            st.caption("No runs recorded yet.")
            return

        # Show runs table with actions
        for i, r in enumerate(reversed(runs)):
            idx = len(runs) - 1 - i
            with st.expander(f"{r.get('session_id','')} · {r.get('timestamp','')} · {r.get('status','')}"):
                st.write("Script:", r.get("script", ""))
                st.write("Log:", r.get("log", ""))
                # Log preview
                try:
                    if os.path.exists(r.get("log", "")):
                        with open(r["log"], "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        st.text_area("Log content", value=content[-8000:], height=200)
                except Exception:
                    pass
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Delete run", key=f"del_run_{idx}"):
                        _delete_run(root, idx)
                        st.experimental_rerun()
                with c2:
                    if os.path.exists(r.get("log", "")):
                        with open(r["log"], "r", encoding="utf-8", errors="ignore") as f:
                            log_bytes = f.read().encode("utf-8", errors="ignore")
                        st.download_button("Download log", data=log_bytes, file_name=os.path.basename(r["log"]))
        return

    if mode == "neurosift":
        st.header("Neurosift Viewer")
        st.caption("Open a local NWB file in the Neurosift app.")

        ns_key = "ns_local_path"
        default_path = st.session_state.get(ns_key, "")
        path = st.text_input("Path to local .nwb file", value=default_path, placeholder="/path/to/file.nwb")
        if st.button("Browse…", key="browse_neurosift"):
            try:
                import tkinter as tk  # type: ignore
                from tkinter import filedialog  # type: ignore
                root = tk.Tk(); root.withdraw()
                sel = filedialog.askopenfilename(title="Select NWB file", filetypes=[("NWB files", "*.nwb"), ("All files", "*.*")])
                if sel:
                    st.session_state[ns_key] = sel
                    path = sel
            except Exception as e:
                st.warning(f"Browse not available: {e}")

        if st.button("Open in Neurosift"):
            p = (path or "").strip()
            if not p:
                st.error("Provide a local .nwb file path.")
            elif not os.path.isfile(p):
                st.error("File not found. Check the path and try again.")
            else:
                st.session_state[ns_key] = p
                # Try a few invocation variants to avoid Windows symlink issues
                attempts = [
                    ["neurosift", "view-nwb", p],
                    ["neurosift", "view-nwb", "--no-symlink", p],
                ]
                last_err = None
                for cmd in attempts:
                    try:
                        st.caption("Command: " + " ".join(cmd))
                        res = subprocess.run(cmd, check=False, capture_output=True, text=True)
                        if res.returncode == 0:
                            st.success("Launched Neurosift. Check your desktop window.")
                            break
                        else:
                            last_err = res.stderr or res.stdout
                    except Exception as e:
                        last_err = str(e)
                        continue
                else:
                    hint = " If this is Windows, this may be due to symlink privilege. Try running a Terminal as Administrator or enable Developer Mode; alternatively, ensure your Neurosift version supports --no-symlink."
                    st.error("Failed to launch Neurosift." + (f" Details: {last_err}" if last_err else "") + hint)
        return

        # Troubleshooting tools
        st.subheader("Troubleshooting")
        if st.button("Test Neurosift CLI", key="test_neurosift_cli"):
            import shutil, sys
            ns_path = shutil.which("neurosift")
            st.write("neurosift on PATH:", ns_path or "(not found)")
            st.write("Python executable:", sys.executable)
            # Version
            try:
                resv = subprocess.run(["neurosift", "--version"], capture_output=True, text=True)
                st.write("--version rc=", resv.returncode)
                st.code((resv.stdout or resv.stderr)[:2000])
            except Exception as e:
                st.warning(f"Failed to run 'neurosift --version': {e}")
            # Help for view-nwb
            try:
                resh = subprocess.run(["neurosift", "view-nwb", "--help"], capture_output=True, text=True)
                st.write("view-nwb --help rc=", resh.returncode)
                st.code((resh.stdout or resh.stderr)[:4000])
                if "--no-symlink" in (resh.stdout or ""):
                    st.info("Detected support for --no-symlink.")
                else:
                    st.info("--no-symlink not detected in help output; your version may not support it.")
            except Exception as e:
                st.warning(f"Failed to run 'neurosift view-nwb --help': {e}")


if __name__ == "__main__":
    main()
