import os

from backup.core.luke import LukeFilewalker
from backup.core.archive import FileBulker, DefaultArchiver
from backup.core.encryptor import GpgEncryptor
from backup.db.db import DatabaseManager, BackupDatabaseReader, BackupType, FileState


class GeneralSettings:
    pass


class BackupParameters:
    def __init__(self):
        self.database_location = "./index.sqlite"
        self.source = None
        self.destination = None
        self.calculate_sha = True
        self.single_archive_size = 1024 * 1024 * 1024  # 1 GB
        """Single Archive size in bytes"""
        self.disc_size = 1024 * 1024 * 1024 * 40  # 40 GB
        """Size of one backup disc"""
        self.backup_type = BackupType.DIFFERENTIAL
        self.encryption_key = None


class RestoreParameters:
    def __init__(self):
        self.database_location = "./index.sqlite"
        self.source = None
        self.destination = None
        self.encryption_key = None
        self.restore_glob = ".*"


class BaseController:
    def __init__(self, settings: GeneralSettings):
        self.settings = settings

    def execute(self, params):
        raise RuntimeError("Please implement me.")

    def _create_archiver(self, parameters):
        return DefaultArchiver()

    def _create_encryptor(self, parameters):
        if parameters.encryption_key is None:
            return None
        return GpgEncryptor(parameters.encryption_key)

    def _find_database(self, parameters):
        return getattr(parameters, 'database_location', None)


class BackupController(BaseController):
    def execute(self, params: BackupParameters):
        db = DatabaseManager(self._find_database(params))

        with db.transaction() as txn:
            backup_reader = db.read_backup(None)
            file_filter = FileFilter(
                backup_reader,
                LukeFilewalker().walk_directory(params.source, params.calculate_sha)
            )
            if backup_reader.is_empty:
                params.backup_type = BackupType.FULL

            file_bulker = FileBulker(file_filter.iterator(), params.single_archive_size)

            archiver = self._create_archiver(params)
            encryptor = self._create_encryptor(params)

            backup_writer = db.create_backup(params.backup_type)

            disc_domain = None
            disc_size = -1
            for file_package in file_bulker.file_package_iter():
                if disc_size >= params.disc_size or disc_domain is None:
                    if disc_domain is not None:  # if there is no entity, it's the first iteration
                        # finish previous disc
                        self._burn_disc(params)

                    # create new disc
                    disc_domain = backup_writer.create_disc()
                    self._create_disc_dir(params, disc_domain)

                archive_domain = backup_writer.create_archive(disc_domain)
                for file_dto in file_package:
                    # files must be new / updated. deleted files are filtered and handled later
                    old_file = backup_reader.find_original_file(file_dto.original_file())
                    state = FileState.NEW if old_file is None else FileState.UPDATED
                    file_domain = backup_writer.create_file_from_dto(file_dto, state)
                    backup_writer.map_file_to_archive(file_domain, archive_domain)

                archive_name = self._create_archive_name(params, disc_domain, archive_domain)
                archive_name += ".%s" % archiver.extension

                archiver.compress_files(file_package, archive_name)

                final_archive_name = archive_name
                if encryptor is not None:
                    final_archive_name = archive_name + ".%s" % encryptor.extension
                    encryptor.encrypt_file(archive_name, final_archive_name)

                self._update_archive(archive_domain, final_archive_name)
                disc_size += self._get_size(final_archive_name)

            for file_dto in file_filter.filtered_files:
                old_file = backup_reader.find_original_file(file_dto.original_path())
                if old_file is not None:
                    raise RuntimeError("Internal error.")

                backup_writer.create_file_from_dto(file_dto, FileState.DELETED)

            txn.commit()

        db.close_database()

    def _update_archive(self, archive_domain, final_archive_name):
        base_name = os.path.basename(final_archive_name)
        archive_domain.name = base_name
        archive_domain.save()

    def _get_size(self, file):
        return os.stat(file).st_size

    def _create_disc_name(self, parameters, disc_domain):
        return parameters.destination + os.sep + "%05i" % disc_domain.number

    def _create_disc_dir(self, parameters, disc_domain):
        os.mkdir(self._create_disc_name(parameters, disc_domain))

    def _create_archive_name(self, parameters, disc_domain, archive_domain):
        d = self._create_disc_name(parameters, disc_domain)
        return d + os.sep + "%05i" % archive_domain.number

    def _burn_disc(self, parameters):
        pass


class RestoreController(BaseController):
    def execute(self, params: RestoreParameters):
        db = DatabaseManager(self._find_database(params))

        with db.transaction() as txn:
            backup_reader = db.read_backup(None)

        #     file_bulker = FileBulker(file_filter.iterator(), params.single_archive_size)
        #
        #     archiver = self._create_archiver(params)
        #     encryptor = self._create_encryptor(params)
        #
        #     backup_writer = db.create_backup(params.backup_type)
        #
        #     disc_domain = None
        #     disc_size = -1
        #     for file_package in file_bulker.file_package_iter():
        #         if disc_size >= params.disc_size or disc_domain is None:
        #             if disc_domain is not None:  # if there is no entity, it's the first iteration
        #                 # finish previous disc
        #                 self._burn_disc(params)
        #
        #             # create new disc
        #             disc_domain = backup_writer.create_disc()
        #             self._create_disc_dir(params, disc_domain)
        #
        #         archive_domain = backup_writer.create_archive(disc_domain)
        #         for file_dto in file_package:
        #             # files must be new / updated. deleted files are filtered and handled later
        #             old_file = backup_reader.find_original_path(file_dto.original_file())
        #             state = FileState.NEW if old_file is None else FileState.UPDATED
        #             file_domain = backup_writer.create_file_from_dto(file_dto, state)
        #             backup_writer.map_file_to_archive(file_domain, archive_domain)
        #
        #         archive_name = self._create_archive_name(params, disc_domain, archive_domain)
        #         archive_name += ".%s" % archiver.extension
        #
        #         archiver.compress_files(file_package, archive_name)
        #
        #         final_archive_name = archive_name
        #         if encryptor is not None:
        #             final_archive_name = archive_name + ".%s" % encryptor.extension
        #             encryptor.encrypt_file(archive_name, final_archive_name)
        #
        #         self._update_archive(archive_domain, final_archive_name)
        #         disc_size += self._get_size(final_archive_name)
        #
        #     for file_dto in file_filter.filtered_files:
        #         old_file = backup_reader.find_original_path(file_dto.original_path())
        #         if old_file is not None:
        #             raise RuntimeError("Internal error.")
        #
        #         backup_writer.create_file_from_dto(file_dto, FileState.DELETED)
        #
        #     txn.commit()
        #
        # db.close_database()


class FileFilter:
    """
    Filters file location or sha sum and excludes it from backup if it was backuped since the last full backup.
    """

    def __init__(self, backup_reader: BackupDatabaseReader, file_iterator):
        self._backup_reader = backup_reader
        self._file_iterator = file_iterator
        self.filtered_files = list()

    def iterator(self):
        br = self._backup_reader
        for file in self._file_iterator:
            fp = br.find_original_file(file.original_path)

            if file.sha_sum is not None:
                fs = br.find_sha(file.sha_sum)
            else:
                fs = False

            if fp or fs:
                self.filtered_files.append(file)
                continue

            yield file
