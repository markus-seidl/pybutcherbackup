import os
import dataclasses
import logging
from math import ceil

from backup.common.logger import configure_logger
from backup.core.luke import FileEntryDTO
from backup.core.archive import FileBulker, DefaultArchiver
import tempfile
from backup.multi.threadpool import ThreadPool
import hashlib

from backup.multi.backpressure import BackpressureManager
from backup.common.progressbar import create_pg

logger = configure_logger(logging.getLogger(__name__))


class ThreadingFileBulker(FileBulker):
    """Bulks the list of files retrieved from the filewalker, into packages of size max_size."""

    def __init__(self, file_iterator, max_size, pool):
        super().__init__(file_iterator, max_size)
        self.pool = pool

    def file_package_iter(self):
        """Gather max_size (bytes) in files and return the file entry objects as list."""
        files = list()
        futures = list()

        amount = 0
        for file in self.file_iterator:
            if amount + self._estimate_file_size(file) > self.max_size:
                if len(files) == 0:  # This file is too large for one archive, special handling
                    self.pool.wait(futures)
                    self._calculate_hash(file)
                    yield self._finish_info_package([file])
                    continue

                self.pool.wait(futures)
                yield self._finish_info_package(files)

                files = list()
                amount = 0

            amount += file.size
            files.append(file)
            futures.append(self.pool.add_task(self._calculate_hash, file))  # todo calc small files in-thread?

        if len(files) > 0:
            yield self._finish_info_package(files)

    @staticmethod
    def _calculate_hash(file: FileEntryDTO):
        sha256_hash = hashlib.sha256()
        with open(file.original_file, "rb") as f:
            # Read and update hash string value in blocks of 4K
            block_size = 4096
            for byte_block in iter(lambda: f.read(block_size), b""):
                sha256_hash.update(byte_block)

            file.sha_sum = sha256_hash.hexdigest()

    def _finish_info_package(self, files):
        return files


@dataclasses.dataclass
class ArchivePackage:
    file_package: [FileEntryDTO]
    archive_file: str
    tempfile: tempfile.NamedTemporaryFile
    part_number: int = -1


class ThreadingArchiveManager:
    def __init__(self, file_bulker: FileBulker, archiver: DefaultArchiver, pool: ThreadPool,
                 pressure: BackpressureManager):
        self.file_bulker = file_bulker
        self.max_size = file_bulker.max_size
        self.archiver = archiver
        self.pool = pool
        self.pressure = pressure

    def archive_package_iter(self) -> ArchivePackage:
        """

        :return:
            * File entry DTO
            * path to the archive file
            * number of the split package, or -1 if there is no source file split
        """

        queue = list()
        futures = list()

        for file_package in self.file_bulker.file_package_iter():
            if len(file_package) == 1 and file_package[0].size > self.max_size:

                # in order to keep the order in the backup files, put a threading barrier here
                # TODO make split_file multi threading able.
                self.pool.wait(futures)
                for q in futures:
                    yield q.result(None)
                    del q

                # split file
                file = file_package[0]

                # guess parts
                parts = int(ceil(file.size / self.max_size))

                i = 0
                for split_file in self.split_file(file.original_file):
                    temp_file = tempfile.NamedTemporaryFile()
                    self.archiver.compress_file(split_file, file, temp_file.name)
                    yield ArchivePackage(file_package, temp_file.name, temp_file, i)

                    i += 1
            else:
                while self.pressure.reached() and len(futures) > 0:
                    yield futures[0].result(None)
                    del futures[0]

                # normal package
                futures.append(self.pool.add_task(self._compress_file, file_package, queue, self.archiver))
                self.pressure.register_pressure()

                if futures[0].done():  # push already completed packages
                    yield futures[0].result(None)
                    del futures[0]

        self.pool.wait(futures)
        for q in futures:
            yield q.result(None)
            del q

    @staticmethod
    def _compress_file(file_package, queue, archiver):
        temp_file = tempfile.NamedTemporaryFile()
        archiver.compress_files(file_package, temp_file.name)
        dto = ArchivePackage(file_package, temp_file.name, temp_file, -1)
        queue.append(dto)

        return dto

    def split_file(self, input_file, buffer=1024) -> str:
        """
        Splits the file in multiple parts which have 'roughly' the size of self.max_size. The smallest size is
        determined by the buffer size.
        """
        file_size = os.stat(input_file).st_size
        with create_pg(total=file_size, leave=False, unit='B', unit_scale=True, unit_divisor=1024,
                       desc='Splitting file') as t:

            with open(input_file, 'rb') as src:
                while True:
                    with tempfile.NamedTemporaryFile() as f:
                        with open(f.name, 'wb') as dest:
                            written = 0
                            while written < self.max_size:
                                data = src.read(buffer)
                                if data:
                                    dest.write(data)
                                    written += buffer
                                    t.update(len(data))
                                else:
                                    if written == 0:
                                        return  # file has ended on split size - don't yield

                                    break

                        yield f.name
