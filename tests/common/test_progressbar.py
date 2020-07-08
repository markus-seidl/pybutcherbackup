import unittest

from backup.common.progressbar import create_pg, set_simple, set_tqdm


class TestProgressBar(unittest.TestCase):
    def test_basic_workflow_simple(self):
        set_simple()
        with create_pg(desc='Description', total=10) as t:
            for i in range(10):
                t.update(1)

    def test_basic_workflow_tqdm(self):
        set_tqdm()
        with create_pg(desc='Description', total=10) as t:
            for i in range(10):
                t.update(1)


if __name__ == '__main__':
    unittest.main()
