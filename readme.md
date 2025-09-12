# Dataset manager

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
- Electrophysiology – Extracellular / Intracellular
- Behavior and physiological measurements
- Optical Physiology
- Stimulations
- Experimental metadata and notes (implicit)

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

### Folder spec with <placeholders>

In Project → Data organization, define your structure using angle‑bracket placeholders inside names:

- `<SUBJECT_ID>`: subject folder name
- `<YYYYMMDD>` or `<YYYY_MM_DD>`: date in folder name
- `<SESSION_ID>`: session folder name

Examples:

1) Simple, date as its own folder

```
<SUBJECT_ID>
├── <YYYY_MM_DD>
│   ├── <SESSION_ID>
│   │   ├── raw_ephys_data
│   │   └── processed_data
```

2) Date embedded into session name

```
<SUBJECT_ID>
├── <SESSION_ID>_<YYYYMMDD>
```

Use the “Check folder structure against spec” button to validate your actual project folders against this spec. The app warns when:
- subject folders are missing,
- date folders don’t match `<YYYYMMDD>` or `<YYYY_MM_DD>`,
- session folders are missing or don’t include the date token when required.

Note: dates like `2025-04-01` (with hyphens) do not match `<YYYY_MM_DD>`.

### Defining subjects and sessions

There are three ways to define `subject_id` and subject metadata. These are used to auto-populate the template on the Descriptors page and later during conversions:

1) Folder name (Project page → Data organization)
- If your dataset directory contains top-level subject folders, each subject folder name becomes the default `subject_id` for all sessions inside it (e.g., `Mouse123`).

2) `subject.json` inside each subject folder
- Place a `subject.json` file next to session folders. Any fields here override the folder name. Suggested keys align with NWB `Subject` fields: `subject_id`, `age`, `sex`, `species`, `subject_description`, `genotype`, `subject_weight`, `subject_strain`, `date_of_birth(YYYY-MM-DD)`.

3) Manually in the template
- You can edit `subject_id` and other fields in the generated spreadsheet.

Notes:
- If “Fetch notes/metadata from brainSTEM.org” is enabled on the Descriptors page, subject and session-related fields are treated as auto-populated. The app fetches notes (not a single subject at a time) so you can reconcile them per subject later in your workflow.
- The Experimenter field is auto-populated from your Project page configuration.

## Notes

- If `dandischema` is installed, DANDI fields are derived from the Pydantic models; otherwise a curated list is used.
- If `pynwb` is installed, NWB required fields are sourced from `NWBFile`; otherwise a curated list is used.
- NWB Validation: Upload an `.nwb` file in the app to run PyNWB validation and NWB Inspector checks (requires `pynwb` and `nwbinspector`).
