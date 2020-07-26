import os
import re
import tempfile
import shutil
import logging

from backup.common.logger import configure_logger
from backup.common.util import copy_with_progress
from backup.core.luke import LukeFilewalker
from backup.core.archive import FileBulker, DefaultArchiver, ArchiveManager
from backup.core.encryptor import GpgEncryptor, Encryptor, EncryptionManager
from backup.db.db import DatabaseManager, BackupDatabaseReader, BackupType, FileState, ArchiveEntry, FileEntry, \
    DiscEntry
from backup.multi.archive import ThreadingFileBulker, ThreadingArchiveManager
from backup.db.disc_id import DiscId
from backup.multi.threadpool import ThreadPool

from backup.multi.encryptor import ThreadingEncryptionManager
from backup.multi.backpressure import BackpressureManager, NopBackpressureManager
from backup.core.parameters import GeneralSettings, BackupParameters, RestoreParameters
from backup.common.progressbar import create_pg
from backup.storage.directory import DirectoryStorageController, DirectoryStorageBackupParameters

logger = configure_logger(logging.getLogger(__name__))

NUMBER_TO_FILE_FORMAT = "%010i"


class BaseController:
    """
    Base class for restore and backup controllers
    """

    def __init__(self, general_settings: GeneralSettings):
        self.general_settings = general_settings

    def execute(self, params):
        raise RuntimeError("Please implement me.")

    def _create_archiver(self, parameters) -> DefaultArchiver:
        return DefaultArchiver()

    def _create_encryptor(self, parameters) -> GpgEncryptor:
        encryption_key = getattr(parameters, 'encryption_key', None)
        if encryption_key is None:
            return None
        return GpgEncryptor(encryption_key)

    def _find_database(self, parameters):
        db_loc = str(getattr(parameters, 'database_location', None))
        if not db_loc.startswith('/'):  # assume path is relative to destination directory
            db_loc = os.path.join(parameters.destination, db_loc)

        return db_loc

    def _valid_database_file(self, file):
        # TODO this is very primitive, but can handle encrypted databases simply.
        return os.path.exists(file) and os.path.getsize(file) > 0


class BackupController(BaseController):
    def execute(self, params: BackupParameters):
        # Init/decrypt database
        encryptor = self._create_encryptor(params)
        db_location = self._find_database(params)

        if encryptor and self._valid_database_file(db_location):
            db_tmp_file = tempfile.NamedTemporaryFile()
            encryptor.decrypt_file(db_location, db_tmp_file.name)
            db_location = db_tmp_file.name

        db = DatabaseManager(db_location)

        with db.transaction() as txn:
            backup_reader = db.read_backup(None)
            first_backup = len(backup_reader.all_files) == 0

            archive_manager, archiver, backup_db_writer, file_filter, pressure, storage \
                = self._factory(backup_reader, db, encryptor, first_backup, params)

            disc_domain = None
            for archive_package in archive_manager.archive_package_iter():
                if storage.next_medium_needed() or disc_domain is None:
                    if disc_domain is not None:  # if there is no entity, it's the first iteration
                        storage.finish_medium(params, disc_domain)  # finish previous disc

                    # create new disc
                    disc_domain = backup_db_writer.create_disc()
                    storage.create_next_medium(disc_domain)

                archive_domain = backup_db_writer.create_archive(disc_domain)
                self._update_archive_domain_from_package(archive_domain, archive_package, backup_db_writer,
                                                         backup_reader)

                archive_package.final_file_extension = archiver.extension
                if encryptor is not None:
                    archive_package.final_file_extension += ".%s" % encryptor.extension

                storage.store_archive(archive_package, disc_domain, archive_domain, pressure)

            if disc_domain is not None:  # finish last disc
                storage.finish_medium(params, disc_domain)  # -> storagecontroller

            # find out which files where deleted
            for key in backup_reader.all_files:
                file = backup_reader.all_files[key]
                fr = file.relative_file
                if fr in file_filter.filtered_files:
                    pass  # file not changed, don't record it
                elif fr not in file_filter.handled_files:
                    backup_db_writer.create_file(
                        file.sha_sum,
                        file.modified_time,
                        file.relative_file,
                        file.size,
                        FileState.DELETED
                    )

            txn.commit()

        db.close_database()
        storage.finish_backup(db, params, encryptor)

    def _factory(self, backup_reader, db, encryptor, first_backup, params):
        """Create all needed instances for the backup process"""
        calculate_sha = not params.use_threading
        if not first_backup:
            calculate_sha = True
        file_filter = FileFilter(
            backup_reader,
            LukeFilewalker().walk_directory(params.source, calculate_sha)
        )
        if backup_reader.is_empty:
            params.backup_type = BackupType.FULL
        archiver = self._create_archiver(params)
        pressure = NopBackpressureManager()
        if params.use_threading:
            pool = params.use_threading if None else ThreadPool(params.threads)
            pressure = BackpressureManager(5)
            if first_backup:
                # if first backup we can use threading, otherwise sha has to be calculated inside the walker
                file_bulker = ThreadingFileBulker(file_filter.iterator(), params.single_archive_size, pool)
            else:
                file_bulker = FileBulker(file_filter.iterator(), params.single_archive_size)
            archive_manager = ThreadingArchiveManager(file_bulker, archiver, pool, pressure)
            archive_manager = ThreadingEncryptionManager(archive_manager, encryptor, pool, pressure)
        else:
            file_bulker = FileBulker(file_filter.iterator(), params.single_archive_size)
            archive_manager = ArchiveManager(file_bulker, archiver)
            archive_manager = EncryptionManager(archive_manager, encryptor)
        backup_db_writer = db.create_backup(params.backup_type, params.backup_name)
        # TODO remove, needs to be given in from the outside
        params.backup_parameters = DirectoryStorageBackupParameters()
        # TODO create parameters and pass it
        storage = DirectoryStorageController().start_backup(params, self.general_settings)
        return archive_manager, archiver, backup_db_writer, file_filter, pressure, storage

    def _update_archive_domain_from_package(self, archive_domain, archive_package, backup_db_writer, backup_reader):
        """Maps files from the archive package to the domain (db)."""
        for file_dto in archive_package.file_package:
            # files must be new / updated. deleted files are filtered and handled later
            old_file = backup_reader.find_relative_file(file_dto.relative_file)
            state = FileState.NEW if old_file is None else FileState.UPDATED
            file_domain = backup_db_writer.create_file_from_dto(file_dto, state)
            backup_db_writer.map_file_to_archive(file_domain, archive_domain)


class RestoreController(BaseController):
    class PartialFileInfo:
        def __init__(self, relative_file, count):
            self.archive_parts = dict()
            self.relative_file = relative_file
            self.count = count

    def _filter_files(self, backup_reader: BackupDatabaseReader, file_glob):
        regex = re.compile(file_glob)

        ret = list()
        all_files = backup_reader.all_files
        for key in all_files:
            file = all_files[key]
            m = regex.match(file.relative_file)
            if m:
                ret.append(file.relative_file)

        return ret

    def _group_by_archive(self, backup_reader: BackupDatabaseReader, available_files: [str]) \
            -> {int: (ArchiveEntry, [str])}:
        """

        :param backup_reader:
        :param available_files:
        :return:  { archive.id: (archive, {original_file: part_count}) }
        """
        dict_archive = dict()
        for key in available_files:
            file, _, archives, _ = backup_reader.find_coordinates(backup_reader.find_relative_file(key))

            for archive in archives:
                if archive.id not in dict_archive:
                    dict_archive[archive.id] = [archive, dict()]

                counts = dict_archive[archive.id][1]
                relative_file = file.relative_file
                counts[relative_file] = len(archives)

        return dict_archive

    # def _create_source_locator(self, params: RestoreParameters) -> RestoreSourceLocator:
    #     return DirectorySourceLocator()

    def _convert_to_archive_path(self, params: RestoreParameters, backup_reader: BackupDatabaseReader,
                                 relative_files: [str]) -> [str]:
        ret = list()
        for relative_file in relative_files:
            file = backup_reader.find_relative_file(relative_file)
            ret.append(file.relative_file)

        return ret

    def execute(self, params: RestoreParameters):
        # Init / decrypt database
        encryptor = self._create_encryptor(params)

        db_location = self._find_database(params)
        if encryptor and self._valid_database_file(db_location) and db_location.endswith(encryptor.extension):
            db_tmp_file = tempfile.NamedTemporaryFile()
            encryptor.decrypt_file(db_location, db_tmp_file.name)
            db_location = db_tmp_file.name

        db = DatabaseManager(db_location)

        # TODO remove, needs to be given in from the outside
        params.backup_parameters = DirectoryStorageBackupParameters()
        # TODO create parameters and pass it
        storage = DirectoryStorageController().start_restore(self.general_settings, params)
        # source_locator = self._create_source_locator(params)

        with db.transaction() as txn:
            backup_reader = db.read_backup(None)

            restore_files = self._filter_files(backup_reader, params.restore_glob)
            archiver = self._create_archiver(params)
            archive_ext = archiver.extension
            if encryptor:
                archive_ext = archive_ext + ".%s" % encryptor.extension

            # TODO:
            # Make sure that if a file is in multiple archives, that all available other files are restored first. Why?
            # Because the file (1:n) could cause a volume/tape change and a change back to restore the other files.

            partial_restored_files = dict()
            endless_loop_counter = len(restore_files) * 10
            while len(restore_files) > 0:
                available_files, list_of_archives = storage.available_sources(backup_reader, restore_files, archive_ext)
                file_map = self._group_by_archive(backup_reader, available_files)

                for archive_id in file_map:  # ( archive.id, [relative_file] )
                    archive_entry, relative_files_count = file_map[archive_id]  # archive, {relative_file: part_count}

                    archive_path = list_of_archives[archive_id]
                    # Files can occur in multiple archives, check if this archive is available
                    if os.path.exists(archive_path):
                        relative_files = self._convert_to_archive_path(params, backup_reader,
                                                                       relative_files_count.keys())
                        self._decrypt_and_decompress(archive_path, archiver, params, relative_files,
                                                     encryptor)  # -> storagecontroller??

                        # if the file is a partial file, we need to move it to the temp directory and mark it as such
                        # do not remove it from restore_files, as we need the other parts, before quitting
                        for relative_file in relative_files_count:
                            count = relative_files_count[relative_file]
                            if count > 1:
                                # these files need special handling, as they have multiple parts
                                if relative_file not in partial_restored_files:
                                    partial_restored_files[relative_file] = \
                                        RestoreController.PartialFileInfo(relative_file, count)

                                prf = partial_restored_files[relative_file]
                                tmp_file = tempfile.NamedTemporaryFile()
                                prf.archive_parts[archive_entry] = tmp_file

                                file = backup_reader.find_relative_file(relative_file)
                                shutil.move(params.destination + os.sep + file.relative_file, tmp_file.name)

                        for relative_file in relative_files_count:
                            count = relative_files_count[relative_file]

                            if count == 1:
                                restore_files.remove(relative_file)
                            else:
                                if len(partial_restored_files[relative_file].archive_parts) == count:
                                    # all parts have been assembled, join file
                                    self._finish_parts(params, partial_restored_files[relative_file],
                                                       backup_reader.find_relative_file(relative_file))
                                    restore_files.remove(relative_file)

                if endless_loop_counter <= 0:
                    raise RuntimeError("Too many iterations while restoring, files left: <%s>" % restore_files)
                endless_loop_counter -= 1

            txn.rollback()

        db.close_database()
        # TODO sanity check for the restored files?

    def _decrypt_and_decompress(self, archive_path, archiver, params, relative_files, encryptor: Encryptor):
        with tempfile.NamedTemporaryFile() as decrypted_file:
            src_archive = archive_path
            if encryptor:
                encryptor.decrypt_file(src_archive, decrypted_file.name)
                src_archive = decrypted_file.name

            archiver.decompress_files(src_archive, relative_files, params.destination)

    def _finish_parts(self, params: RestoreParameters, partial: PartialFileInfo, file: FileEntry):
        archives = partial.archive_parts.keys()
        sorted_archives = sorted(archives, key=lambda a: a.id)

        output_file_path = params.destination + os.sep + file.relative_file
        for archive in sorted_archives:
            tmp_file = partial.archive_parts[archive]
            self._join_files(output_file_path, tmp_file.name)
            tmp_file.close()

    def _join_files(self, dest_path, src_path, buffer=1024):
        with open(dest_path, 'ab') as dest:
            with open(src_path, 'rb') as src:
                while True:
                    data = src.read(buffer)
                    if data:
                        dest.write(data)
                    else:
                        return


class FileFilter:
    """
    Filters file location or sha sum and excludes it from backup if it was backuped since the last full backup.
    """

    def __init__(self, backup_reader: BackupDatabaseReader, file_iterator):
        self._backup_reader = backup_reader
        self._file_iterator = file_iterator
        self.filtered_files = dict()
        self.handled_files = dict()

    def iterator(self):
        br = self._backup_reader
        for file in self._file_iterator:
            fp = br.find_relative_file(file.relative_file)

            fs = False
            if fp:
                fs = fp.sha_sum == file.sha_sum

            if fp and fs:
                self.filtered_files[file.relative_file] = file
                continue

            self.handled_files[file.relative_file] = file
            yield file
