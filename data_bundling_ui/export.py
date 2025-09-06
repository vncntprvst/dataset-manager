from __future__ import annotations

import csv
import io
from typing import List


def build_csv_bytes(columns: List[str], n_rows: int) -> io.BytesIO:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(columns)
    for _ in range(n_rows):
        writer.writerow([""] * len(columns))
    raw = buf.getvalue().encode("utf-8")
    return io.BytesIO(raw)


def build_workbook_bytes(columns: List[str], n_rows: int) -> io.BytesIO:
    """Build XLSX workbook in-memory using pandas/openpyxl/xlsxwriter if available.

    Raises if no supported writer is available so caller can fall back to CSV.
    """
    # Try pandas with openpyxl/xlsxwriter engines
    try:
        import pandas as pd  # type: ignore

        df = pd.DataFrame(columns=columns, data=[[None] * len(columns) for _ in range(n_rows)])
        bio = io.BytesIO()
        # Prefer openpyxl; fall back to xlsxwriter
        try:
            df.to_excel(bio, index=False, engine="openpyxl")
        except Exception:
            df.to_excel(bio, index=False, engine="xlsxwriter")
        bio.seek(0)
        return bio
    except Exception as e:
        # Last-chance: minimal openpyxl without pandas
        try:
            from openpyxl import Workbook  # type: ignore

            wb = Workbook()
            ws = wb.active
            ws.title = "Template"
            ws.append(columns)
            for _ in range(n_rows):
                ws.append([None] * len(columns))
            bio = io.BytesIO()
            wb.save(bio)
            bio.seek(0)
            return bio
        except Exception as e2:
            # Propagate a meaningful combined error
            raise RuntimeError(
                "No Excel writer available (pandas/openpyxl/xlsxwriter missing)"
            ) from e2

