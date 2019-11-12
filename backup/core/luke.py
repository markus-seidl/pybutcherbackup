# Bad pun: Luke Skywalker -> Luke Filewalker
import hashlib
import os
import logging

from typing import List
from tqdm import tqdm

from backup.common.logger import configure_logger
from backup.common.util import calculate_file_hash, configure_tqdm

logger = configure_logger(logging.getLogger(__name__))


class FileEntryDTO:
    def __init__(self):
        self.original_path = None
        """Path to the file at the original location."""
        self.original_filename = None
        """Original filename, add this after original_path."""
        self.sha_sum = None
        """SHA256 hash before backup."""
        self.modified_time = None
        """Modification time at time of backup (timestamp)"""
        self.relative_file = None
        """The relative path of this file to the specified backup root."""
        self.size = -1
        """Original size in bytes."""

    @property
    def original_file(self):
        return self.original_path + os.sep + self.original_filename

    def __repr__(self):
        return "<relative_file='%s'>" % self.relative_file


class LukeFilewalker:
    """Handles all (discovery) file operations."""

    def __init__(self, absolute_progress=True):
        self.absolute_progress = absolute_progress
        """Go through all directories beforehand and count the files for the progress bar."""

    @staticmethod
    def calculate_hash(filename: str, file_size: int = -1) -> str:
        sha256_hash = hashlib.sha256()
        with open(filename, "rb") as f:
            # Read and update hash string value in blocks of 4K
            block_size = 4096
            with tqdm(total=file_size, leave=False, unit='B', unit_scale=True, unit_divisor=1024) as t:
                configure_tqdm(t)
                t.set_description('Calculate hash')
                t.set_postfix(file=filename)

                for byte_block in iter(lambda: f.read(block_size), b""):
                    sha256_hash.update(byte_block)
                    t.update(block_size)

            return sha256_hash.hexdigest()

    def _find_relative_file(self, backup_dir: str, original_file_path: str) -> str:
        return original_file_path[len(backup_dir):]

    def file_generator(self, directory: str) -> (str, str):
        for subdir, dirs, files in os.walk(directory):
            for file in files:
                yield subdir, file

    def count_files(self, directory: str) -> int:
        count = 0

        with tqdm(total=None, leave=False, unit='files') as t:
            configure_tqdm(t)
            t.set_description('Counting files')

            for _, _, files in os.walk(directory):
                for _ in files:
                    count += 1

                    t.update(1)

        return count

    def walk_directory(self, directory: str, calculate_sha=True):
        file_count = -1

        if self.absolute_progress:
            file_count = self.count_files(directory)

        with tqdm(total=file_count, leave=False, unit='files') as t:
            configure_tqdm(t)
            t.set_description('Processing source files')
            for subdir, file in self.file_generator(directory):
                f = os.path.join(subdir, file)

                e = FileEntryDTO()

                e.original_path = subdir
                e.original_filename = file

                e.size = os.stat(f).st_size
                e.modified_time = os.path.getmtime(f)
                e.relative_file = self._find_relative_file(directory, f)

                if calculate_sha:
                    e.sha_sum = self.calculate_hash(f, e.size)

                # logger.debug("Found file <%s> (sha=%s, modified_time=%s, size=%s)"
                #              % (e.relative_file, e.sha_sum, e.modified_time, e.size)
                #           )
                t.update(1)

                yield e

    def walk_directory_list(self, directory: str, calculate_sha=True) -> List[FileEntryDTO]:
        ret = list()
        for e in self.walk_directory(directory, calculate_sha):
            ret.append(e)

        return ret
