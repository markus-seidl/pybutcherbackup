from unittest import TestCase, main
import tempfile

from backup.core.luke import LukeFilewalker


class TestLukeFilewalker(TestCase):

    def create_test_file(self, name):
        with open(name, 'w') as temp:
            temp.write("This is a test")

    def test_calculate_hash(self):
        with tempfile.NamedTemporaryFile() as f:
            self.create_test_file(f.name)

            hash = LukeFilewalker().calculate_hash(f.name)

            assert "c7be1ed902fb8dd4d48997c6452f5d7e509fbcdbe2808b16bcf4edce4c07d14e" == hash

    def test_filewalker_1(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            full_path = temp_dir + '/a'
            self.create_test_file(full_path)

            files = LukeFilewalker().walk_directory_list(temp_dir)

            f = files[0]
            assert f.original_filename == 'a'
            assert f.original_path == temp_dir
            assert f.sha_sum == "c7be1ed902fb8dd4d48997c6452f5d7e509fbcdbe2808b16bcf4edce4c07d14e"


if __name__ == '__main__':
    main()
