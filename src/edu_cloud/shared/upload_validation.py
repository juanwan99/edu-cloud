"""Upload file validation utilities."""

_IMAGE_SIGNATURES: dict[bytes, str] = {
    b"\xff\xd8\xff": "jpeg",
    b"\x89PNG\r\n\x1a\n": "png",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"BM": "bmp",
    b"RIFF": "webp",
    b"II\x2a\x00": "tiff",
    b"MM\x00\x2a": "tiff",
}


def detect_image_type(header: bytes) -> str | None:
    for sig, name in _IMAGE_SIGNATURES.items():
        if header[:len(sig)] == sig:
            if name == "webp" and b"WEBP" not in header[:16]:
                continue
            return name
    return None
