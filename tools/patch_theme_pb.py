#!/usr/bin/env python3
"""Patch Gboard theme protobuf files without touching key colors."""
from pathlib import Path
import argparse


def read_varint(data, pos):
    value = 0
    shift = 0
    while pos < len(data):
        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift
        if not b & 0x80:
            return value, pos
        shift += 7
    raise ValueError("truncated varint")


def varint(value):
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def fields(data):
    pos = 0
    while pos < len(data):
        start = pos
        tag, pos = read_varint(data, pos)
        num, wire = tag >> 3, tag & 7
        payload = None
        if wire == 0:
            _, pos = read_varint(data, pos)
        elif wire == 1:
            pos += 8
        elif wire == 2:
            n, pos = read_varint(data, pos)
            payload_start = pos
            pos += n
            if pos > len(data):
                raise ValueError("truncated length-delimited field")
            payload = data[payload_start:pos]
        elif wire == 5:
            pos += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        yield start, pos, num, wire, payload


def encode_len_field(field_num, payload):
    return varint((field_num << 3) | 2) + varint(len(payload)) + payload


def transparent_literal(field_num):
    # Nested color literal: field 1 (uint32) = ARGB 0x00000000.
    return encode_len_field(field_num, b"\x08\x00")


BACKGROUND_NAMES = (
    b"keyboard-body-area",
    b"keyboard-base-area",
    b"keyboard-header-area",
    b"keyboard-background",
    b"keyboard-clipboard-popup",
    b"keyboard-clipboard-tooltip.panel",
    b"keyboard-clipboard-item.panel",
    b"clipboard-accessory-body-top-bar",
    b"bg-clipboard-item-board-popup.panel",
    b"expression-keyboard-background",
    b"navbar.for-expression-footer.panel",
    b"translate.queryholder.panel",
    b"translate.language.panel.bg",
    b"translate-keyboard-network-card.panel",
)


def is_background_rule(strings):
    joined = b"\0".join(strings)
    return any(name in joined for name in BACKGROUND_NAMES)


def patch_message(msg, mode):
    fs = list(fields(msg))
    strings = [payload for _, _, _, wire, payload in fs if wire == 2 and payload is not None]
    joined = b"\0".join(strings)
    if mode == "alias":
        if not any(x in joined for x in (
            b"default_keyboard_background_primary_color",
            b"default_keyboard_background_secondary_color",
            b"default_keyboard_background_header_color",
        )):
            return msg, False
        target_num = 3
    else:
        if not is_background_rule(strings):
            return msg, False

    has_color_property = any(
        n == 2 and wire == 0 and read_varint(msg[start:end], 1)[0] == 1
        for start, end, n, wire, _ in fs
    )
    out = bytearray()
    changed = False
    for start, end, n, wire, payload in fs:
        raw = msg[start:end]
        if mode == "alias" and n == 3 and wire == 2:
            raw = transparent_literal(3)
            changed = True
        elif mode == "rule" and n == 4 and wire == 2 and has_color_property:
            raw = transparent_literal(4)
            changed = True
        elif mode == "rule" and n == 3 and wire == 2 and has_color_property:
            # Direct ARGB color value used by legacy/overlay rules.
            raw = transparent_literal(3)
            changed = True
        out += raw
    return bytes(out), changed


def patch_file(src, dst):
    data = src.read_bytes()
    out = bytearray()
    changed = False
    for start, end, n, wire, payload in fields(data):
        raw = data[start:end]
        if wire == 2 and payload is not None and n in (1, 2):
            mode = "alias" if n == 2 else "rule"
            patched, did_change = patch_message(payload, mode)
            if did_change:
                raw = encode_len_field(n, patched)
                changed = True
        out += raw
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(bytes(out))
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, required=True, help="Extracted assets/theme directory")
    ap.add_argument("--output", type=Path, required=True, help="Output patched assets/theme directory")
    args = ap.parse_args()
    report = []
    for src in sorted(args.input.glob("*.binarypb")):
        dst = args.output / src.name
        try:
            changed = patch_file(src, dst)
            report.append(("PATCHED" if changed else "COPIED") + " " + src.name)
        except Exception as exc:
            report.append(f"ERROR {src.name}: {exc}")
    (args.output / "PATCH_REPORT.txt").write_text("\n".join(report) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    main()
