import tempfile
import unittest

from backup.db.domain import *
from backup.db.db import DatabaseManager, BackupType
from core.luke import FileEntryDTO


class DomainTest(unittest.TestCase):
    def test_process(self):
        with tempfile.NamedTemporaryFile() as tmp_filename:
            db_manager = DatabaseManager(tmp_filename.name)

            with db_manager.database.atomic():
                backup_manager = db_manager.create_backup(BackupType.FULL)

                disc01 = backup_manager.create_disc()

                archive01_01 = backup_manager.create_archive(disc01)
                file01_01_01 = self.create_dummy_file(1)
                file01_01_02 = self.create_dummy_file(2)
                file01_01_03 = self.create_dummy_file(3)

                archive01_02 = backup_manager.create_archive(disc01)
                file01_02_01 = self.create_dummy_file(4)
                file01_02_02 = self.create_dummy_file(5)
                file01_02_03 = self.create_dummy_file(6)

    def create_dummy_file(self, idx) -> FileEntryDTO:
        pass
