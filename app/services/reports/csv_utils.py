import csv
import io
from collections.abc import Iterable

from fastapi.responses import StreamingResponse


def rows_to_csv_response(rows: Iterable[dict], filename: str) -> StreamingResponse:
    """Streams a list of row dicts back as a downloadable CSV file.

    Takes plain dicts (not Pydantic models) so callers can apply per-role column
    projection before serializing — see column_policy.py.
    """
    rows = list(rows)
    buffer = io.StringIO()
    if rows:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
