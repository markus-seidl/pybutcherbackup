import tempfile
from unittest import TestCase, main
from unittest.mock import Mock
import time

from backup.db.domain import *
from backup.db.db import DatabaseManager, BackupType
from backup.core.luke import FileEntryDTO
from backup.multi.archive import ThreadingArchiveManager
from common.customtestcase import CustomTestCase


class TestThreadingArchiveManager(CustomTestCase):
    def test_iteration_00(self):
        pass  # todo
