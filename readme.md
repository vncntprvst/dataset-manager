# Data Bundling UI

A Streamlit interface that helps bundle data and metadata based on experimental types provided by users.

**DANDI Metadata Standards:**
- Imports official [dandischema](https://docs.dandiarchive.org) Pydantic models
- Automatically provides required/optional fields and data types
- Ensures compatibility with DANDI archive submission requirements

**NWB Core Requirements:**
- Leverages PyNWB for proper NWB file structure
- Enforces minimum required fields: `session_description`, `identifier`, `session_start_time`
- Validates structure using PyNWB's built-in validator and NWB Inspector best practices

### Workflow

1. Select experimental types relevant to your research
2. Choose whether to include DANDI/NWB metadata fields
3. Specify the number of recording sessions (rows) needed
4. Generate and download your customized template as `.xlsx` or `.csv`it interface for generating customized Excel/CSV spreadsheet templates based on experimental data types. This tool helps researchers create standardized data collection templates that comply with NWB (Neurodata Without Borders) and DANDI (Distributed Archives for Neurophysiology Data Integration) standards.

**Project Context:** Part of the High- and low-level computations for coordination of orofacial motor actions project, Team BRAIN Circuit Program (U19) NS137920. 
🔗 [Project Website](https://rhythm-n-rodents.github.io/)

## Overview

This application generates data collection templates tailored to specific experimental types. Users select their experimental modalities, and the tool automatically creates spreadsheets with the appropriate metadata fields required for NWB file creation and DANDI archive submission.

### Supported Experimental Types
- **Electrophysiology** - Neural recordings
- **Behavior tracking** - Movement and behavioral data
- **Optogenetics** - Light-stimulation experiments
- **Miniscope imaging** - Miniaturized microscopy
- **Fiber photometry** - Fluorescence recordings
- **2-photon imaging** - High-resolution neural imaging
- **Widefield imaging** - Large-scale brain activity
- **EEG recordings** - Electroencephalography

### Schema Validation

The application enforces data standards through two canonical schema layers:

DANDI metadata: import the official dandischema (Pydantic models) and/or JSON Schema it emits. That gives us required/optional fields and types “for free.” 
see: docs.dandiarchive.org

NWB core: rely on PyNWB for model construction; minimally, NWBFile requires session_description, identifier, and session_start_time. Validate structure with PyNWB’s validator and best-practice checks with NWB Inspector.

Then we run the generator script to create the appropriate spreadsheet table for the experimenter to fill out for each recording session.

## Usage
- Clone this repo.
- Run the app:
If using [`uv`](https://docs.astral.sh/uv/getting-started/installation/) (recommended):  
`uv run streamlit run app.py`

or, if not using uv:
    - Create a virtual environment (Python 3.9+), then install dependencies:  
    `pip install -r requirements.txt`
    - Activate environment, then `streamlit run app.py`

- In the sidebar, select experimental types and whether to include DANDI/NWB fields.
- Set the number of rows (sessions) you want in the template.
- Download as `.xlsx` (if pandas/openpyxl present) or `.csv`.

## Notes

- If `dandischema` is installed, DANDI fields are derived from the Pydantic models; otherwise a curated list is used.
- If `pynwb` is installed, NWB required fields are sourced from `NWBFile`; otherwise a curated list is used.
- NWB Validation: Upload an `.nwb` file in the app to run PyNWB validation and NWB Inspector checks (requires `pynwb` and `nwbinspector`).
