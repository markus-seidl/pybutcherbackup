import tempfile
import unittest

from backup.db.domain import *
from backup.db.db import DatabaseManager, BackupType
from backup.core.luke import FileEntryDTO
from tests.common.customtestcase import CustomTestCase


class DomainTest(CustomTestCase):
    def test_process_write(self):
        with tempfile.NamedTemporaryFile() as tmp_filename:
            db_manager = DatabaseManager(tmp_filename.name)

            dto_file01_01_01 = self.create_dummy_file(1)
            dto_file01_02_01 = self.create_dummy_file(2)

            # write backup
            with db_manager.transaction():
                backup_manager = db_manager.create_backup(BackupType.FULL, None)

                disc01 = backup_manager.create_disc()

                archive01_01 = backup_manager.create_archive(disc01)
                file01_01_01 = backup_manager.create_file_from_dto(dto_file01_01_01, FileState.NEW)
                backup_manager.map_file_to_archive(file01_01_01, archive01_01)

                archive01_02 = backup_manager.create_archive(disc01)
                file01_02_01 = backup_manager.create_file_from_dto(dto_file01_02_01, FileState.NEW)
                backup_manager.map_file_to_archive(file01_02_01, archive01_02)

            # validate on disk storage
            test_backup_entry = BackupEntry.select().first()
            assert len(BackupEntry.select()) == 1  # there should only one backup assigned

            assert len(test_backup_entry.all_files) == 2
            assert len(test_backup_entry.discs) == 1

            test_disc = test_backup_entry.discs[0]
            assert len(test_disc.archives) == 2

            archive00 = test_disc.archives[0]
            assert len(archive00.files) == 1
            assert archive00.files[0].file.size == 1

            archive01 = test_disc.archives[1]
            assert len(archive01.files) == 1
            assert archive01.files[0].file.size == 2

    def create_dummy_file(self, idx) -> FileEntryDTO:
        ret = FileEntryDTO()

        ret.sha_sum = idx + 512_000
        ret.modified_time = idx
        ret.relative_file = "/path/" + str(idx)
        ret.size = idx

        return ret
