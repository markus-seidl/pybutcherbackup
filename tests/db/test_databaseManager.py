import tempfile
from unittest import TestCase

from backup.db.db import DatabaseManager


class TestDatabaseManager(TestCase):
    def test_open_close_database(self):
        with tempfile.NamedTemporaryFile() as db_file:
            db = DatabaseManager(db_file.name)
            db.close_database()

            db = DatabaseManager(db_file.name)
            db.close_database()
