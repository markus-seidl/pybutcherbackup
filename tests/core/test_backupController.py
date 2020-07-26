from unittest import TestCase
import os, tempfile
from backup.common.dircompare import DirCompare
from backup.core.basecontroller import BackupController, RestoreController
from backup.core.parameters import GeneralSettings, BackupParameters, RestoreParameters
from backup.db.db import DatabaseManager
from common.customtestcase import CustomTestCase


class TestBackupRestoreController(CustomTestCase):
    def create_test_file(self, name, first_line_content, size=1024):
        with open(name, 'w') as temp:
            temp.write("%i" % first_line_content)
            temp.write(os.linesep)

            for i in range(size):
                temp.write("a")

    def create_sourceStructure(self, directory, amount) -> list:
        ret = list()
        file_idx = 0
        for i in range(amount[0]):  # directories
            dir_name = directory + os.sep + "src_dir_%05i" % i
            os.mkdir(dir_name)

            for ii in range(amount[1]):  # files per directory
                file_name = dir_name + os.sep + "src_file_%05i" % ii
                self.create_test_file(file_name, file_idx)

                ret.append(file_name)

                file_idx += 1

        return ret

    def test_backup_00(self):
        """ Backup -> read database """
        bck_params = BackupParameters()

        with tempfile.NamedTemporaryFile() as db_filename:
            with tempfile.TemporaryDirectory() as destination_dir:
                with tempfile.TemporaryDirectory() as source_dir:
                    bck_params.database_location = db_filename.name
                    bck_params.source = source_dir
                    bck_params.destination = destination_dir

                    # Every archive will be one(1) disc.
                    bck_params.single_archive_size = 1050
                    bck_params.disc_size = bck_params.single_archive_size

                    src_file_list = self.create_sourceStructure(source_dir, [10, 10])
                    ctrl = BackupController(GeneralSettings())

                    # Preparations complete start backup...
                    ctrl.execute(bck_params)
                    # ... backup ended.

                    db = DatabaseManager(db_filename.name)
                    backup_reader = db.read_backup(None)

                    for file in src_file_list:
                        relative_file = file[len(bck_params.database_location):]
                        test = backup_reader.find_relative_file(relative_file)
                        assert test is not None

    def test_backup_01(self):
        """ Backup -> validate backup structure (unencrypted) """
        bck_params = BackupParameters()
        expected_extensions = ['tar.bz2', 'sqlite', 'yml']

        with tempfile.NamedTemporaryFile() as db_filename:
            with tempfile.TemporaryDirectory() as destination_dir:
                with tempfile.TemporaryDirectory() as source_dir:
                    bck_params.database_location = db_filename.name
                    bck_params.source = source_dir
                    bck_params.destination = destination_dir

                    # Every archive will be one(1) disc.
                    bck_params.single_archive_size = 1050
                    bck_params.disc_size = bck_params.single_archive_size

                    src_file_list = self.create_sourceStructure(source_dir, [10, 10])
                    ctrl = BackupController(GeneralSettings())

                    # Preparations complete start backup...
                    ctrl.execute(bck_params)
                    # ... backup ended.

                    for subdir, dirs, files in os.walk(destination_dir):
                        for file in files:
                            ok = False
                            for ext in expected_extensions:
                                if file.endswith(ext):
                                    ok = True
                                    break

                            assert ok, "Found file that was not expected <%s>" % file

    def test_backup_02(self):
        """ Backup -> validate backup structure (encrypted) """
        bck_params = BackupParameters()
        bck_params.encryption_key = "encrypt me hard!"
        expected_extensions = ['tar.bz2.gpg', 'sqlite.gpg', 'yml']

        with tempfile.NamedTemporaryFile() as db_filename:
            with tempfile.TemporaryDirectory() as destination_dir:
                with tempfile.TemporaryDirectory() as source_dir:
                    bck_params.database_location = db_filename.name
                    bck_params.source = source_dir
                    bck_params.destination = destination_dir

                    # Every archive will be one(1) disc.
                    bck_params.single_archive_size = 1050
                    bck_params.disc_size = bck_params.single_archive_size

                    src_file_list = self.create_sourceStructure(source_dir, [10, 10])
                    ctrl = BackupController(GeneralSettings())

                    # Preparations complete start backup...
                    ctrl.execute(bck_params)
                    # ... backup ended.

                    for subdir, dirs, files in os.walk(destination_dir):
                        for file in files:
                            ok = False
                            for ext in expected_extensions:
                                if file.endswith(ext):
                                    ok = True
                                    break

                            assert ok, "Found file that was not expected <%s>" % file

    def do_backup_for_configuration(self, bck_params):
        with tempfile.NamedTemporaryFile() as db_filename:
            with tempfile.TemporaryDirectory() as destination_dir:
                with tempfile.TemporaryDirectory() as source_dir:
                    bck_params.database_location = db_filename.name
                    bck_params.source = source_dir
                    bck_params.destination = destination_dir

                    src_file_list = self.create_sourceStructure(source_dir, [10, 10])
                    ctrl = BackupController(GeneralSettings())

                    # Preparations complete start backup...
                    ctrl.execute(bck_params)
                    # ... backup ended.

                    with tempfile.TemporaryDirectory() as restore_dir:
                        rst_params = RestoreParameters()
                        rst_params.database_location = db_filename.name
                        rst_params.source = destination_dir
                        rst_params.destination = restore_dir
                        rst_params.encryption_key = bck_params.encryption_key

                        ctrl = RestoreController(GeneralSettings())
                        ctrl.execute(rst_params)

                        assert DirCompare(source_dir, restore_dir).compare()

    def test_full_backup_00(self):
        """ Backup -> Restore -> check result """
        bck_params = BackupParameters()
        # Every archive will be one(1) disc.
        bck_params.single_archive_size = 1050
        bck_params.disc_size = bck_params.single_archive_size

        self.do_backup_for_configuration(bck_params)

    def test_full_backup_01(self):
        """ Backup (with many fragmented files) -> Restore -> check result """
        bck_params = BackupParameters()
        # Every archive will be one(1) disc.
        bck_params.single_archive_size = 200  # this ensures that each file will have multiple archives
        bck_params.disc_size = bck_params.single_archive_size

        self.do_backup_for_configuration(bck_params)

    def test_full_backup_02(self):
        """ Backup (with many fragmented files, encrypted) -> Restore -> check result """
        bck_params = BackupParameters()
        # Every archive will be one(1) disc.
        bck_params.single_archive_size = 300  # this ensures that each file will have multiple archives
        bck_params.disc_size = bck_params.single_archive_size
        bck_params.encryption_key = "my awesome encryption key!&"

        self.do_backup_for_configuration(bck_params)

    def test_full_backup_03(self):
        """ Backup -> Backup -> check if 2nd backup is empty """
        bck_params = BackupParameters()
        # Every archive will be one(1) disc.
        bck_params.single_archive_size = 1050
        bck_params.disc_size = bck_params.single_archive_size

        with tempfile.NamedTemporaryFile() as db_filename:
            with tempfile.TemporaryDirectory() as destination_dir:
                with tempfile.TemporaryDirectory() as source_dir:
                    bck_params.database_location = db_filename.name
                    bck_params.source = source_dir
                    bck_params.destination = destination_dir

                    src_file_list = self.create_sourceStructure(source_dir, [10, 10])
                    ctrl = BackupController(GeneralSettings())

                    # Preparations complete start backup...
                    ctrl.execute(bck_params)
                    # ... backup ended.

                    with tempfile.TemporaryDirectory() as destination_dir2:
                        bck_params = BackupParameters()
                        bck_params.database_location = db_filename.name
                        bck_params.source = source_dir
                        bck_params.single_archive_size = 1050
                        bck_params.disc_size = bck_params.single_archive_size
                        bck_params.destination = destination_dir2

                        ctrl = BackupController(GeneralSettings())

                        # Preparations complete start backup...
                        ctrl.execute(bck_params)
                        # ... backup ended.

                        for subdir, dirs, files in os.walk(destination_dir2):
                            assert len(dirs) == 0, "Found file that was not expected <%s>" % dirs

    def test_full_backup_04(self):
        """ Backup -> change one file -> Backup -> check if 2nd backup """
        bck_params = BackupParameters()
        # Every archive will be one(1) disc.
        bck_params.single_archive_size = 1050
        bck_params.disc_size = bck_params.single_archive_size

        with tempfile.NamedTemporaryFile() as db_filename:
            with tempfile.TemporaryDirectory() as destination_root:
                destination_dir1 = destination_root + "/0"
                os.mkdir(destination_dir1)
                destination_dir2 = destination_root + "/1"
                os.mkdir(destination_dir2)

                with tempfile.TemporaryDirectory() as source_dir:
                    bck_params.database_location = db_filename.name
                    bck_params.source = source_dir
                    bck_params.destination = destination_dir1

                    src_file_list = self.create_sourceStructure(source_dir, [10, 10])
                    ctrl = BackupController(GeneralSettings())

                    # Preparations complete start backup...
                    ctrl.execute(bck_params)
                    # ... backup ended.

                    # change the source
                    self.create_test_file(src_file_list[0], -1)

                    bck_params = BackupParameters()
                    bck_params.database_location = db_filename.name
                    bck_params.source = source_dir
                    bck_params.single_archive_size = 1050
                    bck_params.disc_size = bck_params.single_archive_size
                    bck_params.destination = destination_dir2

                    ctrl = BackupController(GeneralSettings())

                    # Preparations complete start backup...
                    ctrl.execute(bck_params)
                    # ... backup ended.

                    for subdir, dirs, files in os.walk(destination_dir2):
                        assert len(dirs) != 0 or len(files) != 0, \
                            "There should be directories <%s> or files <%s>" % (dirs, files)

                    with tempfile.TemporaryDirectory() as restore_dir:
                        rst_params = RestoreParameters()
                        rst_params.database_location = db_filename.name
                        rst_params.source = destination_root
                        rst_params.destination = restore_dir
                        rst_params.encryption_key = bck_params.encryption_key

                        ctrl = RestoreController(GeneralSettings())
                        ctrl.execute(rst_params)

                        assert DirCompare(source_dir, restore_dir).compare()
