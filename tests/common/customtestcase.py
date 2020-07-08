import unittest


class CustomTestCase(unittest.TestCase):
    def setUp(self):
        from backup.common.progressbar import set_simple
        set_simple()
