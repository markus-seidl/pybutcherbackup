import tempfile

from backup.core.archive import ArchiveManager
from backup.core.encryptor import Encryptor
from backup.multi.threadpool import ThreadPool
from backup.multi.archive import ArchivePackage, ThreadingArchiveManager


class ThreadingEncryptionManager:

    def __init__(self, archive_iterator: ThreadingArchiveManager, encryptor: Encryptor, pool: ThreadPool):
        self.archive_manager = archive_iterator
        self.encryptor = encryptor
        self.pool = pool

    def archive_package_iter(self) -> ArchivePackage:

        if not self.encryptor:
            for archive_package in self.archive_manager.archive_package_iter():
                yield archive_package
        else:
            futures = list()

            for archive_package in self.archive_manager.archive_package_iter():
                futures.append(self.pool.add_task(self._encrypt_file, archive_package, self.encryptor))

                if futures[0].done():
                    yield futures[0].result(None)
                    del futures[0]

            self.pool.wait(futures)
            for q in futures:
                yield q.result(None)
                del q

    @staticmethod
    def _encrypt_file(archive_package, encryptor):
        temp_file = tempfile.NamedTemporaryFile()
        encryptor.encrypt_file(archive_package.archive_file, temp_file.name)

        archive_package.archive_file = temp_file.name
        archive_package.tempfile.close()
        archive_package.tempfile = temp_file

        return archive_package
