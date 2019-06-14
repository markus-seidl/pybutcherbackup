import os

from peewee import SqliteDatabase

from backup.db.domain import *
from enum import Enum

from backup.core.luke import FileEntryDTO


class BackupDatabaseWriter:
    def __init__(self, backup_root):
        self.backup_root = backup_root
        self.files = dict()
        """Map of all registered files (relative_path, FileEntry)"""
        self.archive_number = 0
        """Number of registered archives."""
        self.disc_number = 0
        """Number of registered discs."""

    def create_file_from_dto(self, file: FileEntryDTO) -> FileEntry:
        return self.create_file(
            file.original_path,
            file.original_filename,
            file.sha_sum,
            file.modified_time,
            file.relative_path,
            file.size
        )

    def create_file(self, original_path,
                    original_filename,
                    sha_sum,
                    modified_time,
                    relative_path,
                    size) -> FileEntry:
        """Creates the database representation and automagically registers the file to the current backup."""
        # Prevent duplication of files
        original_file = original_path + os.sep + original_filename
        if original_file in self.files:
            return self.get_file(relative_path)

        file = FileEntry.create(
            original_filepath=original_path,
            original_filename=original_filename,
            sha_sum=sha_sum,
            modified_time=modified_time,
            relative_path=relative_path,
            size=size,
            archive_map=None,
            backup=None
        )

        self.files[original_file] = file
        self.map_file_to_backup(file)

        return file

    def get_file(self, relative_path) -> FileEntry:
        return self.files[relative_path]

    def create_disc(self) -> DiscEntry:
        no = self.disc_number
        self.disc_number += 1

        return DiscEntry.create(
            number=no,
            backup=self.backup_root
        )

    def create_archive(self, for_disc) -> ArchiveEntry:
        no = self.archive_number
        self.archive_number += 1

        return ArchiveEntry.create(
            number=no,
            disc=for_disc
        )

    def map_file_to_archive(self, file, archive) -> ArchiveFileMap:
        return ArchiveFileMap.create(
            archive=archive,
            file=file
        )

    def map_file_to_backup(self, file):
        return BackupFileMap.create(
            backup=self.backup_root,
            file=file
        )


class BackupDatabaseReader:

    @staticmethod
    def create_reader_from_backup(backup_root: BackupsEntry, backup_start):
        for backup in backup_root.backups.order_by(BackupEntry.created):
            print(backup)

        return None


class BackupType(Enum):
    FULL = "FULL"
    DIFFERENTIAL = "DIFF"


# Note that the database manager is static because of the "static" proxy to peewee.database
class DatabaseManager:
    def __init__(self, file_name):
        self.file_name = file_name
        self.database = database
        self.open_database(file_name)

    def transaction(self):
        return self.database.transaction()

    def open_database(self, file_name):
        database.initialize(SqliteDatabase(file_name, pragmas={'foreign_keys': 1}))
        self.create_tables()

    def create_tables(self):
        with database:
            database.create_tables(
                [BackupsEntry, BackupEntry, DiscEntry, ArchiveEntry,
                 ArchiveFileMap, FileEntry, BackupFileMap]
            )

    def all_backups(self):
        return BackupEntry.select()

    def backups_root(self) -> BackupsEntry:
        s = BackupsEntry.select()
        if len(s) == 0:
            return BackupsEntry.create()
        else:
            return s.first()

    def create_backup(self, backup_type: BackupType) -> BackupDatabaseWriter:
        backup = BackupEntry.create(
            backups=self.backups_root(),
            type=backup_type.name
        )

        return BackupDatabaseWriter(backup)

    def read_backup(self, backup) -> BackupDatabaseReader:
        return BackupDatabaseReader.create_reader_from_backup(self.backups_root(), backup)
