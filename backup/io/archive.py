from io.luke import FileEntryDTO


class FileBulker:

    def __init__(self, file_iterator):
        self.last_file = None
        self.file_iterator = file_iterator

    def archive_package_iter(self, max_size) -> list:
        """Gather max_size (bytes) in files and return the file entry objects as list."""
        files = list()

        amount = 0
        for file in self.file_iterator:
            if amount + self._estimate_file_size(file) > max_size:
                if len(files) == 0:  # This file is too large for one archive, special handling
                    yield self._finish_info_package(list(file))
                    continue

                yield self._finish_info_package(files)

                files = list()
                amount = 0

            amount += file.size
            files.append(file)

    def _finish_info_package(self, files):
        return files

    def _estimate_file_size(self, file_dto: FileEntryDTO) -> int:
        return file_dto.size
