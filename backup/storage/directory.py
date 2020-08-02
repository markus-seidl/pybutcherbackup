import os
import tempfile
import shutil

from backup.common.hookhelper import HookHelper
from backup.common.progressbar import create_pg
from backup.common.util import copy_with_progress, try_parse_int
from backup.core.encryptor import GpgEncryptor
from backup.core.parameters import BackupParameters, GeneralSettings, RestoreParameters
from backup.db.db import DatabaseManager, BackupDatabaseReader
from backup.db.disc_id import DiscId
from backup.db.domain import DiscEntry, ArchiveEntry
from backup.storage.base import BaseStorageController
from backup.storage.base import BaseRestoreStorageController, BaseBackupStorageController

NUMBER_TO_FILE_FORMAT = "%010i"


def _create_disc_name(parameters, disc_domain):
    return parameters.destination + os.sep + NUMBER_TO_FILE_FORMAT % disc_domain.id


def _create_archive_name(parameters, disc_domain, archive_domain):
    d = _create_disc_name(parameters, disc_domain)
    return d + os.sep + NUMBER_TO_FILE_FORMAT % archive_domain.id


def _create_disc_dir(parameters, disc_domain):
    disc_dir = _create_disc_name(parameters, disc_domain)
    os.mkdir(disc_dir)
    return disc_dir


class DirectoryStorageBackupParameters:
    def __init__(self):
        self.medium_size = 1024 * 1024 * 1024 * 44  # 44 GB
        """Size of one directory. Can be -1 = unlimited"""

        # TODO add database size to this slack by default, so the index can be stored in each medium/dir
        self.slack_size = 1024 * 100  # 100 MB
        """The amount of space that is always left empty in each single medium/directory"""


class BackupDirectoryStorageController(BaseBackupStorageController):
    def __init__(self, parameters: BackupParameters, general_settings: GeneralSettings):
        super(BackupDirectoryStorageController, self).__init__()
        self._current_medium_size = 0
        self._parameters = parameters
        parameters.backup_parameters = parameters.backup_parameters or DirectoryStorageBackupParameters()  # TODO remove
        self._general_settings = general_settings
        self._hook_helper = HookHelper(general_settings)
        self.disc_directories = list()
        self.disc_directory = None

    def next_medium_needed(self) -> bool:
        bp = self._parameters.backup_parameters

        if bp.medium_size < 0:
            return True
        return self._current_medium_size + bp.slack_size >= bp.medium_size

    def finish_medium(self, parameters, disc_domain: DiscEntry):
        super(BackupDirectoryStorageController, self).finish_medium(parameters, disc_domain)
        out_file = self.disc_directory + os.sep + self._general_settings.index_filename
        DiscId(disc_domain.id).serialize(out_file)

        self._hook_helper.execute_hook("finish_medium", [_create_disc_name(parameters, disc_domain)])

        # TODO REMOVE
        if self._general_settings.dummy:
            input("Insert next medium - waiting")

    def store_archive(self, archive_package, disc_domain, archive_domain, pressure):
        super(BackupDirectoryStorageController, self).store_archive(archive_package, disc_domain, archive_domain,
                                                                    pressure)
        archive_name = _create_archive_name(self._parameters, disc_domain, archive_domain)

        assert os.path.exists(archive_package.archive_file)

        src_file = archive_package.archive_file
        final_archive_name = archive_name + "." + archive_package.final_file_extension

        with create_pg(total=-1, leave=False, unit='B', unit_scale=True, unit_divisor=1024,
                       desc='Copy archive to destination') as t:
            copy_with_progress(src_file, final_archive_name, t)
            pressure.unregister_pressure()

        temp_file = getattr(archive_package, "tempfile", None)
        if temp_file:
            temp_file.close()  # empty the temporary directory

        archive_domain.name = os.path.basename(final_archive_name)
        archive_domain.save()

        self._current_medium_size += self._get_size(final_archive_name)

    def _get_size(self, file):
        return os.stat(file).st_size

    def create_next_medium(self, disc_domain: DiscEntry):
        super(BackupDirectoryStorageController, self).create_next_medium(disc_domain)
        self.disc_directory = _create_disc_dir(self._parameters, disc_domain)
        self.disc_directories.append(self.disc_directory)
        self._current_medium_size = 0

    def finish_backup(self, db: DatabaseManager, params: BackupParameters, encryptor: GpgEncryptor):
        super(BackupDirectoryStorageController, self).finish_backup(db, params, encryptor)
        db_file = db.file_name

        ext = ""
        db_tmp_file = None
        if encryptor:
            db_tmp_file = tempfile.NamedTemporaryFile()
            encryptor.encrypt_file(db_file, db_tmp_file.name)
            db_file = db_tmp_file.name
            ext = "." + encryptor.extension

        for disc in self.disc_directories:
            shutil.copy(db_file, disc + os.sep + self._general_settings.database_name + ext)

        if db_tmp_file:
            db_tmp_file.close()


class BackupDirectoryRestoreController(BaseRestoreStorageController):
    def __init__(self, general_settings: GeneralSettings, parameters: RestoreParameters):
        self._parameters = parameters
        self._general_settings = general_settings
        self._hook_helper = HookHelper(general_settings)

    def available_sources(self, backup_reader: BackupDatabaseReader, restore_files: [str],
                          ext) -> [str]:
        # Every archive file name is like an ID. Try to find it in the specified directory or subdirectories.

        all_files = dict()
        for subdir, dirs, files in os.walk(self._parameters.source):
            for file in files:
                if file.endswith(ext):
                    # extract id from file name
                    pos_id, could_parse = try_parse_int(file[:-len(ext) - 1])

                    if could_parse:
                        f = os.path.join(subdir, file)
                        all_files[pos_id] = f

        found_files = list()
        for relative_file in restore_files:
            file, state, archives, backup = backup_reader.find_coordinates(
                backup_reader.find_relative_file(relative_file)
            )

            found_all = True
            for archive in archives:
                found_all = found_all and archive.id in all_files

            if found_all:
                found_files.append(relative_file)
            else:
                print(relative_file)

        return found_files, all_files

    def find_archive(self, params: RestoreParameters, backup_reader: BackupDatabaseReader, archive: ArchiveEntry, ext) \
            -> str:
        return _create_archive_name(params, archive.disc, archive)


class DirectoryStorageController(BaseStorageController):
    """
    Represents one directory where all the data will be stored into. This could be in one single or multiple
    sub-directories. This is the most flexible, as the user can then backup each directory as it sees fit.
    """

    def start_backup(self, params: BackupParameters,
                     general_settings: GeneralSettings) -> BackupDirectoryStorageController:
        return BackupDirectoryStorageController(params, general_settings)

    def start_restore(self, general_settings: GeneralSettings,
                      parameters: RestoreParameters) -> BaseRestoreStorageController:
        return BackupDirectoryRestoreController(general_settings, parameters)
