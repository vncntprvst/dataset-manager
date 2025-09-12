import io
import os
import re
import json
import subprocess
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


def _compose_script_name(project_name: str, experimenter: str, modalities: List[str]) -> str:
    mod = "__".join(_sanitize_name(m) for m in modalities) or "modalities"
    base = f"{_sanitize_name(project_name)}__{_sanitize_name(experimenter)}__{mod}.py"
    return base


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

    # Determine modality blocks to include
    include_ecephys = any(et.startswith("Electrophysiology – Extracellular") for et in exp_types)
    include_icephys = any(et.startswith("Electrophysiology – Intracellular") for et in exp_types)
    include_ophys = any(et == "Optical Physiology" for et in exp_types)
    include_behavior = any(et == "Behavior and physiological measurements" for et in exp_types)

    lines: List[str] = []
    lines.append("#!/usr/bin/env python")
    lines.append("# Auto-generated by Dataset Manager – NeuroConv-based conversion skeleton")
    lines.append("import os, argparse, datetime, json")
    lines.append("from typing import Dict, Any")
    lines.append("\n# NeuroConv imports (install: pip install neuroconv)")
    lines.append("from neuroconv import NWBConverter")
    if include_ecephys:
        lines.append("from neuroconv.datainterfaces import ecephys as ncv_ecephys")
    if include_icephys:
        lines.append("from neuroconv.datainterfaces import icephys as ncv_icephys")
    if include_ophys:
        lines.append("from neuroconv.datainterfaces import ophys as ncv_ophys")
    if include_behavior:
        lines.append("from neuroconv.datainterfaces import behavior as ncv_behavior")
    lines.append("")

    # Build converter class
    lines.append("class ProjectConverter(NWBConverter):")
    lines.append("    data_interface_classes = {}")

    # Add interface class references per modality
    if include_ecephys:
        labels = acq_types.get("Electrophysiology – Extracellular", []) or ["SpikeGLX"]
        for lab in labels:
            cls = ecephys_map.get(lab, None)
            if cls:
                lines.append(f"    data_interface_classes['ecephys__{_sanitize_name(lab)}'] = getattr(ncv_ecephys, '{cls}', None)")
            else:
                lines.append(f"    # TODO: map '{lab}' to a NeuroConv ecephys interface")
    if include_icephys:
        labels = acq_types.get("Electrophysiology – Intracellular", []) or ["Axon Instruments"]
        for lab in labels:
            cls = icephys_map.get(lab, None)
            if cls:
                lines.append(f"    data_interface_classes['icephys__{_sanitize_name(lab)}'] = getattr(ncv_icephys, '{cls}', None)")
            else:
                lines.append(f"    # TODO: map '{lab}' to a NeuroConv icephys interface")
    if include_ophys:
        labels = acq_types.get("Optical Physiology", []) or ["Tiff"]
        for lab in labels:
            cls = ophys_map.get(lab, None)
            if cls:
                lines.append(f"    data_interface_classes['ophys__{_sanitize_name(lab)}'] = getattr(ncv_ophys, '{cls}', None)")
            else:
                lines.append(f"    # TODO: map '{lab}' to a NeuroConv ophys interface")
    if include_behavior:
        # Leave as TODO since behavior inputs vary widely
        lines.append("    # TODO: add behavior interfaces (e.g., VideoInterface, AudioInterface) if applicable")

    lines.append("")
    lines.append(dedent(f"""
    def main():
        parser = argparse.ArgumentParser(description='Conversion script for {project} ({experimenter}).')
        parser.add_argument('--source', required=True, help='Path to source data root for this session')
        parser.add_argument('--output', required=True, help='Path to output .nwb file')
        parser.add_argument('--session-id', required=True, help='Session identifier')
        parser.add_argument('--overwrite', action='store_true', help='Overwrite existing output file')
        args = parser.parse_args()

        # Assemble source_data mapping for each interface; modify globs/paths as needed.
        source_data: Dict[str, Any] = {{}}

        # Example entries (uncomment and adjust):
        # source_data['ecephys__SpikeGLX'] = dict(folder_path=os.path.join(args.source, 'raw_ephys_data'))
        # source_data['ophys__Tiff'] = dict(file_paths=[...])

        converter = ProjectConverter(source_data=source_data)

        # Fetch and enrich metadata
        metadata = converter.get_metadata()
        metadata.setdefault('NWBFile', {{}})
        metadata['NWBFile'].update({{
            'session_description': 'Converted using NeuroConv',
            'session_id': args.session_id,
            'session_start_time': datetime.datetime.now().astimezone(),
            'identifier': f"{_sanitize_name(project)}__{{args.session_id}}",
            'experimenter': ['{experimenter}'],
            'institution': '{cfg.get('institution', '')}',
            'lab': '{cfg.get('lab', '')}',
        }})

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

    # Validate actual folders against the spec
    def _validate_folder_structure(spec_text: str, base_dir: str) -> Tuple[bool, List[str]]:
        import re as _re
        from datetime import datetime
        
        def _is_date_like(text: str) -> bool:
            """Check if a string looks like a date using multiple strategies."""
            # Strategy 1: Common date patterns (flexible regex)
            common_patterns = [
                r'^20\d{2}[_-]?\d{1,2}[_-]?\d{1,2}$',  # YYYY_MM_DD, YYYY-MM-DD, YYYYMMDD (2000-2099)
                r'^\d{1,2}[_-]?\d{1,2}[_-]?20\d{2}$',  # MM_DD_YYYY, DD_MM_YYYY, MMDDYYYY
                r'^\d{2}[_-]?\d{1,2}[_-]?\d{1,2}$',    # YY_MM_DD, YYMMDD
                r'^\d{8}$',                              # Generic 8-digit dates
                r'^\d{6}$',                              # Generic 6-digit dates (YYMMDD)
            ]
            
            for pattern in common_patterns:
                if _re.match(pattern, text):
                    return True
            
            # Strategy 2: Try parsing as date (more permissive)
            try:
                # Remove common separators for parsing attempts
                clean_text = text.replace('_', '').replace('-', '')
                
                # Try various date formats
                formats_to_try = [
                    '%Y%m%d',    # YYYYMMDD
                    '%y%m%d',    # YYMMDD
                    '%m%d%Y',    # MMDDYYYY
                    '%d%m%Y',    # DDMMYYYY
                ]
                
                for fmt in formats_to_try:
                    try:
                        datetime.strptime(clean_text, fmt)
                        return True
                    except ValueError:
                        continue
                        
                # Try with separators
                for sep in ['_', '-']:
                    if sep in text:
                        parts = text.split(sep)
                        if len(parts) == 3:
                            # Try to parse as YYYY-MM-DD or MM-DD-YYYY or DD-MM-YYYY
                            try:
                                if len(parts[0]) == 4:  # YYYY-MM-DD
                                    datetime(int(parts[0]), int(parts[1]), int(parts[2]))
                                    return True
                                elif len(parts[2]) == 4:  # MM-DD-YYYY or DD-MM-YYYY
                                    datetime(int(parts[2]), int(parts[0]), int(parts[1]))
                                    return True
                                    # Note: Ambiguity between MM-DD and DD-MM, but both are valid dates
                            except (ValueError, TypeError):
                                continue
            except Exception:
                pass
            
            return False
        
        def _extract_date_placeholders(spec_text: str) -> List[str]:
            """Extract date-like placeholders from the spec."""
            # Find all placeholders in angle brackets
            placeholders = _re.findall(r'<([^>]+)>', spec_text)
            date_placeholders = []
            
            for placeholder in placeholders:
                # Check if placeholder looks like a date format
                if any(date_part in placeholder.upper() for date_part in ['YYYY', 'YY', 'MM', 'DD', 'DATE']):
                    date_placeholders.append(f"<{placeholder}>")
            
            return date_placeholders
        
        def _matches_placeholder_pattern(folder_name: str, placeholder: str) -> bool:
            """Check if a folder name matches a specific placeholder pattern exactly."""
            if placeholder == "<SUBJECT_ID>":
                return True  # Any non-empty name is valid for subject
            elif placeholder == "<SESSION_ID>":
                return True  # Any non-empty name is valid for session
            elif placeholder.startswith("<YYYY") and placeholder.endswith(">"):
                # Extract the expected pattern from the placeholder
                pattern = placeholder.strip("<>")
                
                # Convert placeholder pattern to regex
                if pattern == "YYYY-MM-DD":
                    return bool(_re.match(r'^20\d{2}-\d{2}-\d{2}$', folder_name))
                elif pattern == "YYYY_MM_DD":
                    return bool(_re.match(r'^20\d{2}_\d{2}_\d{2}$', folder_name))
                elif pattern == "YYYYMMDD":
                    return bool(_re.match(r'^20\d{6}$', folder_name))
                elif pattern == "YYYY/MM/DD":
                    return bool(_re.match(r'^20\d{2}/\d{2}/\d{2}$', folder_name))
                # Add more specific patterns as needed
                else:
                    # Fall back to general date detection for unknown patterns
                    return _is_date_like(folder_name)
            else:
                # For other custom placeholders, just check if non-empty
                return len(folder_name.strip()) > 0
        raw_lines = [l.rstrip() for l in spec_text.splitlines() if l.strip()]
        def _content(line: str) -> str:
            return (
                line.replace("├──", "").replace("└──", "").replace("│", "").replace("─", "").strip()
            )
        contents = [_content(l) for l in raw_lines]
        
        # Parse the tree structure to understand the hierarchy
        tree_levels = []
        for content in contents:
            if content and content.startswith("<") and content.endswith(">"):
                tree_levels.append(content)
        
        has_subject = any("<SUBJECT_ID>" in level for level in tree_levels)
        has_session = any("<SESSION_ID>" in level for level in tree_levels)
        
        # Extract date placeholders and their expected positions
        used_date_placeholders = _extract_date_placeholders(spec_text)
        has_dates = len(used_date_placeholders) > 0
        expected_fmt = " or ".join(tok.strip("<>") for tok in used_date_placeholders) if used_date_placeholders else ""
        
        # Determine the expected structure based on tree levels
        if len(tree_levels) >= 2:
            first_level = tree_levels[0]  # Should be subject
            second_level = tree_levels[1] if len(tree_levels) > 1 else None
            third_level = tree_levels[2] if len(tree_levels) > 2 else None
            
            # Check if dates are in second level (separate date folders) or embedded in session names
            date_is_second_level = second_level and any(placeholder in second_level for placeholder in used_date_placeholders)
            date_embedded_in_session = third_level and "<SESSION_ID>" in third_level and any(placeholder in third_level for placeholder in used_date_placeholders)
        else:
            date_is_second_level = False
            date_embedded_in_session = False

        msgs: List[str] = []
        ok = True
        if not os.path.isdir(base_dir):
            return False, [f"Base directory does not exist: {base_dir}"]
        subjects = [e for e in os.scandir(base_dir) if e.is_dir()]
        if has_subject and not subjects:
            ok = False
            msgs.append("No subject folders found in base directory.")

        node_types = {
            "subject": "subject",
            "session_day": "session day",
            "recording_session": "recording session",
        }
        
        for subj in subjects:
            if has_dates and date_is_second_level:
                # Expect separate date folders under subject (structure: SUBJECT/DATE/SESSION)
                subfolders = [d for d in os.scandir(subj.path) if d.is_dir()]
                if not subfolders:
                    ok = False
                    msgs.append(f"{subj.name}: no date folders found (expected format: {expected_fmt}).")
                    continue
                    
                # Check each subfolder against expected date pattern
                invalid_dirs = []
                valid_date_dirs = []
                
                for subfolder in subfolders:
                    # Skip special files like subject.json, etc.
                    if subfolder.name.endswith('.json') or subfolder.name in ['brainstem_config.yaml', 'dataset.yaml', 'project.json']:
                        continue
                        
                    # Check if it matches any expected date placeholder
                    is_valid = False
                    for date_placeholder in used_date_placeholders:
                        if _matches_placeholder_pattern(subfolder.name, date_placeholder):
                            is_valid = True
                            valid_date_dirs.append(subfolder)
                            break
                    
                    if not is_valid:
                        invalid_dirs.append(subfolder.name)
                
                if invalid_dirs:
                    ok = False
                    msgs.append(f"{subj.name}: these folders don't match expected date format '{expected_fmt}': {', '.join(invalid_dirs)}")
                    
                # Check for session folders under valid date folders
                if has_session:
                    for date_dir in valid_date_dirs:
                        sess_dirs = [s for s in os.scandir(date_dir.path) if s.is_dir()]
                        if not sess_dirs:
                            ok = False
                            msgs.append(f"{subj.name}/{date_dir.name}: no session folders found (expected <SESSION_ID>).")
                            
            elif has_session and not date_is_second_level:
                # Sessions directly under subject (structure: SUBJECT/SESSION)
                sess_dirs = [s for s in os.scandir(subj.path) if s.is_dir()]
                if not sess_dirs:
                    ok = False
                    msgs.append(f"{subj.name}: no session folders found (expected <SESSION_ID>).")
                else:
                    # If dates are embedded in session names, validate that
                    if date_embedded_in_session:
                        invalid_sessions = []
                        for sess_dir in sess_dirs:
                            # Skip special files
                            if sess_dir.name.endswith('.json') or sess_dir.name in ['brainstem_config.yaml', 'dataset.yaml', 'project.json']:
                                continue
                                
                            # Check if session name contains expected date pattern
                            contains_valid_date = False
                            for date_placeholder in used_date_placeholders:
                                if _matches_placeholder_pattern(sess_dir.name, date_placeholder):
                                    contains_valid_date = True
                                    break
                            
                            if not contains_valid_date:
                                invalid_sessions.append(sess_dir.name)
                        
                        if invalid_sessions:
                            ok = False
                            msgs.append(f"{subj.name}: these session folders don't contain expected date format '{expected_fmt}': {', '.join(invalid_sessions)}")
            else:
                # No specific structure requirements
                pass

        if ok:
            msgs.append("Folder structure looks consistent with the spec.")
        return ok, msgs

    check_root = os.environ.get("DM_PROJECT_ROOT", os.getcwd())
    st.caption(f"Structure check base: {check_root}")
    if st.button("Check folder structure against spec", key=f"check_folder_{initial.get('_mode','')}"):
        ok, messages = _validate_folder_structure(tree_text, check_root)
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
        "project_root_dir": project_root_dir,
    }


def main() -> None:
    st.title("Dataset Manager for U19 Projects")
    st.caption("Describe your project and create scripts to package and publish your data.")

    # Sidebar: primary actions
    with st.sidebar:
        st.header("Actions")
        st.button("Project definition", use_container_width=True, on_click=_set_mode, args=("project",))
        st.button("Data description", use_container_width=True, on_click=_set_mode, args=("template",))
        st.button("NWB Validation", use_container_width=True, on_click=_set_mode, args=("validate",))
        st.button("Create conversion scripts", use_container_width=True, on_click=_set_mode, args=("scripts",))
        st.button("Conversion runs", use_container_width=True, on_click=_set_mode, args=("runs",))
        st.button("Neurosift Viewer", use_container_width=True, on_click=_set_mode, args=("neurosift",))
        st.divider()
        if st.button("Quit", type="secondary", use_container_width=True):
            os._exit(0)

    # Default to project page on first load
    mode = st.session_state.get("mode", "project")

    if mode == "project":
        st.header("Project definition")
        st.write("Describe your project organization and data formats.")

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
                        with open(dataset_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(data, f)
                        st.success(f"Updated {dataset_path}")
            else:
                st.info(f"No dataset.yaml found in {edit_root}.")
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
            st.subheader("Experimental modalities")
            st.write(", ".join(exp_types) if exp_types else "(none)")
            if not ds:
                st.info("No dataset.yaml found in the project root. Define modalities on the Project page.")
                if st.button("Open Project page", key="go_project_from_template"):
                    _set_mode("project")
                    st.experimental_rerun()

            # Optional: fetch metadata from brainSTEM.org
            st.checkbox("Fetch notes/metadata from brainSTEM.org", value=False, key="use_brainstem")
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
                if not api_key:
                    st.info("No brainSTEM API key configured. Provide and save it below.")
                    api_key_in = st.text_input("brainSTEM API key", type="password")
                    if st.button("Save brainSTEM config"):
                        try:
                            with open(cfg_path, "w", encoding="utf-8") as f:
                                yaml.safe_dump({"api_key": api_key_in}, f)
                            st.success(f"Saved API key to {cfg_path}")
                            api_key = api_key_in
                        except Exception as e:
                            st.error(f"Failed to save config: {e}")
                subj_id = st.text_input("brainSTEM Subject/Record ID (optional)", value="")
                if api_key and st.button("Fetch metadata from brainSTEM"):
                    # Best-effort dynamic import; exact API may vary.
                    meta = {}
                    try:
                        try:
                            import brainstem_python_api_tools as bs  # type: ignore
                        except Exception:
                            bs = None  # type: ignore
                        if bs is not None and hasattr(bs, "Client"):
                            client = bs.Client(api_key=api_key)  # type: ignore
                            # Heuristic call; user may need to adapt to their account/data model
                            if subj_id:
                                meta = client.get_subject(subj_id)  # type: ignore
                            else:
                                meta = client.get_notes(limit=10)  # type: ignore
                        else:
                            # Fallback to plain HTTP; user may adjust endpoint
                            import requests  # type: ignore
                            headers = {"Authorization": f"Bearer {api_key}"}
                            base = "https://support.brainstem.org/api"
                            url = f"{base}/notes" if not subj_id else f"{base}/subjects/{subj_id}"
                            r = requests.get(url, headers=headers, timeout=20)
                            r.raise_for_status()
                            meta = r.json()
                        st.session_state["brainstem_metadata"] = meta
                        st.session_state["brainstem_fields"] = extract_brainstem_values(meta)
                        st.success("Fetched metadata from brainSTEM.")
                        st.caption("Preview of fetched fields (truncated):")
                        try:
                            st.code(json.dumps(meta, indent=2)[:2000])
                        except Exception:
                            st.write(meta)
                        mapped = st.session_state.get("brainstem_fields", {})
                        if mapped:
                            st.caption("Mapped field values:")
                            st.json(mapped)
                    except Exception as e:
                        st.error(f"Failed to fetch brainSTEM metadata: {e}")

            # DANDI/NWB always included
            fields = collect_required_fields(experiment_types=exp_types, include_dandi=True, include_nwb=True)
            
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

            st.subheader("Columns Preview")
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
                df = pd.DataFrame(rows)
                sort_cols = ["Category", "Field"]
                return df.sort_values(sort_cols).reset_index(drop=True)

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
                        "Field": st.column_config.TextColumn("Field"),
                        "Category": st.column_config.TextColumn("Category", disabled=True),
                        "Description": st.column_config.TextColumn("Description", disabled=True),
                    },
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
                    "Field": st.column_config.TextColumn("Field"),
                    "Category": st.column_config.TextColumn("Category", disabled=True),
                    "Description": st.column_config.TextColumn("Description", disabled=True),
                }
                if "Value" in af_df.columns:
                    af_col_cfg["Value"] = st.column_config.TextColumn("Value", disabled=True)
                af_edit = st.data_editor(
                    style_df(af_df),
                    hide_index=True,
                    column_config=af_col_cfg,
                )
                try:
                    auto_fields = af_edit["Field"].tolist()
                except Exception:
                    auto_fields = af_df["Field"].tolist()

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
            st.subheader("Template Completeness Check")
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
            base_name = "u19_spreadsheet_template"
            if bytes_xlsx is not None:
                st.download_button(
                    label="Download template (.xlsx)",
                    data=bytes_xlsx,
                    file_name=f"{base_name}_{timestamp}.xlsx",
                    mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                )
            if bytes_csv is not None:
                st.download_button(
                    label="Download template (.csv)",
                    data=bytes_csv,
                    file_name=f"{base_name}_{timestamp}.csv",
                    mime="text/csv",
                )

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
                columns = list(df.columns)
            except Exception as e:
                st.error(f"Failed to read columns from template: {e}")
                return

            st.subheader("Columns Preview (editable)")
            # Use brainSTEM-aware field splitting if brainSTEM is enabled  
            use_brainstem = st.session_state.get("use_brainstem", False)
            user_fields, auto_fields = split_user_vs_auto(columns, use_brainstem=use_brainstem)
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
            if bytes_xlsx is not None:
                st.download_button(
                    label="Download modified template (.xlsx)",
                    data=bytes_xlsx,
                    file_name=f"{base_name}_modified_{timestamp}.xlsx",
                    mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                )
            if bytes_csv is not None:
                st.download_button(
                    label="Download modified template (.csv)",
                    data=bytes_csv,
                    file_name=f"{base_name}_modified_{timestamp}.csv",
                    mime="text/csv",
                )
        return

    if mode == "validate":
        st.header("NWB Validation")
        st.caption(
            "Upload an .nwb file to run PyNWB validation and NWB Inspector best-practice checks."
        )

        uploaded = st.file_uploader("NWB file", type=["nwb"]) 
        config_upload = st.file_uploader("Optional: NWB Inspector config (YAML)", type=["yml", "yaml"], key="inspector_cfg")
        cfg_text: str | None = None
        if config_upload is not None:
            try:
                cfg_text = config_upload.getvalue().decode("utf-8", errors="ignore")
                st.caption("Inspector config loaded.")
            except Exception:
                st.warning("Could not read config; proceeding without it.")
        if uploaded is not None:
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".nwb") as tmp:
                tmp.write(uploaded.read())
                tmp_path = tmp.name

            try:
                # Always run both checks
                st.write("Running PyNWB validation…")
                vres = run_pynwb_validation(tmp_path)
                if vres.get("status") == "missing":
                    st.warning("PyNWB not installed; skipping PyNWB validation.")
                elif vres.get("ok"):
                    st.success("PyNWB: No validation errors found.")
                else:
                    st.error(f"PyNWB: Found {vres.get('error_count', 0)} issues.")
                    if vres.get("errors"):
                        st.code("\n".join(vres["errors"])[:4000])

                st.write("Running NWB Inspector…")
                ires = run_nwb_inspector(tmp_path, config_text=cfg_text)
                if ires.get("status") == "missing":
                    st.warning("nwbinspector not installed; skipping Inspector checks.")
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
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        else:
            st.info("Upload a .nwb file to start validation.")
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
        st.header("Conversion runs")
        st.caption("Track, run, and manage conversions for the current project.")
        root = _project_root()
        ing_dir = _ingestion_dir(root)
        _ensure_dir(ing_dir)

        # Launch a new conversion
        st.subheader("Run a conversion")
        scripts = [p for p in sorted(os.listdir(ing_dir)) if p.endswith('.py')]
        if not scripts:
            st.info("No scripts in ingestion_scripts. Create one in 'Create conversion scripts'.")
        else:
            sel = st.selectbox("Script", scripts, index=0)
            c1, c2 = st.columns(2)
            with c1:
                session_id = st.text_input("Session ID", value=datetime.now().strftime("%Y%m%d"))
                source = st.text_input("Source folder", value="", placeholder="Path to session folder")
            with c2:
                output = st.text_input("Output NWB path", value="", placeholder="/path/to/output.nwb")
                overwrite = st.checkbox("Overwrite output if exists", value=False)
            if st.button("Run conversion", type="primary"):
                if not source or not output or not session_id:
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
                        "status": status,
                        "log": log_path,
                    })
                    if status == "success":
                        st.success("Conversion finished successfully.")
                    else:
                        st.error(f"Conversion {status}. See log.")

        st.subheader("Previous runs")
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
        path = st.text_input("Path to local .nwb file", value="", placeholder="/path/to/file.nwb")
        uploaded = st.file_uploader("Or upload an NWB file to a temp path", type=["nwb"], key="ns_upl")
        tmp_path: str | None = None
        if uploaded is not None:
            import tempfile
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".nwb") as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = tmp.name
                st.info(f"Saved upload to {tmp_path}")
            except Exception as e:
                st.error(f"Failed to save uploaded file: {e}")
        target = tmp_path or path
        if st.button("Open in Neurosift"):
            if not target:
                st.error("Provide a path or upload an NWB file.")
            else:
                try:
                    # Launch neurosift as a detached process
                    subprocess.Popen(["neurosift", "view-nwb", target])
                    st.success("Launched Neurosift. Check your desktop window.")
                except Exception as e:
                    st.error(f"Failed to launch neurosift: {e}")
        return


if __name__ == "__main__":
    main()
