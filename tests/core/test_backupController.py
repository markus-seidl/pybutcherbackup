import tempfile
from unittest import TestCase
from backup.core.controller import *


class TestDefaultController(TestCase):

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

                    ctrl.execute(bck_params)

                    db = DatabaseManager(db_filename.name)
                    backup_reader = db.read_backup(None)

                    for file in src_file_list:
                        test = backup_reader.find_original_path(file)

                        assert test is not None

    def test_restore(self):
        pass
