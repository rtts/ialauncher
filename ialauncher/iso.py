'''
Minimal ISO 9660 reader, so that CD images can be extracted without
any external dependencies. Joliet filenames are used when present.
Raw images with 2352-byte sectors (such as BIN files that come with a
CUE sheet) are supported as well.

'''
import os
import struct

SECTOR = 2048
RAW_SECTOR = 2352
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


class ISOFile:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.sector_size = SECTOR
        self.data_offset = 0
        header = self.f.read(16)
        if header[:12] == SYNC:
            # Raw sectors: skip sync and header (and the subheader in
            # mode 2), ignore the error correction data at the end
            self.sector_size = RAW_SECTOR
            self.data_offset = 24 if header[15] == 2 else 16
        self.encoding = 'ascii'
        self.root = None
        sector = 16
        while True:
            desc = self.read(sector, SECTOR)
            kind = desc[0]
            if kind == 255 or desc[1:6] != b'CD001':
                break
            if kind == 1 and self.root is None:
                self.root = desc[156:190]
            if kind == 2 and desc[88:91] in (b'%/@', b'%/C', b'%/E'):
                self.root = desc[156:190]
                self.encoding = 'utf-16-be'
                break
            sector += 1
        if self.root is None:
            raise ValueError(f'{path} is not an ISO 9660 image')

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.f.close()

    def read(self, sector, size):
        if self.sector_size == SECTOR:
            self.f.seek(sector * SECTOR)
            return self.f.read(size)
        data = []
        while size > 0:
            self.f.seek(sector * self.sector_size + self.data_offset)
            block = self.f.read(min(size, SECTOR))
            if not block:
                break
            data.append(block)
            size -= len(block)
            sector += 1
        return b''.join(data)

    def walk(self, record=None, prefix=''):
        '''
        Yield (path, sector, size) for every file in the image.

        '''
        extent, size = struct.unpack_from('<I4xI', record or self.root, 2)
        data = self.read(extent, size)
        pos = 0
        while pos < len(data):
            length = data[pos]
            if length == 0:
                # Records never cross sector boundaries
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            rec = data[pos:pos + length]
            pos += length
            name_len = rec[32]
            raw_name = rec[33:33 + name_len]
            if raw_name in (b'\x00', b'\x01'):
                continue
            name = raw_name.decode(self.encoding, 'replace').split(';')[0]
            if name.endswith('.') and '.' not in name[:-1]:
                name = name[:-1]
            if not name or name in ('.', '..') or '/' in name or '\\' in name:
                continue
            path = os.path.join(prefix, name)
            if rec[25] & 0x02:
                yield from self.walk(rec, path)
            else:
                file_extent, file_size = struct.unpack_from('<I4xI', rec, 2)
                yield path, file_extent, file_size

    def extract(self, sector, size, dest, progress=None):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, 'wb') as out:
            while size > 0:
                block = self.read(sector, min(size, 512*SECTOR))
                if not block:
                    raise EOFError(f'Unexpected end of image while extracting {dest}')
                out.write(block)
                size -= len(block)
                sector += 512
                if progress:
                    progress(len(block))
