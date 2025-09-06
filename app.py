import io
from datetime import datetime
from typing import List, Dict

import streamlit as st

from data_bundling_ui.schema import (
    get_supported_experiment_types,
    collect_required_fields,
)
from data_bundling_ui.export import build_workbook_bytes, build_csv_bytes
from data_bundling_ui.validation import (
    run_pynwb_validation,
    run_nwb_inspector,
)


st.set_page_config(page_title="U19 Spreadsheet Generator", page_icon="📄", layout="wide")


def main() -> None:
    st.title("U19 Spreadsheet Table Generator 📄")
    st.caption(
        "Define a spreadsheet template based on experimental types, DANDI metadata, and NWB core fields."
    )

    with st.sidebar:
        st.header("Configuration")
        exp_types = st.multiselect(
            "Experimental types",
            options=get_supported_experiment_types(),
            default=[],
            help="Select one or more experiment categories relevant to your dataset.",
        )

        include_dandi = st.checkbox(
            "Include DANDI core metadata fields",
            value=True,
            help="Derives required/important fields from the DANDI schema if available (falls back to curated list).",
        )
        include_nwb = st.checkbox(
            "Include NWB core fields",
            value=True,
            help="Includes minimally required NWBFile fields and common best-practice fields.",
        )

        n_rows = st.number_input(
            "Number of rows (sessions)", min_value=1, max_value=1000, value=5, step=1
        )

    # Build final field list
    fields = collect_required_fields(
        experiment_types=exp_types,
        include_dandi=include_dandi,
        include_nwb=include_nwb,
    )

    if not fields:
        st.info("Select at least one option to generate fields.")
        return

    st.subheader("Columns Preview")
    st.write(
        f"Total columns: {len(fields)} — duplicates are merged; order grouped by source."
    )

    # Show columns as a table for quick reference
    st.dataframe({"Column": fields})

    st.subheader("Download Template")
    st.caption("Choose format; .xlsx preferred if dependencies are installed.")

    bytes_xlsx = None
    bytes_csv = None

    # Try building xlsx; if dependencies missing, fall back to CSV only
    try:
        bytes_xlsx = build_workbook_bytes(columns=fields, n_rows=int(n_rows))
    except Exception as e:
        st.warning(
            "Could not build .xlsx (missing optional deps like pandas/openpyxl). Falling back to CSV."
        )
        st.debug(str(e)) if hasattr(st, "debug") else None

    try:
        bytes_csv = build_csv_bytes(columns=fields, n_rows=int(n_rows))
    except Exception as e:
        st.error("Failed to build CSV template.")
        st.stop()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = "u19_spreadsheet_template"

    cols_note = io.BytesIO("\n".join(fields).encode("utf-8"))
    st.download_button(
        label="Download column list (txt)",
        data=cols_note,
        file_name=f"{base_name}_columns_{timestamp}.txt",
        mime="text/plain",
    )

    if bytes_xlsx is not None:
        st.download_button(
            label="Download template (.xlsx)",
            data=bytes_xlsx,
            file_name=f"{base_name}_{timestamp}.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )

    if bytes_csv is not None:
        st.download_button(
            label="Download template (.csv)",
            data=bytes_csv,
            file_name=f"{base_name}_{timestamp}.csv",
            mime="text/csv",
        )

    st.divider()
    st.subheader("NWB Validation (optional)")
    st.caption(
        "Upload an .nwb file to run PyNWB validation and NWB Inspector best-practice checks."
    )

    uploaded = st.file_uploader("NWB file", type=["nwb"]) 
    col1, col2 = st.columns(2)
    with col1:
        do_pynwb = st.checkbox("Run PyNWB validator", value=True)
    with col2:
        do_inspector = st.checkbox("Run NWB Inspector", value=True)

    if uploaded is not None and (do_pynwb or do_inspector):
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(delete=False, suffix=".nwb") as tmp:
            tmp.write(uploaded.read())
            tmp_path = tmp.name

        try:
            if do_pynwb:
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

            if do_inspector:
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
                        # Show a compact table view
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


if __name__ == "__main__":
    main()
