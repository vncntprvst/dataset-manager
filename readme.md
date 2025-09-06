Streamlit interface that defines a xls spreadsheet table based on experimental types provided by users. 
Users are part of High- and low-level computations for coordination of orofacial motor actions. Team BRAIN Circuit Program (U19) NS137920. https://rhythm-n-rodents.github.io/

Experimental types are typically (not limited to):
Electrophysiology
Behavior tracking
Optogenetics
Miniscope imaging
Fiber photometry
2p imaging
Widefield imaging
EEG recordings

The interface backend asserts what fields are required based on NWB/DANDI schema + validators. 
Canonical schema layer:

DANDI metadata: import the official dandischema (Pydantic models) and/or JSON Schema it emits. That gives us required/optional fields and types “for free.” 
see: docs.dandiarchive.org

NWB core: rely on PyNWB for model construction; minimally, NWBFile requires session_description, identifier, and session_start_time. Validate structure with PyNWB’s validator and best-practice checks with NWB Inspector.

Then we run the generator script to create the appropriate spreadsheet table for the experimenter to fill out for each recording session.

---

Usage

- Prereqs: Python 3.9+ recommended.
- Optional dependencies enable richer extraction and XLSX export; the app gracefully falls back if missing.

Install (optional but recommended)

- Create a virtual environment, then install dependencies:
- `pip install -r requirements.txt`

Run the app

- `streamlit run app.py`
- In the sidebar, select experimental types and whether to include DANDI/NWB fields.
- Set the number of rows (sessions) you want in the template.
- Download as `.xlsx` (if pandas/openpyxl present) or `.csv`.

Notes

- If `dandischema` is installed, DANDI fields are derived from the Pydantic models; otherwise a curated list is used.
- If `pynwb` is installed, NWB required fields are sourced from `NWBFile`; otherwise a curated list is used.
- Validation and NWB Inspector integration can be added in a subsequent iteration.
