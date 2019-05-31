import tempfile
import unittest

from db.domain import *
from db.db import DatabaseManager


class DomainTest(unittest.TestCase):
    def test_process(self):
        with tempfile.NamedTemporaryFile() as tmp_filename:
            db_manager = DatabaseManager(tmp_filename.name)

            with db_manager.database.atomic():
                backup_manager = db_manager.create_backup()

                backup_manager.create_disc()



