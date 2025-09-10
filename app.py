import io
import os
from datetime import datetime
from typing import List, Dict, Tuple, Set

import streamlit as st

from data_bundling_ui.schema import (
    get_supported_experiment_types,
    collect_required_fields,
    split_user_vs_auto,
)
from data_bundling_ui.export import build_workbook_bytes, build_csv_bytes
from data_bundling_ui.validation import (
    run_pynwb_validation,
    run_nwb_inspector,
    check_template_columns,
)


st.set_page_config(page_title="U19 Dataset Manager", page_icon="📄", layout="wide")


def _set_mode(new_mode: str):
    st.session_state["mode"] = new_mode


def _neuroconv_ecephys_acq_types() -> List[str]:
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


def _default_acq_types() -> Dict[str, List[str]]:
    return {
        "Electrophysiology – Extracellular": _neuroconv_ecephys_acq_types() or [
            "Blackrock",
            "SpikeGLX",
            "OpenEphys",
            "Intan",
            "Neuralynx",
            "Plexon",
            "TDT",
        ],
        "Electrophysiology – Intracellular": _intracellular_acq_types(),
        "Behavior tracking": ["Video", "Analog measurement", "Other"],
        "Optogenetics": ["Stimulation"],
        "Miniscope imaging": ["Miniscope V4", "UCLA Miniscope", "Other"],
        "Fiber photometry": ["Doric", "Other"],
        "2p imaging": ["Resonant", "Galvo", "Other"],
        "Widefield imaging": ["sCMOS", "Other"],
        "Experimental metadata": ["General"],
        "Notes": ["General"],
    }


def _suggest_raw_formats(exp_types: List[str], acq_map: Dict[str, List[str]]) -> List[Dict[str, str]]:
    """Build suggested Raw data formats rows based on selected experimental types and acquisition types."""
    suggestions: List[Dict[str, str]] = []

    # Enhanced format hints for extracellular vendors based on NeuroConv documentation
    # NOTE: Only raw recording formats, no processed/sorted data
    ecephys_formats = {
        "Blackrock": "Blackrock `.nsx`, `.ccf`, `.nev` files",
        "SpikeGLX": "SpikeGLX `.bin`, `.meta` files (Neuropixels)",
        "OpenEphys": "OpenEphys `.continuous`, `.events`, `.spikes` or `.dat`, `.oebin`",
        "Intan": "Intan `.rhd` / `.rhs` files",
        "Neuralynx": "Neuralynx `.ncs`, `.nev`, `.nse`, `.ntt` files", 
        "Plexon": "Plexon `.pl2` / `.plx` files",
        "TDT": "TDT tank files (`.tbk`, `.tev`, `.tsq`, `.sev`)",
        "EDF": "European Data Format `.edf` files",
        "White Matter": "White Matter binary `.bin` files",
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
        elif et == "Behavior tracking":
            for a in acqs or ["Video"]:
                if a.lower().startswith("video"):
                    suggestions.append({
                        "Data type": "Behavior videos",
                        "Format": "MP4/MPEG/AVI videos with timestamps",
                    })
                elif a.lower() == "analog measurement":
                    suggestions.append({
                        "Data type": "Behavior analog sensors",
                        "Format": "CSV/MAT/DAT time series data",
                    })
                else:
                    suggestions.append({
                        "Data type": f"Behavior tracking – {a}",
                        "Format": "Digital/analog behavioral data",
                    })
        elif et == "Optogenetics":
            suggestions.append({
                "Data type": "Optogenetic stimulation protocols",
                "Format": "Stimulation parameters in CSV/JSON/MAT files"
            })
            suggestions.append({
                "Data type": "Optogenetic device settings", 
                "Format": "Laser/LED parameters and timing files"
            })
        elif et == "Miniscope imaging":
            suggestions.append({
                "Data type": "Miniscope imaging", 
                "Format": "Raw `.avi`/`.mp4` videos with timestamp files"
            })
            suggestions.append({
                "Data type": "Miniscope metadata",
                "Format": "Camera settings and calibration files"
            })
        elif et == "Fiber photometry":
            suggestions.append({
                "Data type": "Fiber photometry signals", 
                "Format": "Time-series CSV/MAT with fluorescence data"
            })
            suggestions.append({
                "Data type": "Photometry hardware settings",
                "Format": "Excitation/emission wavelength parameters"
            })
        elif et == "2p imaging":
            suggestions.append({
                "Data type": "Two-photon imaging", 
                "Format": "TIFF stacks/HDF5 with acquisition metadata"
            })
            suggestions.append({
                "Data type": "2p microscope settings",
                "Format": "Laser power, objective, and timing parameters"
            })
        elif et == "Widefield imaging":
            suggestions.append({
                "Data type": "Widefield imaging", 
                "Format": "TIFF stacks/videos with illumination metadata"
            })
        elif et == "Experimental metadata":
            suggestions.append({
                "Data type": "Experimental protocols", 
                "Format": "Experimental design and procedure files"
            })
            suggestions.append({
                "Data type": "Session metadata", 
                "Format": "`SessionTable.xlsx`, `.json` metadata files"
            })
        elif et == "Notes":
            suggestions.append({
                "Data type": "Experimental notes", 
                "Format": "Markdown, text, or PDF documentation"
            })

    # Always include task parameters as a hint if ephys is selected
    if any(et.startswith("Electrophysiology") for et in exp_types):
        suggestions.append({
            "Data type": "Task/stimulus parameters",
            "Format": "TTL events, behavioral task files (`.csv`, `.mat`, `.json`)",
        })

    # Add common analysis outputs if multiple modalities selected
    if len(exp_types) > 1:
        suggestions.append({
            "Data type": "Cross-modal synchronization",
            "Format": "Timing/trigger files for multi-modal alignment",
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
    if len([et for et in exp_types if et.startswith("Electrophysiology")]) > 0 and \
       len([et for et in exp_types if "imaging" in et.lower()]) > 0:
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
    """Construct a folder tree with nodes based on selected experiment types and data formats."""
    children: List[str] = []

    has_video = any(
        (row.get("Data type", "") + " " + row.get("Format", "")).lower().find("video") >= 0
        for row in data_formats
    )

    if any(et.startswith("Electrophysiology") for et in exp_types):
        children.append("raw_ephys_data")
    if "Behavior tracking" in exp_types and has_video:
        children.append("raw_behavior_video")
    if "2p imaging" in exp_types:
        children.append("raw_imaging_2p")
    if "Miniscope imaging" in exp_types:
        children.append("raw_imaging_miniscope")
    if "Widefield imaging" in exp_types:
        children.append("raw_imaging_widefield")
    if "Fiber photometry" in exp_types:
        children.append("raw_photometry_data")
    if "Optogenetics" in exp_types:
        children.append("opto_stim_settings")
    if "Experimental metadata" in exp_types:
        children.append("metadata")
    if "Notes" in exp_types:
        children.append("notes")

    # Always include processed data placeholder
    children.extend(["processed_data"]) #"task_data",

    # Unique and stable order
    ordered: List[str] = []
    for name in [
        "raw_ephys_data",
        "raw_behavior_video",
        "raw_imaging_2p",
        "raw_imaging_miniscope",
        "raw_imaging_widefield",
        "raw_photometry_data",
        "opto_stim_settings",
        "metadata",
        "notes",
        "task_data",
        "processed_data",
    ]:
        if name in children and name not in ordered:
            ordered.append(name)

    tree = (
        "Subject\n"
        "├── YYYY_MM_DD\n"
        "│   ├── SUBJECT_SESSION_ID\n"
    )
    for i, c in enumerate(ordered):
        connector = "│   │   ├── " if i < len(ordered) - 1 else "│   │   └── "
        tree += connector + c + "\n"
    return tree

def _example_formats_df() -> List[Dict[str, str]]:
    return [
        {"Data type": "Electrophysiology recordings", "Format": "Blackrock `.nsx`,  `.ccf`, `.nev` files"},
        {"Data type": "Behavior videos", "Format": "MP4 recordings"},
        {"Data type": "Task parameters", "Format": "TTLs extracted from Blackrock files, `.csv`, `.mat`, `.dat` files"},
        {"Data type": "Optogenetic stimulation settings", "Format": "Text, `.csv` files"},
        {"Data type": "Experimental metadata", "Format": "`WallPassing_StatusTable.xlsx`, `.json` files"},
    ]


def main() -> None:
    st.title("Dataset Manager for U19 Projects")
    st.caption("Describe your project and create scripts to package and publish your data.")

    # Sidebar: primary actions
    with st.sidebar:
        st.header("Actions")
        st.button("Project description", use_container_width=True, on_click=_set_mode, args=("project",))
        st.button("Template management", use_container_width=True, on_click=_set_mode, args=("template",))
        st.button("NWB Validation", use_container_width=True, on_click=_set_mode, args=("validate",))
        st.divider()
        if st.button("Quit", type="secondary", use_container_width=True):
            os._exit(0)

    # Default to project page on first load
    mode = st.session_state.get("mode", "project")

    if mode == "project":
        st.header("Project description")
        st.write("Describe your project organization and data formats.")

        # Experimental types and acquisition types
        exp_types = st.multiselect(
            "Experimental types",
            options=get_supported_experiment_types(),
            default=[],
        )

        # Build acquisition type options per selected experiment type
        ACQ_OPTIONS = _default_acq_types()
        selected_acq: Dict[str, List[str]] = {}
        for et in exp_types:
            opts = ACQ_OPTIONS.get(et, ["Other"])
            acq = st.multiselect(
                f"Acquisition type – {et}", options=opts, default=[], key=f"acq_{et}"
            )
            selected_acq[et] = acq

        st.subheader("Raw data formats")
        st.caption("Enter the data types and formats relevant to your project. Add/modify rows as needed.")
        # Build dynamic suggestions based on current selection
        signature = (tuple(sorted(exp_types)), tuple((k, tuple(v)) for k, v in sorted(selected_acq.items())))
        last_sig = st.session_state.get("_formats_signature")
        if "data_formats_rows" not in st.session_state or signature != last_sig:
            st.session_state["data_formats_rows"] = _suggest_raw_formats(exp_types, selected_acq)
            st.session_state["_formats_signature"] = signature
        data_formats = st.data_editor(
            st.session_state["data_formats_rows"],
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "Data type": st.column_config.TextColumn(required=True),
                "Format": st.column_config.TextColumn(required=True),
            },
            key="data_formats_editor",
        )
        st.session_state["data_formats_rows"] = data_formats

        st.subheader("Data organization")
        st.caption("Define your folder structure and naming conventions. Edit the tree text below.")
        # Regenerate tree dynamically from current selections
        current_tree = _build_tree_text(exp_types, data_formats)
        tree_text = st.text_area("Tree editor", value=current_tree, height=240, key="tree_editor")
        st.session_state["data_org_tree"] = tree_text
        st.caption("Preview")
        st.code(tree_text)
        return

    if mode == "template":
        import glob
        import pandas as pd

        st.header("Template management")
        st.caption("Create a new template or load and edit an existing one.")

        tab_create, tab_load = st.tabs(["Create new", "Load existing"])

        with tab_create:
            exp_types = st.multiselect(
                "Experimental types",
                options=get_supported_experiment_types(),
                default=[],
            )

            # DANDI/NWB always included
            fields = collect_required_fields(experiment_types=exp_types, include_dandi=True, include_nwb=True)
            user_fields, auto_fields = split_user_vs_auto(fields)

            st.subheader("Columns Preview")
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
                af_df = pd.DataFrame({"Column": auto_fields})
                af_edit = st.data_editor(af_df, hide_index=True)
                try:
                    auto_fields = af_edit["Column"].tolist()
                except Exception:
                    auto_fields = af_df["Column"].tolist()

            dataset_dir = st.text_input("Dataset directory (to count sessions)", value="", placeholder="Folder with one subfolder per session")
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
            user_fields, auto_fields = split_user_vs_auto(columns)
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
                af_df = pd.DataFrame({"Column": auto_fields})
                af_edit = st.data_editor(af_df, hide_index=True)
                try:
                    auto_fields = af_edit["Column"].tolist()
                except Exception:
                    auto_fields = af_df["Column"].tolist()

            dataset_dir = st.text_input("Dataset directory (to count sessions)", value="", placeholder="Folder with one subfolder per session")
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


if __name__ == "__main__":
    main()
