from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple


# Curated defaults used if external libs are unavailable
CURATED_DANDI_FIELDS: List[str] = [
    "dandiset_id",
    "dandiset_version",
    "name",
    "description",
    "keywords",
    "contributor_name",
    "contributor_role",
    "institution",
    "species",
    "anatomy",
    "age",
    "sex",
    "session_start_time",
    "protocol",
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
    "Electrophysiology": [
        "ephys_acq_system",
        "sampling_rate_hz",
        "num_channels",
        "probe_model",
        "reference_scheme",
    ],
    "Behavior tracking": [
        "behavior_modality",
        "camera_count",
        "frame_rate_fps",
        "tracking_software",
    ],
    "Optogenetics": [
        "opto_device_model",
        "stimulation_wavelength_nm",
        "stimulation_power_mw",
        "stimulation_protocol",
    ],
    "Miniscope imaging": [
        "miniscope_model",
        "imaging_frame_rate_fps",
        "field_of_view_um",
        "imaging_indicator",
    ],
    "Fiber photometry": [
        "fp_device_model",
        "excitation_wavelength_nm",
        "emission_wavelength_nm",
        "sampling_rate_hz",
    ],
    "2p imaging": [
        "two_photon_microscope",
        "objective_magnification",
        "numerical_aperture",
        "laser_wavelength_nm",
        "imaging_frame_rate_fps",
    ],
    "Widefield imaging": [
        "widefield_system",
        "illumination_wavelength_nm",
        "camera_model",
        "imaging_frame_rate_fps",
    ],
    "EEG recordings": [
        "eeg_system",
        "sampling_rate_hz",
        "montage",
        "reference_scheme",
    ],
}


# Fields that the app can auto-populate from files/folders; used for UI grouping
AUTO_FIELDS: List[str] = [
    "src_folder_directory",
    "session_id",
    "session_start_time(YYYY-MM-DD HH:MM)",
    "date_of_birth(YYYY-MM-DD)",
    "identifier",
]


def _try_import_dandi_fields() -> List[str] | None:
    try:
        # Lazy import; dandischema is optional
        from dandischema.models import Dandiset
        from pydantic.fields import FieldInfo

        # Build from model fields; choose a representative set
        model = Dandiset
        required = []
        for name, field in model.model_fields.items():  # type: ignore[attr-defined]
            info: FieldInfo = field
            if info.is_required():
                required.append(name)
        # Provide a stable ordering
        required_sorted = sorted(set(required))
        return required_sorted or None
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


def split_user_vs_auto(fields: List[str]) -> Tuple[List[str], List[str]]:
    auto_set = set(AUTO_FIELDS)
    user_fields: List[str] = []
    auto_fields: List[str] = []
    for f in fields:
        (auto_fields if f in auto_set else user_fields).append(f)
    return user_fields, auto_fields

