"""Memory-only packages for Store-approved fixed analysis visual specifications.

``render_visual_package(approved_spec, *, expected_run_id, expected_run_hash,
expected_input_hash, expected_data_hash)`` returns ``(spec_bytes, png_bytes,
receipt)``. ``verify_visual_package(spec_bytes, png_bytes, *, approved_spec,
expected_run_id, expected_run_hash, expected_input_hash, expected_data_hash,
expected_png_hash)`` returns the same closed plain-JSON receipt. Its spec_bytes
and png_bytes fields are byte *counts*; hashes are lowercase SHA-256. Spec bytes
are sorted, compact UTF-8 JSON (ensure_ascii=False, allow_nan=False).

The caller must supply the independently trusted, complete Store-approved spec,
run/input/data bindings and, on fresh read, the previously saved PNG hash. This
helper checks equality and integrity, not scientific approval or authenticity
of an image from untrusted hashes. All fields of the existing closed schema
are matched, not only data or a self-supplied spec hash. Save retries can verify
existing bytes without rendering again. No storage, paths, network, models or
caller-selected fonts/styles are used. Historical PNG runtime metadata is
recorded, never compared against currently installed library/font versions.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import struct
import zlib

from .analysis_visuals import (
    MAX_BYTES, RENDERER_VERSION, SCHEMA_VERSION, VisualSpecError,
    render_visual_png, validate_visual_spec,
)

MAX_SPEC_BYTES = MAX_BYTES
MAX_PNG_BYTES = 8 * 1024 * 1024
MAX_DESCRIPTION_BYTES = MAX_SPEC_BYTES + 1024
_MAX_CHUNKS = 1024
_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}\Z")
_UNSAFE = re.compile(r"[<>\\/`{};]|(?:https?|file|data|javascript|ftp):|www\.", re.I)


class VisualPackageError(VisualSpecError):
    """A spec/PNG package is unsupported, oversized or inconsistent."""


def _require(condition, message):
    if not condition:
        raise VisualPackageError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _closed_object(value, fields, label):
    _require(type(value) is dict and set(value) == set(fields), label + " fields")


def _json_bytes(raw, maximum, label):
    """Bound before parsing; reject duplicates/nonfinite values at every level."""
    _require(type(raw) is bytes and 0 < len(raw) <= maximum, label + " byte limit")
    try:
        text = raw.decode("utf-8")
        # json.loads alone can recurse before a later schema/depth check.
        depth, in_string, escaped = 0, False, False
        for char in text:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char in "[{":
                depth += 1
                _require(depth <= 10, label + " depth limit")
            elif char in "]}":
                depth -= 1

        def pairs(items):
            result = {}
            for key, value in items:
                _require(key not in result, label + " duplicate JSON key")
                result[key] = value
            return result

        def constant(_):
            raise VisualPackageError(label + " nonfinite JSON number")

        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
        # This also rejects numeric exponent overflow (e.g. 1e999) and
        # lone surrogates. The renderer validator imposes the tighter schema.
        _canonical(value)
        return value
    except (UnicodeError, ValueError, RecursionError) as exc:
        if isinstance(exc, VisualPackageError):
            raise
        raise VisualPackageError(label + " invalid JSON") from exc


def _approved(approved_spec, bindings):
    # Bindings are values, never objects with caller-defined equality methods.
    _require(type(bindings["expected_run_id"]) is str, "invalid expected run ID")
    for key in ("expected_run_hash", "expected_input_hash", "expected_data_hash"):
        _require(type(bindings[key]) is str and _HASH.fullmatch(bindings[key]),
                 "invalid expected binding hash")
    try:
        return validate_visual_spec(approved_spec, **bindings)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise VisualPackageError("invalid approved spec: " + str(exc)) from exc


def _runtime(value):
    _closed_object(value, {"matplotlib", "pillow", "font_family"}, "runtime")
    for key in ("matplotlib", "pillow"):
        _require(type(value[key]) is str and _VERSION.fullmatch(value[key]),
                 "invalid runtime version")
    family = value["font_family"]
    _require(type(family) is str and 0 < len(family) <= 80
             and family.strip() == family and all(c.isprintable() for c in family)
             and not _UNSAFE.search(family), "invalid runtime font family")
    return dict(value)


def _inflate_text(raw, maximum):
    # Never decompress metadata without a limit, including zTXt/iTXt bombs.
    try:
        inflater = zlib.decompressobj()
        result = inflater.decompress(raw, maximum + 1)
        _require(len(result) <= maximum and inflater.eof
                 and not inflater.unconsumed_tail and not inflater.unused_data,
                 "compressed metadata limit or invalid stream")
        return result
    except zlib.error as exc:
        raise VisualPackageError("invalid compressed metadata") from exc


def _png_text(kind, data):
    key, separator, rest = data.partition(b"\0")
    _require(separator and key in (b"Description", b"Software"), "unexpected PNG metadata")
    limit = MAX_DESCRIPTION_BYTES if key == b"Description" else 64
    encoding = "latin-1"
    if kind == b"zTXt":
        _require(rest[:1] == b"\0", "PNG metadata compression method")
        rest = _inflate_text(rest[1:], limit)
    elif kind == b"iTXt":
        _require(len(rest) >= 4 and rest[0] in (0, 1) and rest[1] == 0,
                 "PNG international metadata header")
        compressed, rest = rest[0], rest[2:]
        language, separator, rest = rest.partition(b"\0")
        _require(separator and not language, "PNG metadata language")
        translated, separator, rest = rest.partition(b"\0")
        _require(separator and not translated, "PNG translated metadata key")
        if compressed:
            rest = _inflate_text(rest, limit)
        encoding = "utf-8"
    _require(len(rest) <= limit, "PNG metadata byte limit")
    try:
        return key.decode("ascii"), rest.decode(encoding)
    except UnicodeError as exc:
        raise VisualPackageError("invalid PNG metadata encoding") from exc


def _image_stream(raw, channels):
    # Pillow can accept incomplete zlib checksums or ignore appended streams,
    # and LOAD_TRUNCATED_IMAGES is process-global. Validate the entire IDAT
    # stream independently before calling Pillow, with a fixed decode budget.
    stride = 1 + 1200 * channels
    expected = 800 * stride
    try:
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(raw, expected + 1)
        _require(len(decoded) == expected and inflater.eof
                 and not inflater.unconsumed_tail and not inflater.unused_data,
                 "PNG image stream length or termination")
        _require(all(value <= 4 for value in decoded[::stride]), "PNG row filter")
    except zlib.error as exc:
        raise VisualPackageError("invalid PNG image stream") from exc


def _png_metadata(png_bytes):
    """Check the bounded renderer PNG profile and every CRC before Pillow."""
    _require(type(png_bytes) is bytes and 0 < len(png_bytes) <= MAX_PNG_BYTES,
             "PNG byte limit")
    _require(png_bytes.startswith(_SIGNATURE), "PNG signature")
    offset, count, idat_count = len(_SIGNATURE), 0, 0
    metadata, seen, image_parts = {}, set(), []
    while offset < len(png_bytes):
        count += 1
        _require(count <= _MAX_CHUNKS and offset + 12 <= len(png_bytes), "PNG chunk limit")
        length, kind = struct.unpack_from(">I4s", png_bytes, offset)
        end = offset + 12 + length
        _require(end <= len(png_bytes), "truncated PNG chunk")
        data = png_bytes[offset + 8:end - 4]
        crc = struct.unpack_from(">I", png_bytes, end - 4)[0]
        _require(zlib.crc32(data, zlib.crc32(kind)) & 0xffffffff == crc, "PNG chunk CRC")
        _require(kind in (b"IHDR", b"tEXt", b"zTXt", b"iTXt", b"pHYs", b"IDAT", b"IEND"),
                 "unsupported PNG chunk")
        if count == 1:
            _require(kind == b"IHDR" and length == 13, "PNG IHDR")
        if kind == b"IHDR":
            _require(count == 1, "duplicate PNG IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", data)
            _require((width, height) == (1200, 800) and depth == 8 and color in (2, 6)
                     and (compression, filtering, interlace) == (0, 0, 0), "PNG header profile")
        elif kind in (b"tEXt", b"zTXt", b"iTXt"):
            _require(not idat_count, "PNG metadata order")
            key, value = _png_text(kind, data)
            _require(key not in metadata, "duplicate PNG " + key)
            metadata[key] = value
        elif kind == b"pHYs":
            _require(kind not in seen and not idat_count and length == 9, "PNG resolution chunk")
            _require(data[-1] in (0, 1), "PNG resolution unit")
        elif kind == b"IDAT":
            _require(length > 0, "empty PNG image chunk")
            idat_count += 1
            image_parts.append(data)
        elif kind == b"IEND":
            _require(length == 0 and idat_count > 0 and end == len(png_bytes), "PNG end or trailing bytes")
            _require(set(metadata) == {"Description", "Software"}, "missing PNG metadata")
            mode = "RGB" if color == 2 else "RGBA"
            _image_stream(b"".join(image_parts), 3 if color == 2 else 4)
            return metadata, mode
        seen.add(kind)
        offset = end
    raise VisualPackageError("missing PNG IEND")


def _verify(spec_bytes, png_bytes, approved, bindings, expected_png_hash):
    _require(type(expected_png_hash) is str and _HASH.fullmatch(expected_png_hash),
             "invalid expected PNG hash")
    parsed = _json_bytes(spec_bytes, MAX_SPEC_BYTES, "spec")
    try:
        validated = validate_visual_spec(parsed, **bindings)
    except (ValueError, TypeError, OverflowError, RecursionError) as exc:
        raise VisualPackageError("invalid package spec: " + str(exc)) from exc
    _require(spec_bytes == _canonical(validated), "noncanonical spec bytes")
    _require(spec_bytes == _canonical(approved), "approved spec mismatch")
    metadata, mode = _png_metadata(png_bytes)
    png_hash = hashlib.sha256(png_bytes).hexdigest()
    _require(png_hash == expected_png_hash, "PNG hash mismatch")
    _require(metadata["Software"] == RENDERER_VERSION, "PNG Software version")
    description = _json_bytes(metadata["Description"].encode("utf-8"), MAX_DESCRIPTION_BYTES, "Description")
    _closed_object(description, {"spec", "runtime"}, "Description")
    _require(_canonical(description["spec"]) == spec_bytes, "PNG Description spec mismatch")
    runtime = _runtime(description["runtime"])

    from PIL import Image
    try:
        # verify() and load() are separate: the former checks structure, the
        # latter forces actual pixel decoding rather than accepting a header.
        with Image.open(io.BytesIO(png_bytes)) as image:
            _require(image.format == "PNG" and image.size == (1200, 800)
                     and image.mode == mode, "decoded PNG profile")
            image.verify()
        with Image.open(io.BytesIO(png_bytes)) as image:
            image.load()
            _require(image.size == (1200, 800) and image.mode == mode
                     and image.info.get("Software") == metadata["Software"]
                     and image.info.get("Description") == metadata["Description"],
                     "decoded PNG metadata mismatch")
    except (OSError, ValueError, SyntaxError, EOFError, zlib.error) as exc:
        if isinstance(exc, VisualPackageError):
            raise
        raise VisualPackageError("invalid PNG image") from exc
    return {"spec_hash": hashlib.sha256(spec_bytes).hexdigest(), "spec_bytes": len(spec_bytes),
            "png_hash": png_hash, "png_bytes": len(png_bytes), "width": 1200, "height": 800,
            "schema_version": SCHEMA_VERSION, "renderer_version": RENDERER_VERSION,
            "runtime": runtime}


def render_visual_package(approved_spec, *, expected_run_id, expected_run_hash,
                          expected_input_hash, expected_data_hash):
    """Render once and return canonical spec bytes, PNG bytes and receipt."""
    bindings = dict(expected_run_id=expected_run_id, expected_run_hash=expected_run_hash,
                    expected_input_hash=expected_input_hash, expected_data_hash=expected_data_hash)
    approved = _approved(approved_spec, bindings)
    spec_bytes = _canonical(approved)
    png_bytes = render_visual_png(approved, **bindings)
    receipt = _verify(spec_bytes, png_bytes, approved, bindings, hashlib.sha256(png_bytes).hexdigest())
    return spec_bytes, png_bytes, receipt


def verify_visual_package(spec_bytes, png_bytes, *, approved_spec, expected_run_id,
                          expected_run_hash, expected_input_hash, expected_data_hash,
                          expected_png_hash):
    """Verify existing bytes without rerendering, returning their closed receipt."""
    bindings = dict(expected_run_id=expected_run_id, expected_run_hash=expected_run_hash,
                    expected_input_hash=expected_input_hash, expected_data_hash=expected_data_hash)
    return _verify(spec_bytes, png_bytes, _approved(approved_spec, bindings), bindings, expected_png_hash)
