import csv
import io
from collections.abc import Iterable

from fastapi.responses import StreamingResponse
from pydantic import BaseModel


def rows_to_csv_response(rows: Iterable[BaseModel], filename: str) -> StreamingResponse:
    """Streams a list of Pydantic row models back as a downloadable CSV file."""
    rows = list(rows)
    buffer = io.StringIO()
    if rows:
        fieldnames = list(rows[0].model_dump().keys())
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.model_dump())
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
