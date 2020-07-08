import os
import tempfile
from unittest import TestCase, main
from unittest.mock import Mock
from backup.core.archive import ArchiveManager, FileBulker, DefaultArchiver
from common.customtestcase import CustomTestCase


class TestArchiver(CustomTestCase):
    def test_split_file_1(self):
        with tempfile.NamedTemporaryFile() as tf:

            total_size = 100
            single_size = 10

            with open(tf.name, 'w') as f:
                for i in range(total_size):
                    f.write('0')

            file_bulker = Mock()
            file_bulker.max_size = single_size

            a = ArchiveManager(file_bulker, Mock())

            count = 0
            for split in a.split_file(tf.name, 1):
                size = os.stat(split).st_size
                count += 1

                assert size == single_size

            assert count == 10

    def test_split_file_2(self):
        with tempfile.NamedTemporaryFile() as tf:

            total_size = 105
            single_size = 10

            with open(tf.name, 'w') as f:
                for i in range(total_size):
                    f.write('0')

            file_bulker = Mock()
            file_bulker.max_size = single_size

            a = ArchiveManager(file_bulker, Mock())

            count = 0
            for split in a.split_file(tf.name, 1):
                size = os.stat(split).st_size
                count += 1

                if count < 11:
                    assert size == single_size
                else:
                    assert size == 5

            assert count == 11


if __name__ == '__main__':
    main()
