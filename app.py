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


st.set_page_config(page_title="U19 Dataset Manager", page_icon="📄", layout="wide")


def _set_mode(new_mode: str):
    st.session_state["mode"] = new_mode


SUBTYPES: Dict[str, List[str]] = {
    "Electrophysiology": ["Neuropixels", "Silicon probes", "Single electrode", "Tetrodes", "Patch-clamp"],
    "Behavior tracking": ["Video", "Analog measurement", "Other"],
    "Optogenetics": [],
    "Miniscope imaging": ["Miniscope V4", "UCLA Miniscope", "Other"],
    "Fiber photometry": ["Doric", "Other"],
    "2p imaging": ["Resonant", "Galvo", "Other"],
    "Widefield imaging": ["sCMOS", "Other"],
    "EEG recordings": [],
    "Notes": []
}

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

        # Experimental types and subtypes
        exp_types = st.multiselect(
            "Experimental types",
            options=get_supported_experiment_types(),
            default=[],
        )

        selected_subtypes: Dict[str, List[str]] = {}
        for et in exp_types:
            subtypes = st.multiselect(
                f"Subtypes – {et}", options=SUBTYPES.get(et, ["Other"]), default=[]
            )
            selected_subtypes[et] = subtypes

        st.subheader("Raw data formats")
        st.caption("Enter the data types and formats relevant to your project. Add/modify rows as needed.")
        if "data_formats_rows" not in st.session_state:
            st.session_state["data_formats_rows"] = _example_formats_df()
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
        if "data_org_tree" not in st.session_state:
            st.session_state["data_org_tree"] = (
                "Subject\n"
                "├── YYYY_MM_DD\n"
                "│   ├── SUBJECT_SESSION_ID\n"
                "│   │   ├── raw_ephys_data\n"
                "│   │   ├── raw_video_data\n"
                "│   │   ├── task_data\n"
                "│   │   └── processed_data\n"
            )
        tree_text = st.text_area("Tree editor", value=st.session_state["data_org_tree"], height=240, key="tree_editor")
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
