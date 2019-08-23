# Bad pun: Luke Skywalker -> Luke Filewalker
import hashlib
import os
from typing import List

from backup.common.util import calculate_file_hash


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
        self.relative_path = None
        """The relative path of this file to the specified backup root."""
        self.size = -1
        """Original size in bytes."""

    def original_file(self):
        return self.original_path + os.sep + self.original_filename

    def __repr__(self):
        return "<relative_file='%s'>" % self.relative_path


class LukeFilewalker:
    """Handles all (discovery) file operations."""

    @staticmethod
    def calculate_hash(filename: str) -> str:
        return calculate_file_hash(filename)

    def _find_relative_path(self, backup_dir: str, original_file_path: str) -> str:
        return original_file_path[len(backup_dir):]

    def file_generator(self, directory: str) -> (str, str):
        for subdir, dirs, files in os.walk(directory):
            for file in files:
                yield subdir, file

    def walk_directory(self, directory: str, calculate_sha=True):
        for subdir, file in self.file_generator(directory):
            f = os.path.join(subdir, file)

            e = FileEntryDTO()

            e.original_path = subdir
            e.original_filename = file

            if calculate_sha:
                e.sha_sum = self.calculate_hash(f)
            e.modified_time = os.path.getmtime(f)
            e.relative_path = self._find_relative_path(directory, f)

            e.size = os.stat(f).st_size

            yield e

    def walk_directory_list(self, directory: str, calculate_sha=True) -> List[FileEntryDTO]:
        ret = list()
        for e in self.walk_directory(directory, calculate_sha):
            ret.append(e)

        return ret
