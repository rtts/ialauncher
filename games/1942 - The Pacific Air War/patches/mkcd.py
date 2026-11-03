"""Write 1942.CD, one central directory for the joined 1942.00? files.

The six floppies hold 1942.001 to 1942.006, which joined together are
12 zip files in a row, each with its own central directory. Appending
1942.CD, a central directory of all their files, gives a single zip
file that PKUNZJR can extract in one go:

    copy 1942.001+1942.002+...+1942.006+1942.cd 1942.zip

Usage: python3 mkcd.py 1942.001 ... 1942.006 > 1942.cd
"""

import struct
import sys
from pathlib import Path

LOCAL = struct.Struct("<4sHHHHHIIIHH")
CENTRAL = struct.Struct("<4sHHHHHHIIIHHHHHII")
END = struct.Struct("<4sHHHHIIH")
ATTRIBUTES = (0, 0, 0, 0, 0x20)


def main() -> None:
    """Print the central directory for the joined files."""
    data = b"".join(Path(name).read_bytes() for name in sys.argv[1:])
    entries = []
    offset = 0
    while offset < len(data):
        signature = data[offset : offset + 4]
        if signature == b"PK\1\2":
            nlen, xlen, clen = struct.unpack_from("<HHH", data, offset + 28)
            offset += CENTRAL.size + nlen + xlen + clen
            continue
        if signature == b"PK\5\6":
            (clen,) = struct.unpack_from("<H", data, offset + 20)
            offset += END.size + clen
            continue
        if signature != b"PK\3\4":
            sys.exit(f"Unexpected data at offset {offset}")
        header = LOCAL.unpack_from(data, offset)
        _, version, flag, *_, csize, _, nlen, xlen = header
        if flag & 8:
            sys.exit("Sizes in data descriptors aren't supported")
        name = data[offset + LOCAL.size : offset + LOCAL.size + nlen]
        central = CENTRAL.pack(b"PK\1\2", version, *header[1:10], *ATTRIBUTES, offset)
        entries.append(central + name)
        offset += LOCAL.size + nlen + xlen + csize
    directory = b"".join(entries)
    end = END.pack(
        b"PK\5\6", 0, 0, len(entries), len(entries), len(directory), len(data), 0
    )
    sys.stdout.buffer.write(directory + end)


if __name__ == "__main__":
    main()
