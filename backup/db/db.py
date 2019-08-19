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

    def create_file_from_dto(self, file: FileEntryDTO, state: FileState) -> FileEntry:
        return self.create_file(
            file.original_path,
            file.original_filename,
            file.sha_sum,
            file.modified_time,
            file.relative_path,
            file.size,
            state
        )

    def create_file(self, original_path,
                    original_filename,
                    sha_sum,
                    modified_time,
                    relative_path,
                    size, state: FileState) -> FileEntry:
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
        self.map_file_to_backup(file, state)

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

    def map_file_to_backup(self, file, state: FileState):
        """
        Maps the file to the current backup. Automagically called when the file entity is created.
        """
        return BackupFileMap.create(
            backup=self.backup_root,
            file=file,
            state=state
        )


class BackupDatabaseReader:
    class FileInfo:
        def __init__(self, file: FileEntry, state: FileState, backup: BackupEntry):
            self.file = file
            self.state = state
            self.backup = backup

            afm = ArchiveFileMap.select().join(ArchiveEntry).join(DiscEntry).where(
                (ArchiveFileMap.file == file)
                & (DiscEntry.backup == backup)
            ).first()
            if afm is None:
                raise RuntimeError("Database corruption, can't find backup for file %s" % file)

            self.archive = afm.archive
            self.disc = afm.archive.disc

    @staticmethod
    def create_reader_from_backup(backup_root: BackupsEntry, backup_start):
        backups = list()

        for backup in backup_root.backups.order_by(BackupEntry.created.desc()):
            backups.append(backup)
            if backup.type == BackupType.FULL:
                break

        backups.reverse()
        # generate full file list
        file_original_file = dict()
        file_sha = dict()
        for backup in backups:
            for backup_file_map in backup.all_files.select():
                f = backup_file_map.file
                if backup_file_map.state in (FileState.NEW, FileState.UPDATED):
                    info = BackupDatabaseReader.FileInfo(
                        backup_file_map.file, backup_file_map.state, backup
                    )
                    file_original_file[f.original_file] = info
                    file_sha[f.sha_sum] = info
                elif backup_file_map.state == FileState.DELETED:
                    del file_original_file[f.original_file]
                    del file_sha[f.sha_sum]

        return BackupDatabaseReader(file_original_file, file_sha)

    def __init__(self, file_original_file: {str: FileInfo}, file_sha: {str: FileInfo}):
        self._all_files = file_original_file
        self._all_sha = file_sha

    @property
    def all_files(self) -> {str: FileEntry}:
        ret = dict()
        for key in self._all_files:
            ret[key] = self._all_files[key].file

        return ret

    def find_sha(self, sha_sum):
        if sha_sum not in self._all_sha:
            return None

        return self._all_sha[sha_sum].file

    def find_original_file(self, original_file):
        if original_file not in self._all_files:
            return None

        return self._all_files[original_file].file

    def find_coordinates(self, file: FileEntry) -> (FileEntry, FileState, ArchiveEntry, DiscEntry, BackupEntry):
        if file.original_file not in self._all_files:
            return None, None, None, None, None

        fi = self._all_files[file.original_file]
        return fi.file, fi.state, fi.archive, fi.disc, fi.backup

    @property
    def is_empty(self) -> bool:
        return len(self._all_files) == 0


class DatabaseManager:
    # Note that the database manager is static because of the "static" proxy to peewee.database
    def __init__(self, file_name):
        if file_name is None:
            raise RuntimeError("Database file can't be None.")

        self.file_name = file_name
        self.database = database
        self.open_database(file_name)

    def transaction(self):
        return self.database.transaction()

    def open_database(self, file_name):
        self.database.initialize(SqliteDatabase(file_name, pragmas={'foreign_keys': 1}))
        self.database.connect()
        self.create_tables()

    def create_tables(self):
        with self.database:
            self.database.create_tables(
                [BackupsEntry, BackupEntry, DiscEntry, ArchiveEntry,
                 ArchiveFileMap, FileEntry, BackupFileMap]
            )

    def close_database(self):
        self.database.close()

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
            type=backup_type
        )

        return BackupDatabaseWriter(backup)

    def read_backup(self, backup) -> BackupDatabaseReader:
        """

        :param backup: Backup to start from (not implemented), None to start from the latest
        :return:
        """
        return BackupDatabaseReader.create_reader_from_backup(self.backups_root(), backup)
