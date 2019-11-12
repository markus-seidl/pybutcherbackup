import os
import tarfile
import tempfile
from unittest import TestCase, main
from unittest.mock import Mock
from backup.core.archive import ArchiveManager, DefaultArchiver, FileBulker
from backup.core.luke import FileEntryDTO, LukeFilewalker


class TestDefaultArchiver(TestCase):
    def create_test_file(self, name, size=14):
        with open(name, 'w') as temp:
            for i in range(size):
                temp.write("a")

    def test_compress_file(self):
        with tempfile.NamedTemporaryFile() as archive_file:
            file_bulker = Mock()
            file_bulker.max_size = 0

            compression_type = 'bz2'

            tar = DefaultArchiver('w:' + compression_type)

            with tempfile.NamedTemporaryFile() as src_file:
                self.create_test_file(src_file.name)

                relative_file = "/rel/ative_path"

                file_entry = FileEntryDTO()
                file_entry.original_path = src_file.name
                file_entry.original_filename = ""
                file_entry.relative_file = relative_file

                tar.compress_file(src_file.name, file_entry, archive_file.name)

                with tarfile.open(archive_file.name, 'r:' + compression_type) as tar:
                    # tar.extract(relative_file)
                    file_info = tar.next()
                    assert file_info.size == 14
                    assert file_info.name == relative_file[1:]

                    assert tar.next() is None

    def test_compress_files(self):
        with tempfile.NamedTemporaryFile() as archive_file:
            file_bulker = Mock()
            file_bulker.max_size = 0

            compression_type = 'bz2'

            tar = DefaultArchiver('w:' + compression_type)

            with tempfile.NamedTemporaryFile() as src_file:
                self.create_test_file(src_file.name)

                relative_file = "/rel/ative_path"

                file_entry = FileEntryDTO()
                file_entry.original_path = os.path.split(src_file.name)[0]
                file_entry.original_filename = os.path.split(src_file.name)[1]
                file_entry.relative_file = relative_file

                tar.compress_files([file_entry], archive_file.name)

                with tempfile.TemporaryDirectory() as dest_dir:
                    tar.decompress_files(archive_file.name, [file_entry.relative_file], dest_dir)

                    assert os.stat(dest_dir + os.sep + file_entry.relative_file).st_size == 14

    def test_archive_package_iter(self):
        with tempfile.NamedTemporaryFile() as archive_file:
            with tempfile.TemporaryDirectory() as source_directory:

                self.create_test_file(source_directory + "/source_1", 2048)
                self.create_test_file(source_directory + "/source_2", 2048)
                self.create_test_file(source_directory + "/source_3", 100)

                file_walker = LukeFilewalker()
                file_bulker = FileBulker(file_walker.walk_directory(source_directory), 1024)

                compression_type = 'bz2'

                tar = DefaultArchiver('w:' + compression_type)
                am = ArchiveManager(file_bulker, archive_file.name, tar)

                i = 0
                for backup_package in am.archive_package_iter():
                    # print(backup_package)
                    if backup_package.file_package[0].original_filename == "source_1" \
                            and backup_package.part_number == 0:  # part 1 of source_1

                        assert backup_package.part_number == 0
                        assert backup_package.file_package[0].size == 2048
                    elif backup_package.file_package[0].original_filename == "source_1" \
                            and backup_package.part_number == 1:  # part 2 of source_1

                        assert backup_package.part_number == 1
                        assert backup_package.file_package[0].size == 2048
                    elif backup_package.file_package[0].original_filename == "source_2" \
                            and backup_package.part_number == 0:  # part 1 of source_2

                        assert backup_package.part_number == 0
                        assert backup_package.file_package[0].size == 2048
                    elif backup_package.file_package[0].original_filename == "source_2" \
                            and backup_package.part_number == 1:  # part 2 of source_2

                        assert backup_package.part_number == 1
                        assert backup_package.file_package[0].size == 2048
                    elif backup_package.file_package[0].original_filename == "source_3" \
                            and backup_package.part_number == -1:  # source_3

                        assert backup_package.part_number == -1
                        assert backup_package.file_package[0].size == 100
                    else:
                        self.fail("Unknown case: " + str(backup_package))

                    i += 1

            # the archive_package_iter removes the archive file, but the NamedTemporaryFile complains if it
            # has already been deleted
            self.create_test_file(archive_file.name, 1)


if __name__ == '__main__':
    main()
