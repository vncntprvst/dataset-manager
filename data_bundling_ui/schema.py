from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set


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

        # Known required args for NWBFile constructor
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
    experiment_types: List[str], include_dandi: bool, include_nwb: bool
) -> List[str]:
    fields: List[str] = []

    # Per-experiment fields
    for et in experiment_types:
        fields.extend(EXPERIMENT_TYPE_FIELDS.get(et, []))

    # DANDI fields
    if include_dandi:
        dandi_fields = _try_import_dandi_fields()
        fields.extend(dandi_fields if dandi_fields else CURATED_DANDI_FIELDS)

    # NWB fields
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

