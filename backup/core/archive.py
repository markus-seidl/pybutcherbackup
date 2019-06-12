import os
import tarfile
import dataclasses

from backup.core.luke import FileEntryDTO
import tempfile


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
        return file_dto.size


class Archiver:
    @dataclasses.dataclass
    class ArchivePackage:
        file_package: [FileEntryDTO]
        archive_file: str
        part_number: int = -1

    def __init__(self, file_bulker: FileBulker, archive_file):
        self.file_bulker = file_bulker
        self.max_size = file_bulker.max_size
        self.archive_file = archive_file

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

                i = 0
                for split_file in self.split_file(file.original_file()):
                    self.compress_file(split_file, file, self.archive_file)
                    yield Archiver.ArchivePackage(file_package, self.archive_file, i)

                    os.remove(self.archive_file)
                    i += 1
            else:
                # normal package
                self.compress_files(file_package, self.archive_file)
                yield Archiver.ArchivePackage(file_package, self.archive_file, -1)

                os.remove(self.archive_file)

    def compress_file(self, input_file, file_entry: FileEntryDTO, output_archive):
        pass

    def compress_files(self, input_files: [FileEntryDTO], output_archive):
        pass

    def file_extension(self):
        return None

    def split_file(self, input_file, buffer=1024) -> str:
        """
        Splits the file in multiple parts which have 'roughly' the size of self.max_size. The smallest size is
        determined by the buffer size.
        """
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
                            else:
                                if written == 0:
                                    return  # file has ended on split size - don't yield

                                break

                    yield f.name


class TarArchiver(Archiver):
    """
    Compresses files into tar files.

    - 'w:gz'	Open for gzip compressed writing.
    - 'w:bz2'	Open for bzip2 compressed writing.
    - 'w:xz'	Open for lzma compressed writing.
    """

    def __init__(self, file_bulker: FileBulker, archive_file, open_spec):
        super().__init__(file_bulker, archive_file)
        self.open_spec = open_spec
        if self.open_spec is None:
            self.open_spec = "w:bz2"

    def compress_file(self, input_file, file_entry: FileEntryDTO, output_archive):
        with tarfile.open(output_archive, self.open_spec) as tar:
            bck_path = file_entry.relative_path

            tar.add(input_file, arcname=bck_path)

    def compress_files(self, input_files: [FileEntryDTO], output_archive):
        with tarfile.open(output_archive, self.open_spec) as tar:
            for file in input_files:
                src_path = file.original_file()
                bck_path = file.relative_file

                tar.add(src_path, arcname=bck_path)
