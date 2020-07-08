from unittest import TestCase, main

from backup.core.archive import FileBulker
from backup.core.luke import FileEntryDTO
from common.customtestcase import CustomTestCase


class TestFileBulker(CustomTestCase):
    def test_file_package_iter(self):
        files = list()

        files.append(FileEntryDTO())
        files.append(FileEntryDTO())
        files.append(FileEntryDTO())

        files[0].original_filename = "1"
        files[0].size = 100_000

        files[1].original_filename = "2"
        files[1].size = 100_000

        files[2].original_filename = "3"
        files[2].size = 1_000_000

        i = 0
        for package in FileBulker(files, 200_000).file_package_iter():
            if i == 0:
                assert len(package) == 2

                assert package[0].original_filename == "1"
                assert package[0].size == 100_000

                assert package[1].original_filename == "2"
                assert package[1].size == 100_000

            if i == 1:
                assert len(package) == 1

                assert package[0].original_filename == "3"
                assert package[0].size == 1_000_000

            i += 1

        assert i == 2


if __name__ == '__main__':
    main()
