from pathlib import Path
import struct

ROOT = Path('/home/ubuntu/gboard_patch/orig/assets/theme')
OUT = Path('/home/ubuntu/gboard_patch/patched_theme')
OUT.mkdir(parents=True, exist_ok=True)

# Android/Gboard color literals are uint32 ARGB. Zero is fully transparent.
TRANSPARENT = b'\x08\x00'

def read_varint(data, pos):
    start = pos
    value = 0
    shift = 0
    while pos < len(data):
        b = data[pos]; pos += 1
        value |= (b & 0x7f) << shift
        if not b & 0x80:
            return value, pos
        shift += 7
        if shift > 70:
            raise ValueError('bad varint')
    raise ValueError('truncated varint')

def fields(data):
    pos = 0
    while pos < len(data):
        start = pos
        tag, pos = read_varint(data, pos)
        num, wire = tag >> 3, tag & 7
        if wire == 0:
            _, pos = read_varint(data, pos)
        elif wire == 1:
            pos += 8
        elif wire == 2:
            n, pos = read_varint(data, pos)
            payload_start = pos
            pos += n
            if pos > len(data): raise ValueError('truncated bytes')
        elif wire == 5:
            pos += 4
        else:
            raise ValueError(f'unsupported wire {wire}')
        yield start, pos, num, wire, data[payload_start:pos] if wire == 2 else None

def encode_len_field(num, payload):
    return bytes([num << 3 | 2, len(payload)]) + payload

def encode_literal(num, field_num):
    # nested message: field 1 (uint32) = zero
    nested = b'\x08' + TRANSPARENT[1:]
    return encode_len_field(field_num, nested)

def patch_message(msg, mode):
    # mode=alias: a color alias definition has field 1=name and field 3=ref.
    # mode=rule: a style rule has field 1=selector and field 4=ref.
    fs = list(fields(msg))
    has_color_property = any(
        n == 2 and w == 0 and read_varint(msg[start:end], 1)[0] == 1
        for start, end, n, w, _ in fs
    )
    strings = [p for _, _, n, w, p in fs if w == 2]
    joined = b'\0'.join(strings)
    if mode == 'alias':
        if not any(x in joined for x in (b'default_keyboard_background_primary_color', b'default_keyboard_background_secondary_color', b'default_keyboard_background_header_color')):
            return msg, False
        target_num = 3
    else:
        if not any(x in joined for x in (b'keyboard-body-area', b'keyboard-base-area', b'keyboard-header-area', b'keyboard-background')):
            return msg, False
        target_num = 4
    out = bytearray(); changed = False
    for start, end, n, w, payload in fs:
        raw = msg[start:end]
        if n == target_num and w == 2:
            # Replace only string-reference field with a literal transparent color.
            raw = encode_literal(3, target_num)
            changed = True
        elif mode == 'rule' and has_color_property and n == 3 and w == 2 and b'keyboard-' in joined:
            # Direct ARGB background values used by legacy/overlay themes.
            raw = encode_literal(3, 3)
            changed = True
        out += raw
    return bytes(out), changed

report = []
for src in sorted(ROOT.glob('*.binarypb')):
    data = src.read_bytes()
    changed = False
    out = bytearray()
    try:
        top = list(fields(data))
        for start, end, n, w, payload in top:
            raw = data[start:end]
            if n == 2 and w == 2:
                p1, c1 = patch_message(payload, 'alias')
                p2, c2 = patch_message(p1, 'rule')
                raw = encode_len_field(2, p2) if (c1 or c2) else raw
                changed |= c1 or c2
            elif n == 1 and w == 2:
                p, c = patch_message(payload, 'rule')
                raw = encode_len_field(1, p) if c else raw
                changed |= c
            out += raw
    except Exception as e:
        report.append(f'ERROR {src.name}: {e}')
        continue
    if changed:
        (OUT / src.name).write_bytes(bytes(out))
        report.append(f'PATCHED {src.name}')
    else:
        (OUT / src.name).write_bytes(data)
report_path = OUT / 'PATCH_REPORT.txt'
report_path.write_text('\n'.join(report) + '\n')
print('\n'.join(report))
