import tempfile
from unittest import TestCase, main

from backup.db.domain import *
from backup.db.db import DatabaseManager


class DomainTest(TestCase):
    def test_basic_store_load(self):
        with tempfile.NamedTemporaryFile() as tmp_filename:
            db_manager = DatabaseManager(tmp_filename.name)

            with db_manager.database.atomic():
                backups = BackupsEntry.create(
                    name="Blah"
                )

                backup = BackupEntry.create(
                    backups=backups,
                    type=BackupType.FULL
                )

                disc = DiscEntry.create(
                    backup=backup
                )

                archive = ArchiveEntry.create(
                    disc=disc
                )

                file01 = FileEntry.create(
                    original_filepath="p01",
                    original_filename="n01",
                    sha_sum="sha256_01",
                    modified_time=datetime.datetime.now(),
                    relative_file="r01",
                    size=1,
                    backup=backup
                )

                file02 = FileEntry.create(
                    original_filepath="p02",
                    original_filename="n02",
                    sha_sum="sha256_02",
                    modified_time=datetime.datetime.now(),
                    relative_file="r02",
                    size=2,
                    backup=backup
                )

                archive_file_map01 = ArchiveFileMap.create(
                    archive=archive,
                    file=file01
                )
                archive_file_map02 = ArchiveFileMap.create(
                    archive=archive,
                    file=file02
                )

                BackupFileMap.create(
                    backup=backup,
                    file=file01,
                    state=FileState.NEW
                )

                BackupFileMap.create(
                    backup=backup,
                    file=file02,
                    state=FileState.NEW
                )

                assert BackupsEntry.select().count() == 1

                test_backup_entry = BackupEntry.select().first()
                test_disc_entry = test_backup_entry.discs[0]
                test_archive_entry = test_disc_entry.archives[0]

                assert len(test_backup_entry.all_files) == 2

                files_for_archive = (ArchiveEntry
                                     .select()
                                     .join(ArchiveFileMap)
                                     .join(FileEntry))

                assert len(files_for_archive) == 2


if __name__ == '__main__':
    main()
