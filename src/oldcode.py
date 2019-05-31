import os
import hashlib
import sys
import tarfile
import pickle
import datetime
from tqdm import tqdm

ARCHIVE_SIZE = 1 * 1024 * 1024  # * 1024  # 1G in bytes
MAX_DISC_SIZE = 300 * 1024 * 1024  # * 1024  # 48G in bytes


def calculate_hash(filename) -> str:
    sha256_hash = hashlib.sha256()
    with open(filename, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

        return sha256_hash.hexdigest()


class BackupsEntry:
    def __init__(self):
        self.backups = list()


class BackupEntry:
    def __init__(self):
        self.created = datetime.datetime.now()
        self.discs = list()


class DiscEntry:
    number = None
    """Number of disc in backup."""
    archives = None
    """List of ArchiveEntry s."""

    def __init__(self):
        self.archives = list()

    def size(self):
        ret = 0
        for archive in self.archives:
            ret += archive.size

        return ret


class ArchiveEntry:
    number = None
    """Number of the archive on the disc."""
    files = None
    """List of FileEntry s inside this archive."""
    size = None
    """Size of the compressed archive."""

    def __init__(self):
        self.files = list()


class FileEntry:
    originalFilepath = None
    originalFilename = None
    shaSum = None
    modifiedTime = None
    size = None
    """Size in bytes"""
    archives = None
    """List of archives this file is contained. (Usually one)"""
    relativePath = None

    def __init__(self):
        self.archives = list()

    def original_file(self):
        return os.path.join(self.originalFilepath, self.originalFilename)

    def __repr__(self):
        return "(%s, %s, %s)" % (self.originalFilepath, self.originalFilename, self.shaSum)


def backup(directory, temp_dir, output_dir, all_backuped_files):
    # * Ingests the whole directory and builds up a database of all files with sha256/512 hashsums
    all_files = walk_directory(directory)

    # * Builds a diff against the supplied database (maybe from the last backup?)
    new_files_keys, _, _, changed_files_keys = diff_file_lists(all_backuped_files, all_files)
    print("New files %i, changed files %i" % (len(new_files_keys), len(changed_files_keys)))

    backup_files = generate_backup_file_list(all_files, new_files_keys, changed_files_keys)

    backups = BackupsEntry()
    backup_entry = BackupEntry()
    backups.backups.append(backup_entry)

    archive_no = 0
    current_disc = DiscEntry()
    current_disc.number = 0
    backup_entry.discs.append(current_disc)

    output_dir_disc = output_dir + "/" + str(current_disc.number) + "/"
    os.mkdir(output_dir_disc)

    archives = ArchiveIterator(directory, backup_files, output_dir_disc, temp_dir)
    for archive in archives:
        temp_archive_name, archive_package, split_no = archive
        temp_archive_size = os.stat(temp_archive_name).st_size

        # Does this archive fit into the current disc?
        if current_disc.size() + temp_archive_size > MAX_DISC_SIZE:
            #       * Finish disc
            backup_entry.discs.append(current_disc)
            pickle.dump(backup_entry, open(output_dir_disc + "db.pickle", "wb"))
            current_disc, output_dir_disc = finish_disc(current_disc, output_dir, output_dir_disc, True)

        archive_name = archive_file_name(output_dir_disc, current_disc.number, archive_no)
        os.rename(temp_archive_name, archive_name)

        update_information(backup_files, archive_package, current_disc, archive_no, archive_name, split_no)

        archive_no += 1

    if len(current_disc.archives) > 0:
        backup_entry.discs.append(current_disc)
        pickle.dump(backup_entry, open(output_dir_disc + "db.pickle", "wb"))
        current_disc, output_dir_disc = finish_disc(current_disc, output_dir, output_dir_disc, False)

    if os.path.exists(output_dir_disc) and os.listdir(output_dir_disc) == 0:
        os.rmdir(output_dir_disc)

    print("Success")


def finish_disc(current_disc, output_dir, output_dir_disc, has_next_disc):
    print("Burning disc %s" % output_dir_disc)
    # -> setup everything for the next disc
    disc_no = current_disc.number
    current_disc = DiscEntry()
    current_disc.number = disc_no + 1
    output_dir_disc = output_dir + "/" + str(current_disc.number) + "/"

    if has_next_disc:
        os.mkdir(output_dir_disc)

    return current_disc, output_dir_disc


class ArchiveIterator:
    def __init__(self, backup_dir, backup_files, output_dir, temp_dir):
        self.output_dir = output_dir
        self.backup_files = backup_files
        self.part = -1
        self.part_file_entry = None
        self.temp_dir = temp_dir
        self.backup_dir = backup_dir

    def __iter__(self):
        return self

    def __next__(self):
        archive_name = os.path.join(self.output_dir, "temp.tar.bz2")

        if self.part >= 0:
            split_file_name, more_files = compress_part(self.backup_dir, self.part_source_name, self.part, archive_name,
                                                        self.temp_dir)
            tmp = self.part
            if not more_files:
                self.part = -1
            else:
                self.part += 1

            return archive_name, self.part_file_entry, tmp

        archive_package, extra_large_file = find_archive_package(self.backup_files, ARCHIVE_SIZE)
        # * If source file is larger than 1G?
        if archive_package is None:
            #   * Binary split the file in 1G chunks
            self.part = 0
            self.part_file_entry = list()
            self.part_file_entry.append(extra_large_file)
            self.part_source_name = extra_large_file.original_file()

            split_file_name, more_files = compress_part(self.backup_dir, self.part_source_name, self.part, archive_name,
                                                        self.temp_dir)
            tmp = self.part
            if not more_files:
                self.part = -1
            else:
                self.part += 1

            return archive_name, self.part_file_entry, tmp
        elif archive_package is not None and len(archive_package) > 0:
            # * Compress this
            compress(self.backup_dir, archive_package, archive_name)
            return archive_name, archive_package, -1

        raise StopIteration


def walk_directory(directory) -> list:
    ret = list()
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            f = os.path.join(subdir, file)

            e = FileEntry()
            ret.append(e)

            e.originalFilepath = subdir
            e.originalFilename = file

            e.shaSum = calculate_hash(f)
            e.modifiedTime = os.path.getmtime(f)
            e.relativePath = find_relative_path(directory, f)

            e.size = os.stat(f).st_size

    return ret


def diff_file_lists(old_list, new_list):
    old_dict = diff_file_list_create_dict(old_list)
    new_dict = diff_file_list_create_dict(new_list)

    new_files_keys = set(new_dict) - set(old_dict)
    deleted_files_keys = set(old_dict) - set(new_dict)
    same_files_keys = set(new_dict) & set(old_dict)
    changed_files_keys = list()

    for file in same_files_keys:
        # check if shasum is different
        sha_old = old_dict[file].shaSum
        sha_new = new_dict[file].shaSum

        if sha_old != sha_new:
            changed_files_keys.append(file)

    return new_files_keys, deleted_files_keys, same_files_keys, changed_files_keys


def diff_file_list_create_dict(files) -> dict:
    ret = dict()

    for file in files:
        name = file.original_file()
        if name in ret:
            print("Duplicate file: %s" % file)
        else:
            ret[name] = file

    return ret


def generate_backup_file_list(all_files, new_files_keys, changed_files_keys):
    ret = list()

    all_files_dict = diff_file_list_create_dict(all_files)

    for name in new_files_keys:
        file = all_files_dict[name]
        ret.append(file)

    for name in changed_files_keys:
        file = all_files_dict[name]
        ret.append(file)

    return ret


def find_archive_package(files, max_size) -> (list, FileEntry):
    """Gather max_size (bytes) in files and return the file entry objects as list"""
    ret = list()

    amount = 0
    for file in files:
        if amount + file.size > max_size:
            break

        amount += file.size
        ret.append(file)

    # print("Found for amount: %i" % amount)

    if len(ret) == 0 and not len(files) == 0:
        # the next file is too large for one archive
        return None, files[0]

    return ret, None


def archive_file_name(output_dir, disc_no, archive_no):
    name = "backup_%04i_%04i.%s" % (disc_no, archive_no, "tar.bz2")
    return os.path.join(output_dir, name)


def compress(backup_dir, files, output_file):
    with tarfile.open(output_file, "w|bz2") as tar:
        for file in files:
            p = file.original_file()
            tar.add(p, arcname=find_relative_path(backup_dir, p))


def split_file(inp, output, part, buffer=1024):
    start = ARCHIVE_SIZE * part
    end = start + ARCHIVE_SIZE

    print("{0} - {1}".format(start, end))

    with open(inp, 'rb') as src:
        with open(output, 'wb') as dest:
            src.seek(start)
            written = 0
            while written < end - start:
                data = src.read(buffer)
                if data:
                    dest.write(data)
                    written += buffer
                else:
                    return False

    return True


def compress_part(backup_dir, file, part_no, output_file, temp_dir):
    # prepare temp file
    part_no_str = "%04i" % part_no
    split_file_name = os.path.split(file)[1] + "." + part_no_str
    split_file_path = temp_dir + "/" + split_file_name

    more_files = split_file(file, split_file_path, part_no)

    original_relative_path = find_relative_path(backup_dir, file) + "." + part_no_str

    with tarfile.open(output_file, "w|bz2") as tar:
        tar.add(split_file_path, arcname=original_relative_path)

    os.remove(split_file_path)

    return split_file_path, more_files


def find_relative_path(backup_dir, original_file_path):
    return original_file_path[len(backup_dir):]


def update_information(backup_files, archive_package, current_disc, archive_no, archive_name, split_no):
    archive_size = os.stat(archive_name).st_size

    archive = ArchiveEntry()
    archive.size = archive_size
    archive.files = archive_package
    archive.number = archive_no

    current_disc.archives.append(archive)

    for file in archive_package:
        # we are splitting files into multiple archives, it's ok its no longer in the backup collection
        if split_no <= 0:
            backup_files.remove(file)

    for file in archive_package:
        file.archives.append(archive)

    return archive


######


def restore(directory, temp_dir, output_dir):
    # TODO: make iterator, that asks for the correct disc
    backups = [x for x in os.listdir(directory) if x[0] != '.']  # all backups without hidden dirs/files
    last_backup = sorted(backups, reverse=True)[0]

    # restore db
    final_db = os.path.join(directory, last_backup, 'db.pickle')
    backup_entry = pickle.load(open(final_db, "rb"))

    # TODO make iterator, that asks for the correct disc
    archives = list()
    for subdir, dirs, files in os.walk(directory):
        for file in files:
            if file[-3:] == 'bz2':
                archives.append(subdir + "/" + file)
    archives = sorted(archives)
    # /iterator

    dict_split_files = dict()

    for archive in archives:
        disc_entry, archive_entry = find_archive_entry(backup_entry, archive)
        t = tarfile.open(archive)
        t.extractall(output_dir)

        # has this archive a file that is in more than one archive?
        split_files = find_split_files(archive_entry)
        if len(split_files) > 0:
            for file in split_files:
                no = 0
                if file.relativePath in dict_split_files:
                    no = dict_split_files[file.relativePath]

                join_files(output_dir + "/" + file.relativePath, no)
                dict_split_files[file.relativePath] = no + 1

    # check all files against the sha256 of the pickle file
    validate_all_files(output_dir, backup_entry)


def validate_all_files(directory, backup_entry):
    for disc in backup_entry.discs:
        for archive in disc.archives:
            for file in archive.files:
                p = directory + "/" + file.relativePath

                if not os.path.exists(p):
                    print("File %s doesn't exist" % p)

                sha = calculate_hash(p)

                if file.shaSum != sha:
                    print("File %s has non-matching shasum." % p)


def find_split_files(archive_entry):
    ret = list()

    for file in archive_entry.files:
        if len(file.archives) > 1:
            ret.append(file)

    return ret


def find_archive_entry(backup_entry, archive_name):
    archive_name = os.path.split(archive_name)[1]

    for disc in backup_entry.discs:
        for archive in disc.archives:
            name = "backup_%04i_%04i.%s" % (disc.number, archive.number, "tar.bz2")

            if name == archive_name:
                return disc, archive

    return None, None


def join_files(dest, no, buffer=1024):
    src = dest + ".%04i" % no

    if not os.path.exists(dest):
        # first part, just copy file to the destination
        os.rename(src, dest)
    else:
        with open(dest, "ab") as d:
            d.seek(0, os.SEEK_END)
            with open(src, "rb") as s:
                while True:
                    data = s.read(buffer)
                    if data:
                        d.write(data)
                    else:
                        break

        os.remove(src)  # delete unused part file ###.0000


if __name__ == '__main__':
    # backup("/Users/msei/temp/coursera/deep-neural-network/", "../temp/", "../output", list())
    restore("../output", "../temp/", "../restore")
