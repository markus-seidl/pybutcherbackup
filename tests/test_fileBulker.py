from unittest import TestCase, main
import tempfile
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backup.io.archive import FileBulker
from backup.io.luke import FileEntryDTO


class TestFileBulker(TestCase):
    def test_archive_package_iter(self):
        files = list()

        files.append(FileEntryDTO())
        files.append(FileEntryDTO())
        files.append(FileEntryDTO())

        files[0].size = 100_000
        files[1].size = 100_000
        files[2].size = 1_000_000

        FileBulker(files).archive_package_iter()
