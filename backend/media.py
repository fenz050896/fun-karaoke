import re
from pathlib import Path

import anyio
from fastapi import HTTPException, Request
from fastapi.responses import StreamingResponse


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)$")
_CHUNK_SIZE = 64 * 1024


def _parse_range_header(range_header: str, file_size: int):
    match = _RANGE_RE.fullmatch(range_header.strip())
    if not match or "," in range_header:
        return None

    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return None

    if start_text:
        start = int(start_text)
        if start >= file_size:
            return None
        if end_text:
            end = int(end_text)
            if end < start:
                return None
            end = min(end, file_size - 1)
        else:
            end = file_size - 1
        return start, end

    suffix_length = int(end_text)
    if suffix_length <= 0:
        return None
    suffix_length = min(suffix_length, file_size)
    return file_size - suffix_length, file_size - 1


async def _read_file_range(path: Path, start: int, end: int):
    async with await anyio.open_file(path, mode="rb") as file:
        await file.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = await file.read(min(_CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def ranged_file_response(request: Request, path: Path, media_type: str):
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio not found")

    file_size = path.stat().st_size
    range_header = request.headers.get("range")
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": media_type,
    }

    if not range_header:
        headers["Content-Length"] = str(file_size)
        return StreamingResponse(
            _read_file_range(path, 0, file_size - 1),
            status_code=200,
            headers=headers,
            media_type=media_type,
        )

    byte_range = _parse_range_header(range_header, file_size)
    if byte_range is None:
        headers["Content-Range"] = f"bytes */{file_size}"
        headers["Content-Length"] = "0"
        return StreamingResponse(
            iter(()),
            status_code=416,
            headers=headers,
            media_type=media_type,
        )

    start, end = byte_range
    headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(
        _read_file_range(path, start, end),
        status_code=206,
        headers=headers,
        media_type=media_type,
    )
