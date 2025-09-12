from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Set, Tuple

# Lightweight checks for template completeness (proxy fields -> NWB mappings)
# These checks operate on column names in the generated templates, not on NWB files.
# They complement runtime NWB validation by ensuring the spreadsheet will have the
# minimum metadata needed to construct NWB Devices, ElectrodeGroups, and ImageSeries.


def get_minimum_template_requirements(experiment_types: List[str]) -> Dict[str, Any]:
    """Return minimum template field requirements for NWB mapping.

    The returned dict contains:
    - core_any: list of alternative names that satisfy each core requirement
      (e.g., session_start_time can be either "session_start_time" or
      "session_start_time(YYYY-MM-DD HH:MM)")
    - subject_all: set of field names that should be present for Subject
    - subject_any_one_of: list of groups where at least one must be present
    - per_modality: dict modality -> {'required': set[str], 'optional': set[str]}

    Notes:
    - This function is heuristic and tuned for the U19 templates in schema.py.
      Adjust as your ingestion scripts evolve.
    """
    # Core NWBFile fields: allow either template label or canonical NWB label
    core_any: List[Set[str]] = [
        {"session_description"},
        {"identifier"},
        {"session_start_time", "session_start_time(YYYY-MM-DD HH:MM)"},
    ]

    # Subject: minimally require these, plus at least one of age or date_of_birth
    subject_all: Set[str] = {"subject_id", "species", "sex"}
    subject_any_one_of: List[Set[str]] = [{"age", "date_of_birth(YYYY-MM-DD)"}]

    # Per-modality minima (heuristics for constructing NWB objects)
    per_modality: Dict[str, Dict[str, Set[str]]] = {
        "Electrophysiology – Extracellular": {
            # Needed to create Device + ElectrodeGroup + infer channel table shape
            "required": {"ephys_acq_system", "sampling_rate_hz", "num_channels", "reference_scheme"},
            "optional": {"probe_model", "electrode_configuration"},
        },
        "Electrophysiology – Intracellular": {
            # Needed to create Device/ICEphys series with proper rates and identifiers
            "required": {"icephys_setup", "recording_mode", "sampling_rate_hz"},
            "optional": {"cell_id", "electrode_name"},
        },
        "Behavior and physiological measurements": {
            # Needed to represent Video/Audio/Analog series with correct timing
            "required": {"frame_rate_fps"},
            "optional": {"camera_count", "tracking_software", "behavior_modality"},
        },
        "Stimulations": {
            # Needed to define stimulation Device and basic parameters
            "required": {"opto_device_model", "stimulation_wavelength_nm"},
            "optional": {"stimulation_power_mw", "stimulation_protocol"},
        },
        "Optical Physiology": {
            # Needed to create Device/OpticalChannel and imaging series
            "required": {"ophys_device_model", "imaging_frame_rate_fps"},
            "optional": {
                "field_of_view_um",
                "imaging_indicator",
                "objective_magnification",
                "numerical_aperture",
                "excitation_wavelength_nm",
                "emission_wavelength_nm",
                "camera_model",
            },
        },
    }

    # Keep only modalities selected
    selected_modalities = {m: per_modality[m] for m in experiment_types if m in per_modality}

    return {
        "core_any": core_any,
        "subject_all": subject_all,
        "subject_any_one_of": subject_any_one_of,
        "per_modality": selected_modalities,
    }


def check_template_columns(columns: List[str], experiment_types: List[str]) -> Dict[str, Any]:
    """Check if a list of template column names meets minimum requirements.

    Returns a dict with:
    - ok: bool
    - missing_core: List[str] (human-readable requirement labels)
    - missing_subject: List[str]
    - missing_by_modality: Dict[modality, List[str]]
    - summary: str short description
    """
    req = get_minimum_template_requirements(experiment_types)
    cols_set = set(columns)

    # Core: at least one of each group in core_any must be present
    missing_core: List[str] = []
    for group in req["core_any"]:
        if not (group & cols_set):
            missing_core.append(" or ".join(sorted(group)))

    # Subject
    missing_subject: List[str] = [f for f in sorted(req["subject_all"]) if f not in cols_set]
    # at least one of each group
    for group in req["subject_any_one_of"]:
        if not (group & cols_set):
            missing_subject.append(" or ".join(sorted(group)))

    # Modalities
    missing_by_modality: Dict[str, List[str]] = {}
    for modality, parts in req["per_modality"].items():
        missing = [f for f in sorted(parts["required"]) if f not in cols_set]
        if missing:
            missing_by_modality[modality] = missing

    ok = not (missing_core or missing_subject or missing_by_modality)
    summary = (
        "All minimum template fields present"
        if ok
        else "Missing required fields for NWB mapping"
    )

    return {
        "ok": ok,
        "missing_core": missing_core,
        "missing_subject": missing_subject,
        "missing_by_modality": missing_by_modality,
        "summary": summary,
    }


def run_pynwb_validation(path: str) -> Dict[str, Any]:
    """Validate an NWB file using PyNWB's validator.

    Returns a dict with keys:
    - status: "ok" | "error" | "missing"
    - ok: bool (when available)
    - error_count: int
    - errors: List[str]
    """
    try:
        from pynwb import NWBHDF5IO  # type: ignore
        try:
            # new-style import available in recent PyNWB
            from pynwb.validate import validate as nwb_validate  # type: ignore
        except Exception:
            # very old fallback (unlikely)
            nwb_validate = None  # type: ignore

        with NWBHDF5IO(path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            errors: List[str] = []
            if nwb_validate is not None:
                try:
                    res = nwb_validate(nwbfile)
                    # res may be list/iterable of strings or ValidationErrors
                    if isinstance(res, list):
                        errors = [str(e) for e in res]
                    else:
                        try:
                            errors = [str(e) for e in list(res)]  # type: ignore
                        except Exception:
                            errors = [str(res)]  # best-effort
                except Exception as e:
                    # Best-effort: if validate fails, report exception as error
                    errors = [f"Validation raised: {e}"]
            else:
                # Minimal structural check: attempting to read file succeeded
                errors = []

        return {
            "status": "ok",
            "ok": len(errors) == 0,
            "error_count": len(errors),
            "errors": errors,
        }
    except ModuleNotFoundError:
        return {"status": "missing"}
    except Exception as e:
        return {
            "status": "error",
            "ok": False,
            "error_count": 1,
            "errors": [str(e)],
        }


def run_nwb_inspector(path: str, *, config_path: str | None = None, config_text: str | None = None) -> Dict[str, Any]:
    """Run NWB Inspector best-practice checks on a file.

    Returns a dict with keys:
    - status: "ok" | "missing" | "error"
    - count: int total messages
    - by_severity: dict severity->count
    - messages: list of simplified messages
    """
    try:
        # Try multiple entry points to handle version variance
        import importlib, sys  # type: ignore
        inspect_nwb = None  # type: ignore
        try:
            from nwbinspector import inspect_nwb as _insp  # type: ignore
            inspect_nwb = _insp
        except Exception:
            inspect_nwb = None  # type: ignore

        if inspect_nwb is None:
            # Probe a few possible module paths and symbol names
            candidates = [
                ("nwbinspector", "inspect_nwb"),
                ("nwbinspector.inspector", "inspect_nwb"),
                ("nwbinspector.nwbinspector", "inspect_nwb"),
                ("nwbinspector", "inspect_all"),
            ]
            for mod_name, attr in candidates:
                try:
                    mod = importlib.import_module(mod_name)
                    func = getattr(mod, attr, None)
                    if callable(func):
                        inspect_nwb = func  # type: ignore
                        break
                except Exception:
                    continue
            if inspect_nwb is None:
                return {
                    "status": "missing",
                    "detail": "Could not locate inspect_nwb in installed nwbinspector",
                    "python": sys.executable,
                }

        # Try to load a user-provided config if any
        inspector_config = None
        if config_text or config_path:
            try:
                # Prefer Inspector's own loader if available
                try:
                    # Some versions expose load_config from top-level; others under utils/config
                    try:
                        from nwbinspector import load_config  # type: ignore
                    except Exception:
                        try:
                            from nwbinspector.utils import load_config  # type: ignore
                        except Exception:
                            load_config = None  # type: ignore
                except Exception:
                    load_config = None  # type: ignore

                if config_text and load_config is not None:
                    inspector_config = load_config(config_text)  # type: ignore[arg-type]
                elif config_path and load_config is not None:
                    with open(config_path, "r", encoding="utf-8") as f:
                        inspector_config = load_config(f.read())  # type: ignore[arg-type]
                else:
                    # Fallback: parse YAML and pass dict directly
                    try:
                        import yaml  # type: ignore

                        if config_text is None and config_path is not None:
                            with open(config_path, "r", encoding="utf-8") as f:
                                config_text = f.read()
                        if config_text is not None:
                            inspector_config = yaml.safe_load(config_text)
                    except Exception:
                        inspector_config = None
            except Exception:
                inspector_config = None

        # Call inspector with or without config depending on support
        try:
            if inspector_config is not None:
                messages = inspect_nwb(path, config=inspector_config)  # type: ignore
            else:
                messages = inspect_nwb(path)  # type: ignore
        except TypeError:
            # Older versions may not support config kwarg
            messages = inspect_nwb(path)  # type: ignore

        simplified: List[Dict[str, Any]] = []
        sev_counter: Counter = Counter()

        for m in messages:
            # InspectorMessage has attributes; guard with getattr
            severity = getattr(m, "severity", None) or getattr(m, "importance", "INFO")
            check_name = getattr(m, "check_function_name", None) or getattr(m, "check_name", "")
            message = getattr(m, "message", "")
            location = getattr(m, "location", None) or \
                ".".join([
                    str(getattr(m, "object_type", "")),
                    str(getattr(m, "object_name", "")),
                ]).strip(".")

            sev_str = str(severity)
            sev_counter[sev_str] += 1
            simplified.append(
                {
                    "severity": sev_str,
                    "check_name": str(check_name),
                    "message": str(message),
                    "location": location,
                }
            )

        return {
            "status": "ok",
            "count": len(simplified),
            "by_severity": dict(sev_counter),
            "messages": simplified,
        }
    except ModuleNotFoundError as e:
        import sys
        return {"status": "missing", "detail": str(e), "python": sys.executable}
    except Exception as e:
        return {"status": "error", "error": str(e)}

