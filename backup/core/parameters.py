import multiprocessing

from backup.db.domain import BackupType

DEFAULT_DATABASE_FILENAME = "index.sqlite"


class GeneralSettings:
    def __init__(self):
        self.database_name = DEFAULT_DATABASE_FILENAME
        self.index_filename = "disc_id.yml"
        self.hook_dir = "./hooks/"


class BackupParameters:
    def __init__(self):
        self.database_location = "./" + DEFAULT_DATABASE_FILENAME
        self.source = None
        self.destination = None
        self.backup_type = BackupType.INCREMENTAL
        self.encryption_key = None
        self.use_threading = False
        self.threads = multiprocessing.cpu_count()
        self.backup_name = None  # User identifiable name, only stored with the very first backup

        self.single_archive_size = 1024 * 1024 * 1024  # 1 GB
        """Single Archive size in bytes"""
        self.backup_parameters = None  # TODO create defaults


class RestoreParameters:
    def __init__(self):
        self.database_location = "./" + DEFAULT_DATABASE_FILENAME
        self.source = None
        self.destination = None
        self.encryption_key = None
        self.restore_glob = ".*"
