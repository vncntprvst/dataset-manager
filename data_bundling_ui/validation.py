from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List


def run_pynwb_validation(path: str) -> Dict[str, Any]:
    """Validate an NWB file using PyNWB's validator.

    Returns a dict with keys:
    - status: "ok" | "error" | "missing"
    - ok: bool (when available)
    - error_count: int
    - errors: List[str]
    """
    try:
        from pynwb import NWBHDF5IO  # type: ignore
        try:
            # new-style import available in recent PyNWB
            from pynwb.validate import validate as nwb_validate  # type: ignore
        except Exception:
            # very old fallback (unlikely)
            nwb_validate = None  # type: ignore

        with NWBHDF5IO(path, mode="r", load_namespaces=True) as io:
            nwbfile = io.read()
            errors: List[str] = []
            if nwb_validate is not None:
                try:
                    res = nwb_validate(nwbfile)
                    # res may be list/iterable of strings or ValidationErrors
                    if isinstance(res, list):
                        errors = [str(e) for e in res]
                    else:
                        try:
                            errors = [str(e) for e in list(res)]  # type: ignore
                        except Exception:
                            errors = [str(res)]  # best-effort
                except Exception as e:
                    # Best-effort: if validate fails, report exception as error
                    errors = [f"Validation raised: {e}"]
            else:
                # Minimal structural check: attempting to read file succeeded
                errors = []

        return {
            "status": "ok",
            "ok": len(errors) == 0,
            "error_count": len(errors),
            "errors": errors,
        }
    except ModuleNotFoundError:
        return {"status": "missing"}
    except Exception as e:
        return {
            "status": "error",
            "ok": False,
            "error_count": 1,
            "errors": [str(e)],
        }


def run_nwb_inspector(path: str) -> Dict[str, Any]:
    """Run NWB Inspector best-practice checks on a file.

    Returns a dict with keys:
    - status: "ok" | "missing" | "error"
    - count: int total messages
    - by_severity: dict severity->count
    - messages: list of simplified messages
    """
    try:
        # Try multiple entry points to handle version variance
        try:
            from nwbinspector import inspect_nwb  # type: ignore
        except Exception:
            inspect_nwb = None  # type: ignore

        if inspect_nwb is None:
            try:
                from nwbinspector.inspector import inspect_nwb  # type: ignore
            except Exception:
                return {"status": "missing"}

        messages = inspect_nwb(path)  # type: ignore

        simplified: List[Dict[str, Any]] = []
        sev_counter: Counter = Counter()

        for m in messages:
            # InspectorMessage has attributes; guard with getattr
            severity = getattr(m, "severity", None) or getattr(m, "importance", "INFO")
            check_name = getattr(m, "check_function_name", None) or getattr(m, "check_name", "")
            message = getattr(m, "message", "")
            location = getattr(m, "location", None) or \
                ".".join([
                    str(getattr(m, "object_type", "")),
                    str(getattr(m, "object_name", "")),
                ]).strip(".")

            sev_str = str(severity)
            sev_counter[sev_str] += 1
            simplified.append(
                {
                    "severity": sev_str,
                    "check_name": str(check_name),
                    "message": str(message),
                    "location": location,
                }
            )

        return {
            "status": "ok",
            "count": len(simplified),
            "by_severity": dict(sev_counter),
            "messages": simplified,
        }
    except ModuleNotFoundError:
        return {"status": "missing"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

