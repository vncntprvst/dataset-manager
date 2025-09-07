import io
import os
from datetime import datetime
from typing import List, Dict

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
)


st.set_page_config(page_title="U19 Spreadsheet Generator", page_icon="📄", layout="wide")


def _set_mode(new_mode: str):
    st.session_state["mode"] = new_mode


def _scan_tree(root: str, max_depth: int = 4) -> str:
    def _walk(path: str, prefix: str, depth: int) -> List[str]:
        if depth > max_depth:
            return []
        lines: List[str] = []
        try:
            entries = sorted([e for e in os.scandir(path)], key=lambda e: (not e.is_dir(), e.name.lower()))
        except Exception:
            return []
        for idx, e in enumerate(entries):
            connector = "└── " if idx == len(entries) - 1 else "├── "
            lines.append(prefix + connector + e.name)
            if e.is_dir():
                extension = "    " if idx == len(entries) - 1 else "│   "
                lines.extend(_walk(e.path, prefix + extension, depth + 1))
        return lines

    if not os.path.isdir(root):
        return ""
    lines = [os.path.basename(os.path.normpath(root))]
    lines.extend(_walk(root, "", 1))
    return "\n".join(lines)


SUBTYPES: Dict[str, List[str]] = {
    "Electrophysiology": ["Neuropixels", "Silicon probes", "Single electrode", "Tetrodes", "Patch-clamp"],
    "Behavior tracking": ["Video", "Analog measurement", "Other"],
    "Optogenetics": [],
    "Miniscope imaging": ["Miniscope V4", "UCLA Miniscope", "Other"],
    "Fiber photometry": ["Doric", "Other"],
    "2p imaging": ["Resonant", "Galvo", "Other"],
    "Widefield imaging": ["sCMOS", "Other"],
    "EEG recordings": [],
}


def _detect_formats(example_dirs: Dict[str, str]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    def has_any(path: str, exts: List[str]) -> bool:
        for root, _, files in os.walk(path):
            for f in files:
                for ext in exts:
                    if f.lower().endswith(ext):
                        return True
        return False

    # Ephys
    if example_dirs.get("Electrophysiology") and os.path.isdir(example_dirs["Electrophysiology"]):
        p = example_dirs["Electrophysiology"]
        formats = []
        if has_any(p, [".ns1", ".ns2", ".ns3", ".ns4", ".ns5", ".ns6", ".nsx", ".nev"]):
            formats.append("Blackrock .nsx/.nev")
        if has_any(p, [".ap.bin", ".lf.bin", ".meta"]):
            formats.append("Neuropixels .bin/.meta")
        if has_any(p, [".mat", ".npy", ".csv", ".dat"]):
            formats.append("Generic .mat/.npy/.csv/.dat")
        if formats:
            rows.append({"Data type": "Electrophysiology recordings", "Format": ", ".join(formats)})

    # Behavior
    if example_dirs.get("Behavior tracking") and os.path.isdir(example_dirs["Behavior tracking"]):
        p = example_dirs["Behavior tracking"]
        fmts = []
        if has_any(p, [".mp4", ".avi", ".mov"]):
            fmts.append("Video .mp4/.avi/.mov")
        if fmts:
            rows.append({"Data type": "Behavior videos", "Format": ", ".join(fmts)})

    # Task parameters
    any_dir = example_dirs.get("Electrophysiology") or example_dirs.get("Behavior tracking")
    if any_dir and os.path.isdir(any_dir):
        p = any_dir
        if has_any(p, [".csv", ".mat", ".dat"]):
            rows.append({"Data type": "Task parameters", "Format": ".csv, .mat, .dat"})

    # Optogenetics
    if example_dirs.get("Optogenetics") and os.path.isdir(example_dirs["Optogenetics"]):
        p = example_dirs["Optogenetics"]
        if has_any(p, [".csv", ".txt", ".json"]):
            rows.append({"Data type": "Optogenetic stimulation settings", "Format": ".csv, .txt, .json"})

    # Experimental metadata
    for p in example_dirs.values():
        if p and os.path.isdir(p) and (has_any(p, [".xlsx"]) or has_any(p, [".json"])):
            rows.append({"Data type": "Experimental metadata", "Format": ".xlsx, .json"})
            break

    return rows


def _list_drives() -> List[str]:
    drives: List[str] = []
    if os.name == "nt":
        import string
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            if os.path.exists(path):
                drives.append(path)
    else:
        drives.append("/")
    return drives


def folder_picker(label: str, key: str, start_dir: str | None = None) -> str:
    state_cwd_key = f"{key}__cwd"
    state_sel_key = f"{key}__sel"
    state_path_key = f"{key}__picked"

    if state_cwd_key not in st.session_state:
        st.session_state[state_cwd_key] = start_dir or (os.getcwd())

    cwd = st.session_state[state_cwd_key]
    if not os.path.isdir(cwd):
        cwd = os.getcwd()
        st.session_state[state_cwd_key] = cwd

    st.caption(label)
    cols = st.columns([2, 1, 1])
    with cols[0]:
        st.text_input("Current folder", value=cwd, key=f"{key}__path_show", disabled=True)
    with cols[1]:
        if st.button("Up", key=f"{key}__up"):
            parent = os.path.dirname(cwd.rstrip("/\\")) or cwd
            if parent and os.path.isdir(parent):
                st.session_state[state_cwd_key] = parent
                cwd = parent
    with cols[2]:
        # Quick jump to drive/root
        roots = _list_drives()
        if roots:
            root_choice = st.selectbox("Jump", options=roots, index=0, key=f"{key}__root")
            if st.button("Go", key=f"{key}__go_root"):
                if os.path.isdir(root_choice):
                    st.session_state[state_cwd_key] = root_choice
                    cwd = root_choice

    # Manual jump
    jcols = st.columns([3, 1])
    with jcols[0]:
        jump_to = st.text_input("Go to path", value=cwd, key=f"{key}__jump")
    with jcols[1]:
        if st.button("Open", key=f"{key}__open"):
            if os.path.isdir(jump_to):
                st.session_state[state_cwd_key] = jump_to
                cwd = jump_to

    try:
        entries = sorted([e for e in os.scandir(cwd) if e.is_dir()], key=lambda e: e.name.lower())
    except Exception:
        entries = []
    names = [e.name for e in entries]
    sel = st.selectbox("Subfolders", options=names, index=0 if names else None, key=state_sel_key)
    bcols = st.columns([1, 1])
    with bcols[0]:
        if st.button("Enter", key=f"{key}__enter") and sel:
            nxt = os.path.join(cwd, sel)
            if os.path.isdir(nxt):
                st.session_state[state_cwd_key] = nxt
                cwd = nxt
    picked = st.session_state.get(state_path_key, "")
    with bcols[1]:
        if st.button("Use this folder", key=f"{key}__use"):
            st.session_state[state_path_key] = cwd
            picked = cwd

    return picked


def main() -> None:
    st.title("Metadata bundler")
    st.caption("Generate, load, and validate templates; describe your project.")

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

        # Experimental types and subtypes with example directory
        exp_types = st.multiselect(
            "Experimental types",
            options=get_supported_experiment_types(),
            default=[],
        )

        example_dirs: Dict[str, str] = {}
        selected_subtypes: Dict[str, List[str]] = {}
        for et in exp_types:
            col1, col2 = st.columns([1, 2])
            with col1:
                subtypes = st.multiselect(
                    f"Subtypes – {et}", options=SUBTYPES.get(et, ["Other"]), default=[]
                )
                selected_subtypes[et] = subtypes
            with col2:
                example_dir = folder_picker(
                    f"Example data directory – {et}", key=f"exdir_{et.replace(' ', '_')}", start_dir=os.getcwd()
                )
            example_dirs[et] = example_dir

        st.subheader("Raw data formats")
        rows = _detect_formats(example_dirs)
        if rows:
            st.dataframe(rows, hide_index=True)
        else:
            st.info("Provide example directories above to detect raw formats.")

        st.subheader("Data organization")
        ex_session = folder_picker("Example session folder (for tree)", key="tree_example", start_dir=os.getcwd())
        if ex_session:
            tree_txt = _scan_tree(ex_session, max_depth=4)
            if tree_txt:
                st.code(tree_txt)
            else:
                st.warning("Could not read folder or it is empty.")
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
                user_fields = st.data_editor({"Column": user_fields}, hide_index=True)["Column"].tolist()
            with c2:
                st.caption("Auto-populated fields")
                auto_fields = st.data_editor({"Column": auto_fields}, hide_index=True)["Column"].tolist()

            dataset_dir = folder_picker("Dataset directory (to count sessions)", key="dataset_dir_create", start_dir=os.getcwd())
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
                user_fields = st.data_editor({"Column": user_fields}, hide_index=True)["Column"].tolist()
            with c2:
                st.caption("Auto-populated fields")
                auto_fields = st.data_editor({"Column": auto_fields}, hide_index=True)["Column"].tolist()

            dataset_dir = folder_picker("Dataset directory (to count sessions)", key="dataset_dir_load", start_dir=os.getcwd())
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
                ires = run_nwb_inspector(tmp_path)
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
