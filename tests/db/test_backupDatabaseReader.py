import tempfile
import unittest
import time

from backup.db.domain import *
from backup.db.db import DatabaseManager, BackupType
from backup.core.luke import FileEntryDTO


class TestBackupDatabaseReader(unittest.TestCase):

    def test_basic_operation(self):
        with tempfile.NamedTemporaryFile() as tmp_filename:
            db_manager = DatabaseManager(tmp_filename.name)

            dto_file01_full_01_01 = self.create_dummy_file(1)
            dto_file01_full_02_01 = self.create_dummy_file(2)

            with db_manager.transaction():
                backup_manager = db_manager.create_backup(BackupType.FULL, None)
                # empty FULL backup

            time.sleep(0.1)  # this ensures that the diff backup is a few milliseconds older. Helps in sorting backups

            # write backup FULL
            with db_manager.transaction():
                backup_manager = db_manager.create_backup(BackupType.FULL, None)

                disc01 = backup_manager.create_disc()

                archive01_01 = backup_manager.create_archive(disc01)
                file01_01_01 = backup_manager.create_file_from_dto(dto_file01_full_01_01, FileState.NEW)
                backup_manager.map_file_to_archive(file01_01_01, archive01_01)

                archive01_02 = backup_manager.create_archive(disc01)
                file01_02_01 = backup_manager.create_file_from_dto(dto_file01_full_02_01, FileState.NEW)
                backup_manager.map_file_to_archive(file01_02_01, archive01_02)

            dto_file01_diff_01_01 = self.create_dummy_file(3)

            time.sleep(0.1)  # this ensures that the diff backup is a few milliseconds older. Helps in sorting backups

            # write diff backup
            with db_manager.transaction():
                backup_manager = db_manager.create_backup(BackupType.INCREMENTAL, None)

                disc01 = backup_manager.create_disc()

                backup_manager.create_file_from_dto(dto_file01_full_02_01, FileState.DELETED)

                archive01_02 = backup_manager.create_archive(disc01)
                file01_02_01 = backup_manager.create_file_from_dto(dto_file01_diff_01_01, FileState.NEW)
                backup_manager.map_file_to_archive(file01_02_01, archive01_02)

            time.sleep(0.1)  # this ensures that the diff backup is a few milliseconds older. Helps in sorting backups

            # write diff backup
            with db_manager.transaction():
                backup_manager = db_manager.create_backup(BackupType.INCREMENTAL, None)

                disc01 = backup_manager.create_disc()

                archive01_02 = backup_manager.create_archive(disc01)
                file01_02_01 = backup_manager.create_file_from_dto(dto_file01_full_02_01, FileState.NEW)
                backup_manager.map_file_to_archive(file01_02_01, archive01_02)

            bm = db_manager.read_backup(None)
            af = bm.all_files

            assert len(af) == 3
            assert dto_file01_diff_01_01.relative_file in af  # file created in 1. diff backup
            assert dto_file01_full_01_01.relative_file in af  # file created in 1 full, and not mentioned in 2. diff
            assert dto_file01_full_02_01.relative_file in af  # file created - deleted - created

    def create_dummy_file(self, idx) -> FileEntryDTO:
        ret = FileEntryDTO()

        ret.original_path = "/original/path/"
        ret.original_filename = str(idx)
        ret.sha_sum = idx + 512_000
        ret.modified_time = idx
        ret.relative_file = "/path/" + str(idx)
        ret.size = idx

        return ret
