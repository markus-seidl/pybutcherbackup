import os
import re
import tempfile
import shutil
import logging
import multiprocessing

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
from tqdm import tqdm

from backup.multi.encryptor import ThreadingEncryptionManager

DEFAULT_DATABASE_FILENAME = "index.sqlite"

logger = configure_logger(logging.getLogger(__name__))

NUMBER_TO_FILE_FORMAT = "%010i"


class GeneralSettings:
    def __init__(self):
        self.database_name = DEFAULT_DATABASE_FILENAME
        self.index_filename = "disc_id.yml"


class BackupParameters:
    def __init__(self):
        self.database_location = "./" + DEFAULT_DATABASE_FILENAME
        self.source = None
        self.destination = None
        self.single_archive_size = 1024 * 1024 * 1024  # 1 GB
        """Single Archive size in bytes"""
        self.disc_size = 1024 * 1024 * 1024 * 44  # 44 GB
        """Size of one backup disc"""
        self.backup_type = BackupType.INCREMENTAL
        self.encryption_key = None
        self.use_threading = False
        self.threads = multiprocessing.cpu_count() / 2


class RestoreParameters:
    def __init__(self):
        self.database_location = "./" + DEFAULT_DATABASE_FILENAME
        self.source = None
        self.destination = None
        self.encryption_key = None
        self.restore_glob = ".*"


class BaseController:
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
        encryptor = self._create_encryptor(params)
        db_location = self._find_database(params)

        pool = params.use_threading if None else ThreadPool(params.threads)
        if encryptor and self._valid_database_file(db_location):
            db_tmp_file = tempfile.NamedTemporaryFile()
            encryptor.decrypt_file(db_location, db_tmp_file.name)
            db_location = db_tmp_file.name

        db = DatabaseManager(db_location)

        disc_directories = list()
        disc_directory = None
        with db.transaction() as txn:
            backup_reader = db.read_backup(None)
            first_backup = len(backup_reader.all_files) == 0

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
            if params.use_threading:
                if first_backup:
                    # if first backup we can use threading, otherwise sha has to be calculated inside the walker
                    file_bulker = ThreadingFileBulker(file_filter.iterator(), params.single_archive_size, pool)
                else:
                    file_bulker = FileBulker(file_filter.iterator(), params.single_archive_size)
                archive_manager = ThreadingArchiveManager(file_bulker, archiver, pool)
                archive_manager = ThreadingEncryptionManager(archive_manager, encryptor, pool)
            else:
                file_bulker = FileBulker(file_filter.iterator(), params.single_archive_size)
                archive_manager = ArchiveManager(file_bulker, archiver)
                archive_manager = EncryptionManager(archive_manager, encryptor)

            backup_writer = db.create_backup(params.backup_type)

            disc_domain = None
            disc_size = -1
            for archive_package in archive_manager.archive_package_iter():
                if disc_size >= params.disc_size or disc_domain is None:
                    if disc_domain is not None:  # if there is no entity, it's the first iteration
                        # finish previous disc
                        self._finish_disc(params, disc_directory, disc_domain)

                    # create new disc
                    disc_domain = backup_writer.create_disc()
                    disc_directory = self._create_disc_dir(params, disc_domain)
                    disc_directories.append(disc_directory)
                    disc_size = 0

                archive_domain = backup_writer.create_archive(disc_domain)
                for file_dto in archive_package.file_package:
                    # files must be new / updated. deleted files are filtered and handled later
                    old_file = backup_reader.find_relative_file(file_dto.relative_file)
                    state = FileState.NEW if old_file is None else FileState.UPDATED
                    file_domain = backup_writer.create_file_from_dto(file_dto, state)
                    backup_writer.map_file_to_archive(file_domain, archive_domain)

                archive_name = self._create_archive_name(params, disc_domain, archive_domain)
                final_archive_name = self._copy(archive_package, archiver, encryptor, archive_name)

                self._update_archive(archive_domain, final_archive_name)
                disc_size += self._get_size(final_archive_name)

            if disc_domain is not None:  # finish last disc
                self._finish_disc(params, disc_directory, disc_domain)

            # find out which files where deleted
            for key in backup_reader.all_files:
                file = backup_reader.all_files[key]
                fr = file.relative_file
                if fr in file_filter.filtered_files:
                    pass  # file not changed, don't record it
                elif fr not in file_filter.handled_files:
                    backup_writer.create_file(
                        file.sha_sum,
                        file.modified_time,
                        file.relative_file,
                        file.size,
                        FileState.DELETED
                    )

            txn.commit()

        db.close_database()
        self._finish_backup(db, params, disc_directories, encryptor)

    def _copy(self, archive_package, archiver, encryptor, archive_name):
        """Copy it to the destination."""

        assert os.path.exists(archive_package.archive_file)

        archive_name += ".%s" % archiver.extension
        final_archive_name = archive_name
        src_file = archive_package.archive_file
        if encryptor is not None:
            final_archive_name = archive_name + ".%s" % encryptor.extension

        with tqdm(total=-1, leave=False, unit='B', unit_scale=True, unit_divisor=1024) as t:
            t.set_description('Copy archive to destination')
            copy_with_progress(src_file, final_archive_name, t)

        temp_file = getattr(archive_package, "tempfile", None)
        if temp_file:
            temp_file.close()  # empty the temporary directory

        return final_archive_name

    def _update_archive(self, archive_domain, final_archive_name):
        base_name = os.path.basename(final_archive_name)
        archive_domain.name = base_name
        archive_domain.save()

    def _get_size(self, file):
        return os.stat(file).st_size

    def _create_disc_name(self, parameters, disc_domain):
        return parameters.destination + os.sep + NUMBER_TO_FILE_FORMAT % disc_domain.id

    def _create_archive_name(self, parameters, disc_domain, archive_domain):
        d = self._create_disc_name(parameters, disc_domain)
        return d + os.sep + NUMBER_TO_FILE_FORMAT % archive_domain.id

    def _create_disc_dir(self, parameters, disc_domain):
        disc_dir = self._create_disc_name(parameters, disc_domain)
        os.mkdir(disc_dir)
        return disc_dir

    def _finish_disc(self, parameters, disc_directory: str, disc_domain: DiscEntry):
        out_file = disc_directory + os.sep + self.general_settings.index_filename
        DiscId(disc_domain.id).serialize(out_file)

    def _finish_backup(self, db: DatabaseManager, params: BackupParameters, disc_dirs: list, encryptor: GpgEncryptor):
        db_file = db.file_name

        ext = ""
        db_tmp_file = None
        if encryptor:
            db_tmp_file = tempfile.NamedTemporaryFile()
            encryptor.encrypt_file(db_file, db_tmp_file.name)
            db_file = db_tmp_file.name
            ext = "." + encryptor.extension

        for disc in disc_dirs:
            shutil.copy(db_file, disc + os.sep + self.general_settings.database_name + ext)

        if db_tmp_file:
            db_tmp_file.close()


class RestoreSourceLocator:
    def available_sources(self, params: RestoreParameters, backup_reader: BackupDatabaseReader,
                          restore_files: [str], ext) -> [str]:
        raise RuntimeError("Implement me")

    def find_archive(self, params: RestoreParameters, backup_reader: BackupDatabaseReader, archive: ArchiveEntry, ext) \
            -> str:
        raise RuntimeError("Implement me")


class DirectorySourceLocator(RestoreSourceLocator):

    def _create_disc_name(self, parameters, disc_domain):  # TODO this is duplicated to backupcontroller, rename to path
        return parameters.source + os.sep + NUMBER_TO_FILE_FORMAT % disc_domain.id

    def _create_archive_name(self, parameters, disc_domain, archive_domain, ext):
        # TODO this is duplicated to backupcontroller, rename to path
        d = self._create_disc_name(parameters, disc_domain)
        return d + os.sep + NUMBER_TO_FILE_FORMAT % archive_domain.id + (".%s" % ext)

    @staticmethod
    def try_parse_int(value):
        try:
            return int(value), True
        except ValueError:
            return value, False

    def available_sources(self, params: RestoreParameters, backup_reader: BackupDatabaseReader, restore_files: [str],
                          ext) -> [str]:
        """Every archive file name is like an ID. Try to find it in the specified directory or subdirectories."""

        all_files = dict()
        for subdir, dirs, files in os.walk(params.source):
            for file in files:
                if file.endswith(ext):
                    # extract id from file name
                    pos_id, could_parse = self.try_parse_int(file[:-len(ext) - 1])

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
        return self._create_archive_name(params, archive.disc, archive, ext)


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

    def _create_source_locator(self, params: RestoreParameters) -> RestoreSourceLocator:
        return DirectorySourceLocator()

    def _convert_to_archive_path(self, params: RestoreParameters, backup_reader: BackupDatabaseReader,
                                 relative_files: [str]) -> [str]:
        ret = list()
        for relative_file in relative_files:
            file = backup_reader.find_relative_file(relative_file)
            ret.append(file.relative_file)

        return ret

    def execute(self, params: RestoreParameters):
        encryptor = self._create_encryptor(params)

        db_location = self._find_database(params)
        if encryptor and self._valid_database_file(db_location) and db_location.endswith(encryptor.extension):
            db_tmp_file = tempfile.NamedTemporaryFile()
            encryptor.decrypt_file(db_location, db_tmp_file.name)
            db_location = db_tmp_file.name

        db = DatabaseManager(db_location)

        with db.transaction() as txn:
            backup_reader = db.read_backup(None)

            restore_files = self._filter_files(backup_reader, params.restore_glob)
            source_locator = self._create_source_locator(params)
            archiver = self._create_archiver(params)
            archive_ext = archiver.extension
            if encryptor:
                archive_ext = archive_ext + ".%s" % encryptor.extension

            partial_restored_files = dict()
            endless_loop_counter = len(restore_files) * 10
            while len(restore_files) > 0:
                available_files, list_of_archives = source_locator.available_sources(params, backup_reader,
                                                                                     restore_files, archive_ext)
                file_map = self._group_by_archive(backup_reader, available_files)

                for archive_id in file_map:  # ( archive.id, [relative_file] )
                    archive_entry, relative_files_count = file_map[archive_id]  # archive, {relative_file: part_count}

                    archive_path = list_of_archives[archive_id]
                    # Files can occur in multiple archives, check if this archive is available
                    if os.path.exists(archive_path):
                        relative_files = self._convert_to_archive_path(params, backup_reader,
                                                                       relative_files_count.keys())
                        self._decrypt_and_decompress(archive_path, archiver, params, relative_files, encryptor)

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
