import multiprocessing

from backup.db.domain import BackupType

DEFAULT_DATABASE_FILENAME = "index.sqlite"


class GeneralSettings:
    def __init__(self):
        self.database_name = DEFAULT_DATABASE_FILENAME
        self.index_filename = "disc_id.yml"


class BackupParameters:
    def __init__(self):
        self.database_location = "./" + DEFAULT_DATABASE_FILENAME
        self.source = None
        self.destination = None
        self.single_archive_size = 1024 * 1024 * 1024  # 1 GB
        """Single Archive size in bytes"""
        self.disc_size = 1024 * 1024 * 1024 * 44  # 44 GB
        """Size of one backup disc"""
        self.backup_type = BackupType.INCREMENTAL
        self.encryption_key = None
        self.use_threading = False
        self.threads = multiprocessing.cpu_count()
        self.backup_name = None  # User identifiable name, only stored with the very first backup


class RestoreParameters:
    def __init__(self):
        self.database_location = "./" + DEFAULT_DATABASE_FILENAME
        self.source = None
        self.destination = None
        self.encryption_key = None
        self.restore_glob = ".*"
