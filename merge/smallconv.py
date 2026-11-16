"""Endian converters for two small Wii U formats BCML leaves alone: BLAL (sound loop asset list) and BECO (ecosystem area map)."""
import struct, collections

def blal_be_to_le(d):
    assert d[:4] == b"BLAL" and d[4:6] == b"\xfe\xff", "not a big-endian BLAL"
    n = struct.unpack_from(">I", d, 8)[0]; assert len(d) == 12 + 4 * n, (len(d), n)   # bytes 6..7 are two u8 (01 00 on both platforms)
    vals = struct.unpack_from(">%dI" % n, d, 12)
    return b"BLAL\xff\xfe" + d[6:8] + struct.pack("<I", n) + struct.pack("<%dI" % n, *vals)

def beco_parse(d, e):
    magic, rows, div, pad = struct.unpack_from(e + "4I", d, 0); assert magic == 0x00112233, hex(magic)
    offs = struct.unpack_from(e + "%dI" % rows, d, 16); base = 16 + 4 * rows
    body = struct.unpack_from(e + "%dH" % ((len(d) - base) // 2), d, base); assert (len(d) - base) % 2 == 0
    sums = collections.Counter(); vals = collections.Counter()
    for i, o in enumerate(offs):
        end = offs[i + 1] if i + 1 < rows else len(body) // 2 * 2 // 2 * 1
        # offsets are in units of 2 bytes from base; each segment = (value u16, length u16)
        seg = body[o:(offs[i + 1] if i + 1 < rows else len(body))]
        assert len(seg) % 2 == 0, (i, len(seg))
        sums[sum(seg[1::2])] += 1; vals.update(seg[0::2])
    return dict(rows=rows, div=div, pad=pad, offs=offs, body=body, row_widths=dict(sums), nvals=len(vals), maxval=max(vals))

def beco_be_to_le(d):
    p = beco_parse(d, ">")
    return struct.pack("<4I", 0x00112233, p["rows"], p["div"], p["pad"]) + struct.pack("<%dI" % p["rows"], *p["offs"]) + struct.pack("<%dH" % len(p["body"]), *p["body"])

if __name__ == "__main__":
    import sys
    sb, mb, se, me = [open(f, "rb").read() for f in sys.argv[1:5]]
    lb = blal_be_to_le(mb); print("blal: stock", len(sb), "converted", len(lb), "header equal", lb[:8] == sb[:8])
    a = set(struct.unpack_from("<%dI" % ((len(sb) - 12) // 4), sb, 12)); b = set(struct.unpack_from("<%dI" % ((len(lb) - 12) // 4), lb, 12))
    print(" stock-only", len(a - b), "mod-only", [hex(x) for x in b - a])
    ps = beco_parse(se, "<"); pm = beco_parse(me, ">"); le = beco_be_to_le(me); pl = beco_parse(le, "<")
    for k, p in (("stock", ps), ("mod-be", pm), ("converted", pl)): print("beco", k, {x: p[x] for x in ("rows", "div", "pad", "row_widths", "nvals", "maxval")}, len(p["body"]))
    print(" converted semantic == mod:", pl["offs"] == pm["offs"] and pl["body"] == pm["body"], "| header bytes equal stock:", le[:16] == se[:16])
    same_rows = sum(1 for i in range(ps["rows"]) if ps["body"][ps["offs"][i]:(ps["offs"][i+1] if i+1 < ps["rows"] else None)] == pm["body"][pm["offs"][i]:(pm["offs"][i+1] if i+1 < pm["rows"] else None)])
    print(" rows identical to stock Switch:", same_rows, "of", ps["rows"])
