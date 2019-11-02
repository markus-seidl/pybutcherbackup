import os
import tarfile
import dataclasses
import logging
from math import ceil

from tqdm import tqdm
from backup.common.logger import configure_logger
from backup.core.luke import FileEntryDTO
import tempfile

from backup.common.util import configure_tqdm

logger = configure_logger(logging.getLogger(__name__))


class FileBulker:
    """Bulks the list of files retrieved from the filewalker, into packages of size max_size."""

    def __init__(self, file_iterator, max_size):
        self.last_file = None
        self.file_iterator = file_iterator
        self.max_size = max_size

    def file_package_iter(self):
        """Gather max_size (bytes) in files and return the file entry objects as list."""
        files = list()

        amount = 0
        for file in self.file_iterator:
            if amount + self._estimate_file_size(file) > self.max_size:
                if len(files) == 0:  # This file is too large for one archive, special handling
                    yield self._finish_info_package([file])
                    continue

                yield self._finish_info_package(files)

                files = list()
                amount = 0

            amount += file.size
            files.append(file)

        if len(files) > 0:
            yield self._finish_info_package(files)

    def _finish_info_package(self, files):
        return files

    def _estimate_file_size(self, file_dto: FileEntryDTO) -> int:
        # TODO: guess the file type and then apply some kind of factor. Because we know that jpg/mpeg etc don't
        #  compress well, but txt files do for example
        return file_dto.size


class DefaultArchiver:
    """
    Compresses files into tar files.

    - 'w:gz'	Open for gzip compressed writing.
    - 'w:bz2'	Open for bzip2 compressed writing.
    - 'w:xz'	Open for lzma compressed writing.
    """

    def __init__(self, open_spec='w:bz2'):
        self.open_spec = open_spec

    def compress_file(self, override_file, file_entry: FileEntryDTO, output_archive):
        with tarfile.open(output_archive, self.open_spec) as tar:
            bck_path = file_entry.relative_path
            tar.add(override_file, arcname=bck_path)

    def compress_files(self, input_files: [FileEntryDTO], output_archive):
        with tarfile.open(output_archive, self.open_spec) as tar:
            with tqdm(input_files, leave=False, unit='file') as t:
                configure_tqdm(t)
                t.set_description('Compressing files')

                for file in t:
                    src_path = file.original_file
                    bck_path = file.relative_path

                    t.set_postfix(file=file.relative_path)
                    tar.add(src_path, arcname=bck_path)
                    t.update(1)

    def decompress_files(self, source_archive: str, relative_files: [str], output_dir: str):
        with tarfile.open(source_archive, 'r:*') as tar:
            for relative_path in relative_files:
                temp = relative_path
                if temp[0] == '/':  # remove leading slash, because tar does this also internally
                    temp = temp[1:]

                member = tar.getmember(temp)
                tar.extract(member, output_dir)

    @property
    def extension(self):
        if self.open_spec == 'w:bz2':
            return "tar.bz2"
        raise RuntimeError("TODO")


class ArchiveManager:
    @dataclasses.dataclass
    class ArchivePackage:
        file_package: [FileEntryDTO]
        archive_file: str
        part_number: int = -1

    def __init__(self, file_bulker: FileBulker, temp_archive_file: str, archiver: DefaultArchiver):
        self.file_bulker = file_bulker
        self.max_size = file_bulker.max_size
        self.temp_archive_file = temp_archive_file
        self.archiver = archiver

    def archive_package_iter(self) -> (FileEntryDTO, str, int):
        """

        :return:
            * File entry DTO
            * path to the archive file
            * number of the split package, or -1 if there is no source file split
        """
        for file_package in self.file_bulker.file_package_iter():
            if len(file_package) == 1 and file_package[0].size > self.max_size:
                # split file
                file = file_package[0]

                # guess parts
                parts = int(ceil(file.size / self.max_size))

                i = 0
                with tqdm(total=parts, unit='part', leave=False) as t:
                    configure_tqdm(t)
                    t.set_description('Compressing part')

                    for split_file in self.split_file(file.original_file):
                        t.set_postfix(file=file.relative_path)
                        t.unpause()
                        self.archiver.compress_file(split_file, file, self.temp_archive_file)
                        t.update(1)
                        yield ArchiveManager.ArchivePackage(file_package, self.temp_archive_file, i)

                    i += 1
            else:
                # normal package
                self.archiver.compress_files(file_package, self.temp_archive_file)
                yield ArchiveManager.ArchivePackage(file_package, self.temp_archive_file, -1)

    def split_file(self, input_file, buffer=1024) -> str:
        """
        Splits the file in multiple parts which have 'roughly' the size of self.max_size. The smallest size is
        determined by the buffer size.
        """
        file_size = os.stat(input_file).st_size
        with tqdm(total=file_size, leave=False, unit='B', unit_scale=True, unit_divisor=1024) as t:
            configure_tqdm(t)
            t.set_description('Splitting file')

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
