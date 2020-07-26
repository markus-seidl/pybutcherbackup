from backup.core.encryptor import GpgEncryptor
from backup.core.parameters import BackupParameters, GeneralSettings, RestoreParameters
from backup.db.db import DatabaseManager, BackupDatabaseReader
from backup.db.domain import DiscEntry


class BaseBackupStorageController:
    def __init__(self):
        self._medium_open = False

    def next_medium_needed(self):
        """Returns true if a new medium has to be created. If true, a call to store_archive is not allowed but
        finish_medium should be called. """
        pass

    def finish_medium(self, parameters, disc_domain: DiscEntry):
        """Close the current medium. Has to be called before finish_backup. Empty mediums (not a single call to
        store_archive) should remove the medium information."""
        self._medium_open = False

    def store_archive(self, archive_package, disc_domain, archive_domain, pressure):
        """Store the archive on the medium. It's up to the implementer if this or the finish medium/backup actually
        stores the data."""
        assert self._medium_open

    def create_next_medium(self, disc_domain: DiscEntry):
        """Executed to indicate that a new medium might(!) be needed."""
        self._medium_open = True

    def finish_backup(self, db: DatabaseManager, params: BackupParameters, encryptor: GpgEncryptor):
        """Finish up the backup after all archives are stored."""
        self._medium_open = False


class BaseRestoreStorageController:
    def available_sources(self, backup_reader: BackupDatabaseReader, restore_files: [str],
                          ext) -> [str]:
        pass


class BaseStorageController:
    def start_backup(self, params: BackupParameters, general_settings: GeneralSettings) -> BaseBackupStorageController:
        pass

    def start_restore(self, general_settings: GeneralSettings, params: RestoreParameters) -> BaseRestoreStorageController:
        pass
