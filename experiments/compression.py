import tarfile
import os
import tempfile
import time
import libarchive

from backup.common.progressbar import create_pg, set_slient, set_tqdm

set_slient()


def compress_file_tar(open_spec, input_files: [str], output_archive):
    """
    Compresses files into tar files.

    - 'w:gz'	Open for gzip compressed writing.
    - 'w:bz2'	Open for bzip2 compressed writing.
    - 'w:xz'	Open for lzma compressed writing.
    """

    with tarfile.open(output_archive, open_spec) as tar:
        with create_pg(total=len(input_files), leave=False, unit='file', desc='Compressing files') as t:
            for file in input_files:
                t.set_postfix(file=file)
                tar.add(file)
                t.update(1)


def compress_libarchive(open_spec, input_files: [str], output_archive):
    """

    on mac start with
    export LIBARCHIVE=/usr/local/Cellar/libarchive/3.4.3/lib/libarchive.dylib
    :return:
    """
    with libarchive.file_writer(output_archive, open_spec) as f:
        f.add_files(input_files)


def create_dummy_file(output_file, size):
    buff = 1024 * 10
    cur_size = 0

    with open(output_file, 'wb') as f:
        while cur_size <= size:
            f.write(os.urandom(buff))
            cur_size += buff


if __name__ == '__main__':
    with tempfile.NamedTemporaryFile() as tf_input:
        with tempfile.NamedTemporaryFile() as tf_archive:
            file_size = 1024 * 1024 * 500  # in bytes

            create_dummy_file(tf_input.name, file_size)

            # python tar:gz
            start = time.perf_counter()
            compress_file_tar('w:gz', [tf_input.name], tf_archive.name)
            end = time.perf_counter()
            os.remove(tf_archive.name)
            print("python w:gz %02.3fs" % (end - start))

            # python tar:bz2
            start = time.perf_counter()
            compress_file_tar('w:bz2', [tf_input.name], tf_archive.name)
            end = time.perf_counter()
            os.remove(tf_archive.name)
            print("python w:bz2 %02.3fs" % (end - start))
