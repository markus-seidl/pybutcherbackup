from peewee import SqliteDatabase

from db.domain import database, BackupsEntry, BackupEntry, DiscEntry, ArchiveEntry, ArchiveFileMap, FileEntry, \
    BackupFileMap


class BackupDatabaseWriter:
    def __init__(self, backup_root):
        self.backup_root = backup_root
        self.files = dict()
        """Map of all registered files (relative_path, FileEntry)"""
        self.archive_number = 0
        """Number of registered archives."""
        self.disc_number = 0
        """Number of registered discs."""

    def create_file(self, original_filepath,
                    original_filename,
                    sha_sum,
                    modified_time,
                    relative_path,
                    size) -> FileEntry:
        # Prevent duplication of files
        if relative_path in self.files:
            return self.get_file(relative_path)

        file = FileEntry.create(
            original_filepath=original_filepath,
            original_filename=original_filename,
            sha_sum=sha_sum,
            modified_time=modified_time,
            relative_path=relative_path,
            size=size,
            archive_map=None,
            backup=None
        )

        self.files[relative_path] = file

        # automagically add this file to the backup
        # TODO is this ok or should this be in another function?
        BackupFileMap.create(
            backup=self.backup_root,
            file=file
        )

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

    def map_file_to_archive(self, file, archive):
        return ArchiveFileMap.create(
            archive=archive,
            file=file
        )

    def map_file_to_backup(self, file, backup):
        return BackupFileMap.create(
            backup=self.backup_root,
            file=file
        )


class BackupDatabaseReader:
    pass


# Note that the database manager is static because of the static proxy to peewee.database
class DatabaseManager:
    def __init__(self, file_name):
        self.file_name = file_name
        self.database = database
        self.open_database(file_name)

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
            pass
        else:
            return s.first()

    def create_backup(self) -> BackupDatabaseWriter:
        backup = BackupEntry.create(
            backups=self.backups_root()
        )

        return BackupDatabaseWriter(backup)
