import hashlib
import os
from enum import Enum
from tqdm import tqdm

from backup.common.progressbar import ProgressBar


def is_enum(obj):
    """Determines whether the object is an enum.Enum."""

    if obj is None:
        return True

    try:
        return issubclass(obj.__class__, Enum)
    except TypeError:
        return False


def auto_str(cls):
    def __str__(self):
        return '%s(%s)' % (
            type(self).__name__,
            ', '.join('%s=%s' % item for item in vars(self).items())
        )

    cls.__str__ = __str__
    return cls


def calculate_file_hash(filename):
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()


def copy_with_progress(src_file: str, dest_file: str, t: ProgressBar, length=16 * 1024):
    t.total = os.stat(src_file).st_size

    with open(src_file, 'rb') as fsrc:
        with open(dest_file, 'wb') as fdst:
            while 1:
                buf = fsrc.read(length)
                if not buf:
                    return
                fdst.write(buf)
                t.update(length)
