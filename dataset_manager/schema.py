from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple


# Curated defaults used if external libs are unavailable
# Only essential DANDI fields for basic archive submission
CURATED_DANDI_FIELDS: List[str] = [
    "dataset_name",  # Dataset/project name (maps to DANDI 'name' field)
    "dataset_description",  # Dataset description (maps to DANDI 'description' field)
    "contributor_name",  # Principal investigator/contributor
    "contributor_role", # Role (e.g., "ContactPerson", "Creator")
    "keywords",  # Research keywords
    "protocol",  # Experimental protocol description
]

# Common fields expected in U19 templates (order matters)
COMMON_FIELDS: List[str] = [
    "session_start_time(YYYY-MM-DD HH:MM)",
    "session_id",
    "subject_id",
    "age",
    "subject_description",
    "genotype",
    "sex",
    "species",
    "subject_weight",
    "subject_strain",
    "date_of_birth(YYYY-MM-DD)",
    "session_description",
    "src_folder_directory",
    "experimenters",
    "institution",
    "identifier",
]

CURATED_NWB_FIELDS: List[str] = [
    # Minimal NWBFile requirements
    "session_description",
    "identifier",
    "session_start_time",
    # Common best-practice fields
    "experiment_description",
    "experimenter",
    "lab",
    "institution",
    "related_publications",
]


"""
Template/proxy fields by experiment type
---------------------------------------
These are human-friendly template fields collected in spreadsheets; they do NOT
directly correspond to NWB API arguments. Downstream ingestion/conversion
scripts (e.g., prep.py, volumetric_imaging_h5ToNWB.py) translate these fields
into proper NWB objects and attributes. Typical mappings include:

- Device: fields like "ephys_acq_system", "two_photon_microscope", "camera_model",
  "fp_device_model" map to NWB `Device` via `nwbfile.create_device()`
  (e.g., name/description/manufacturer consolidated from multiple template fields).

- Electrode groups: fields like "probe_model", "reference_scheme", and/or additional
  per-probe metadata map to `nwbfile.create_electrode_group()` and to per-electrode
  table columns (e.g., group name/description, device linkage).

- Imaging series: fields like frame rates and wavelengths (e.g., "imaging_frame_rate_fps",
  "laser_wavelength_nm", "illumination_wavelength_nm") inform construction of
  ImageSeries/TwoPhotonSeries/OpticalChannel objects linked to the appropriate Device.

The UI and validation code treat these fields as a proxy layer so that:
- researchers can fill intuitive fields without worrying about the NWB API;
- we can validate completeness pre-conversion; and
- the mapping logic can evolve without changing the templates.
"""

# Per experiment-type extra fields (extend as needed)
EXPERIMENT_TYPE_FIELDS: Dict[str, List[str]] = {
    "Electrophysiology – Extracellular": [
        "ephys_acq_system",
        "sampling_rate_hz",
        "num_channels",
        "probe_model",
        "reference_scheme",
        # EEG/EMG electrode configuration (montage = arrangement of electrodes for recording)
        "electrode_configuration",
    ],
    "Electrophysiology – Intracellular": [
        "icephys_setup",
        "recording_mode",  # e.g., current-clamp, voltage-clamp
        "sampling_rate_hz",
        "cell_id",
        "electrode_name",
    ],
    "Behavior and physiological measurements": [
        "behavior_modality",
        "camera_count",
        "frame_rate_fps",
        "tracking_software",
    ],
    "Stimulations": [
        # Keep existing field names for backward compatibility with templates/validation
        "opto_device_model",
        "stimulation_wavelength_nm",
        "stimulation_power_mw",
        "stimulation_protocol",
    ],
    "Optical Physiology": [
        # Unified ophys proxy fields across 2p/widefield/miniscope/photometry
        "ophys_device_model",
        "imaging_frame_rate_fps",
        "field_of_view_um",
        "imaging_indicator",
        "objective_magnification",
        "numerical_aperture",
        "excitation_wavelength_nm",
        "emission_wavelength_nm",
        "camera_model",
    ],
    "Sync and Task events or parameters": [
        # Task/stimulus parameters and synchronization events
        "task_protocol",
        "stimulus_type",
        "sync_system",
        "event_timing_precision_ms",
    ],
    # Additional organizational/annotation type — always available as a modality
    # Keep field list minimal to avoid imposing structure; detailed metadata
    # can be captured in free-form notes or external systems (e.g., brainSTEM).
    "Experimental metadata and notes": [
        "protocol",
        "experiment_notes",
    ],
}


# Fields that the app can auto-populate from files/folders; used for UI grouping
AUTO_FIELDS: List[str] = [
    "src_folder_directory",
    "session_id",
    "session_start_time(YYYY-MM-DD HH:MM)",
    "date_of_birth(YYYY-MM-DD)",
    "identifier",
    # Dataset-level fields that can be auto-populated from project configuration
    "dataset_name",  # From project name in dataset.yaml
    "dataset_description",  # From project description
]

# Additional fields that should be auto-populated when brainSTEM is enabled
BRAINSTEM_AUTO_FIELDS: List[str] = [
    "subject_id",
    "age", 
    "subject_description",
    "genotype",
    "sex",
    "species",
    "subject_weight", 
    "subject_strain",
    "session_description",
    "experimenters",
    "session_start_time",
    "institution",
]

# Mapping from brainSTEM API responses to our template fields.
# Each tuple represents the nested key path in the response JSON. These
# paths are heuristics and may need adjustment for a given deployment.
BRAINSTEM_FIELD_MAP: Dict[str, Tuple[str, ...]] = {
    "subject_id": ("subject", "id"),
    "age": ("subject", "age"),
    "subject_description": ("subject", "description"),
    "genotype": ("subject", "genotype"),
    "sex": ("subject", "sex"),
    "species": ("subject", "species"),
    "subject_weight": ("subject", "weight"),
    "subject_strain": ("subject", "strain"),
    "session_description": ("session", "description"),
    "experimenters": ("session", "experimenters"),
    "session_start_time": ("session", "start_time"),
    "institution": ("session", "institution"),
}

# Scaffold for extracting brainSTEM-derived values for auto-filled fields.
def extract_brainstem_values(meta: Dict[str, Any]) -> Dict[str, Any]:
    """Return mapping of template field names to values extracted from brainSTEM.

    Missing paths are ignored. This helper is intentionally permissive and is
    expected to be adapted once the exact brainSTEM response schema is known.
    """

    out: Dict[str, Any] = {}
    for field, path in BRAINSTEM_FIELD_MAP.items():
        value: Any = meta
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)
            if value is None:
                break
        if value not in (None, ""):
            out[field] = value
    return out

# Mapping of template fields to semantic categories for UI grouping
FIELD_CATEGORIES: Dict[str, str] = {
    # Subject-related fields
    "subject_id": "Subject",
    "age": "Subject",
    "subject_description": "Subject",
    "genotype": "Subject",
    "sex": "Subject",
    "species": "Subject",
    "subject_weight": "Subject",
    "subject_strain": "Subject",
    "date_of_birth(YYYY-MM-DD)": "Subject",
    # Session-related fields
    "session_start_time(YYYY-MM-DD HH:MM)": "Session",
    "session_start_time": "Session",
    "session_id": "Session",
    "session_description": "Session",
    "src_folder_directory": "Session",
    # Experiment details
    "experiment_description": "Experiment",
    "experimenters": "Experiment",
    "experimenter": "Experiment",
    # Institutional metadata
    "institution": "Institution",
    "lab": "Institution",
    # Dataset-level metadata
    "dataset_name": "Dataset",
    "dataset_description": "Dataset",
    "contributor_name": "Dataset",
    "contributor_role": "Dataset",
    "keywords": "Dataset",
    "protocol": "Dataset",
    # General identifier/other
    "identifier": "Other",
}


def get_field_category(field: str) -> str:
    """Return the semantic category for a template field.

    Falls back to heuristics based on common prefixes if the field is not in
    :data:`FIELD_CATEGORIES`.
    """

    if field in FIELD_CATEGORIES:
        return FIELD_CATEGORIES[field]
    if field.startswith("subject_") or field in {"age", "sex", "species"}:
        return "Subject"
    if field.startswith("session_"):
        return "Session"
    if field in {"experiment_description", "experimenter", "experimenters", "protocol"}:
        return "Experiment"
    if field in {"institution", "lab"}:
        return "Institution"
    if field.startswith("dataset_") or field in {"contributor_name", "contributor_role", "keywords"}:
        return "Dataset"
    return "Other"


def _try_import_dandi_fields() -> List[str] | None:
    try:
        # Lazy import; dandischema is optional
        from dandischema.models import Dandiset
        
        # Only return user-relevant fields for session templates
        # Use descriptive field names that can be mapped to DANDI fields later
        session_relevant_fields = [
            "dataset_name",  # Dataset/project name (maps to DANDI 'name' field)
            "dataset_description",  # Dataset description (maps to DANDI 'description' field)
            "contributor_name",  # Contributor information (maps to DANDI 'contributor' field)
            "keywords",  # Research keywords
        ]
        
        # Map our descriptive field names to actual DANDI model field names for verification
        dandi_field_mapping = {
            "dataset_name": "name",
            "dataset_description": "description", 
            "contributor_name": "contributor",
            "keywords": "keywords"
        }
        
        # Verify the underlying DANDI fields exist in the model
        model = Dandiset
        available_fields = []
        for our_field_name, dandi_field_name in dandi_field_mapping.items():
            if dandi_field_name in model.model_fields:  # type: ignore[attr-defined]
                available_fields.append(our_field_name)
        
        return available_fields if available_fields else None
    except Exception:
        return None


def _try_import_nwb_fields() -> List[str] | None:
    try:
        from pynwb.file import NWBFile

        # Extract required arguments dynamically from PyNWB's docval metadata
        if hasattr(NWBFile.__init__, '__docval__'):
            docval_info = NWBFile.__init__.__docval__
            if 'args' in docval_info:
                # Extract required arguments (those without 'default' key)
                required = []
                for arg in docval_info['args']:
                    name = arg.get('name')
                    if name and 'default' not in arg:
                        required.append(name)
                return required if required else None

        # Fallback to known required args if docval metadata isn't available
        required = [
            "session_description",
            "identifier",
            "session_start_time",
        ]
        return required
    except Exception:
        return None


def get_supported_experiment_types() -> List[str]:
    return list(EXPERIMENT_TYPE_FIELDS.keys())


def collect_required_fields(
    experiment_types: List[str], include_dandi: bool = True, include_nwb: bool = True
) -> List[str]:
    # Start with the common U19 fields to ensure Subject and defaults show up
    fields: List[str] = list(COMMON_FIELDS)

    # Per-experiment fields
    for et in experiment_types:
        fields.extend(EXPERIMENT_TYPE_FIELDS.get(et, []))

    # DANDI fields
    if include_dandi:
        dandi_fields = _try_import_dandi_fields()
        fields.extend(dandi_fields if dandi_fields else CURATED_DANDI_FIELDS)

    # NWB fields (ensure required ones are present; COMMON_FIELDS already includes many)
    if include_nwb:
        nwb_fields = _try_import_nwb_fields()
        fields.extend(nwb_fields if nwb_fields else CURATED_NWB_FIELDS)

    # Deduplicate while preserving order
    seen: Set[str] = set()
    deduped: List[str] = []
    for f in fields:
        if f not in seen:
            seen.add(f)
            deduped.append(f)

    return deduped


def split_user_vs_auto(fields: List[str], use_brainstem: bool = False) -> Tuple[List[str], List[str]]:
    """Split fields into user-provided vs auto-populated categories.
    
    Args:
        fields: List of field names to categorize
        use_brainstem: If True, treat subject/session metadata as auto-populated
    
    Returns:
        Tuple of (user_fields, auto_fields)
    """
    auto_set = set(AUTO_FIELDS)
    if use_brainstem:
        auto_set.update(BRAINSTEM_AUTO_FIELDS)
    
    user_fields: List[str] = []
    auto_fields: List[str] = []
    for f in fields:
        (auto_fields if f in auto_set else user_fields).append(f)
    return user_fields, auto_fields


# ---- Additional helpers for dynamic subject/DANDI fields ----
def get_nwb_subject_fields() -> List[str]:
    """Best-effort retrieval of PyNWB Subject field names.

    Uses PyNWB docval metadata when available; otherwise falls back to a curated list.
    """
    try:
        from pynwb.file import Subject  # type: ignore

        if hasattr(Subject.__init__, "__docval__"):
            args = Subject.__init__.__docval__.get("args", [])  # type: ignore[attr-defined]
            names = [a.get("name") for a in args if a.get("name")]
            # Filter out 'self' and duplicates
            out: List[str] = []
            seen: Set[str] = set()
            for n in names:
                if n and n != "self" and n not in seen:
                    seen.add(n)
                    out.append(n)
            return out
    except Exception:
        pass
    # Fallback subject-related fields commonly used in U19 templates
    return [
        "subject_id",
        "age",
        "subject_description",
        "genotype",
        "sex",
        "species",
        "subject_weight",
        "subject_strain",
        "date_of_birth(YYYY-MM-DD)",
    ]


def get_dandi_required_fields() -> List[str]:
    """Return DANDI required top-level fields when dandischema is installed.

    Falls back to curated set used elsewhere if the library is unavailable.
    """
    d = _try_import_dandi_fields()
    if d:
        return d
    return CURATED_DANDI_FIELDS


def get_dandi_field_mapping() -> Dict[str, str]:
    """Return mapping from our descriptive field names to DANDI field names.
    
    This mapping should be used when exporting templates to DANDI format.
    
    Returns:
        Dictionary mapping our field names -> DANDI field names
    """
    return {
        # Dataset-level fields
        "dataset_name": "name",
        "dataset_description": "description",
        "contributor_name": "contributor",
        "contributor_role": "contributor",  # Part of contributor structure
        "keywords": "keywords",
        "protocol": "protocol",
        # Note: contributor_name and contributor_role both map to the 'contributor' 
        # field in DANDI, which expects a structured object with name and role
    }


def get_field_descriptions() -> Dict[str, str]:
    """Return descriptions for template fields to help users understand what they mean.
    
    Returns:
        Dictionary mapping field names to their descriptions
    """
    return {
        # Subject fields
        "subject_id": "Subject identifier unique within the project.",
        "age": "Age of the subject at time of experiment (e.g., 'P60').",
        "subject_description": "Free-text description of the subject.",
        "genotype": "Genetic line or modifications.",
        "sex": "Biological sex of the subject.",
        "species": "Species of the subject (e.g., 'Mus musculus').",
        "subject_weight": "Weight of the subject with units (e.g., '25 g').",
        "subject_strain": "Strain of the subject.",
        "date_of_birth(YYYY-MM-DD)": "Subject's date of birth (YYYY-MM-DD).",

        # Session fields
        "session_start_time(YYYY-MM-DD HH:MM)": "Start time of the session in UTC (YYYY-MM-DD HH:MM).",
        "session_start_time": "Start time of the session.",
        "session_id": "Unique identifier for this session (e.g., folder name).",
        "session_description": "Summary or purpose of the session.",
        "src_folder_directory": "Path to source data folder for this session.",

        # Experiment fields
        "experiment_description": "Description of the experiment or protocol.",
        "experimenters": "Names of experimenters for this session.",
        "experimenter": "Name of the experimenter.",

        # Institution fields
        "institution": "Institution where the experiment was performed.",
        "lab": "Laboratory or department name.",

        # Administrative/other fields
        "identifier": "Unique dataset identifier (e.g., GUID).",

        # Dataset fields
        "dataset_name": (
            "Name/title of your dataset (auto-populated from project configuration). "
            "This will be used as the dataset title when publishing to DANDI."
        ),
        "dataset_description": (
            "Description of your dataset (auto-populated from project configuration). "
            "Provides an overview of the research and experimental approach."
        ),
        "contributor_name": "Name of the principal investigator or main contributor.",
        "contributor_role": "Role of the contributor (e.g., 'ContactPerson', 'Creator').",
        "keywords": "Research keywords describing your study.",
        "protocol": "Description of experimental protocols used.",

        # Electrophysiology fields
        "electrode_configuration": (
            "Electrode configuration/arrangement for EEG/EMG recordings. "
            "Describes how electrodes are positioned and referenced relative to each other. "
            "Examples: 'bipolar', 'monopolar', 'common average reference', 'Cz reference'. "
            "Not typically used for intracranial/probe recordings."
        ),
        "reference_scheme": (
            "Reference electrode configuration used for recording. "
            "Examples: 'common average reference', 'single electrode reference', 'bipolar', 'ground'."
        ),
        "probe_model": (
            "Model/type of recording probe or electrode array. "
            "Examples: 'Neuropixels 1.0', 'Neuronexus A32', 'custom tetrode array'."
        ),
        "ephys_acq_system": (
            "Electrophysiology data acquisition system used. "
            "Examples: 'Intan RHD2000', 'Blackrock Cerebus', 'SpikeGLX', 'OpenEphys'."
        ),
    }
