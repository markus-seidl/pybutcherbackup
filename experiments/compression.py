import tarfile
import os
import tempfile
import time
import libarchive

from backup.common.progressbar import create_pg, set_slient, set_tqdm
from backup.common.shell import Shell

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


def compress_libarchive(format_name, filter_name, input_files: [str], output_archive):
    """

    on mac start with
    export LIBARCHIVE=/usr/local/Cellar/libarchive/3.4.3/lib/libarchive.dylib

    format_name = 7zip, v7tar
    filter_name =     , bzip2

    :return:
    """
    with libarchive.file_writer(output_archive, format_name, filter_name) as f:
        f.add_files(input_files)


def compress_shell_tar(format, input_file: str, output_archive):
    cmd = list()
    cmd.append("/usr/bin/tar")
    cmd.append("c%sf" % format)
    cmd.append(output_archive)
    cmd.append(input_file)

    s = Shell()
    result = s.run_cmd(cmd)
    # print(result.data)


def compress_shell_lz4(input_file: str, output_archive, compression_level=1):
    cmd = list()
    cmd.append("/usr/local/bin/lz4")
    cmd.append("-%s" % compression_level)
    cmd.append(input_file)
    cmd.append(output_archive)

    os.remove(output_archive)

    s = Shell()
    result = s.run_cmd(cmd)


def create_dummy_file(output_file, size):
    buff = 1024 * 10
    cur_size = 0

    with open(output_file, 'wb') as f:
        while cur_size <= size:
            f.write(os.urandom(buff))
            cur_size += buff


def create_dummy_text_file(output_file, size):
    cur_size = 0

    text = 'abcdefghijklmnopqrstuvwyzABCDEFGHIJKLMNOPQRSTUVWYZ0123456789' + str(os.urandom(100))
    text += text[::-1]

    with open(output_file, 'w') as f:
        while cur_size <= size:
            f.write(text)
            cur_size += len(text)


def get_size(file):
    return os.stat(file).st_size / 1024 / 1024  # b -> mb


def print_single_result(type, time, compressed_size, original_size):
    original_size_mb = original_size / 1024 / 1024
    ratio = compressed_size / original_size_mb
    print("\t%s\t\t%03.3fs\t%02.3f\t%03.2f%%" % (type, time, compressed_size, ratio * 100))


def run_algorithms(input_file, output_file, original_file_size):
    # python tar:gz
    start = time.perf_counter()
    compress_file_tar('w:gz', [input_file], output_file)
    end = time.perf_counter()
    # os.remove(tf_archive.name)
    print_single_result("python w:gz", end - start, get_size(tf_archive.name), original_file_size)

    # python tar:bz2
    start = time.perf_counter()
    compress_file_tar('w:bz2', [input_file], output_file)
    end = time.perf_counter()
    # os.remove(tf_archive.name)
    print_single_result("python w:bz2", end - start, get_size(tf_archive.name), original_file_size)

    # libarchive tar+bz2 - doesn't work (!!)
    # start = time.perf_counter()
    # compress_libarchive('7zip', None, [tf_input.name], tf_archive.name)
    # end = time.perf_counter()
    # os.remove(tf_archive.name)
    # print("python w:bz2 %02.3fs" % (end - start))

    # gnutar+gz
    start = time.perf_counter()
    compress_shell_tar('z', input_file, output_file)
    end = time.perf_counter()
    # os.remove(tf_archive.name)
    print_single_result("gnutar czf", end - start, get_size(tf_archive.name), original_file_size)

    # gnutar+bzip
    start = time.perf_counter()
    compress_shell_tar('j', input_file, output_file)
    end = time.perf_counter()
    # os.remove(tf_archive.name)
    print_single_result("gnutar cjf", end - start, get_size(tf_archive.name), original_file_size)

    # lz4 1 ("best")
    start = time.perf_counter()
    compress_shell_lz4(input_file, output_file, 1)
    end = time.perf_counter()
    # os.remove(tf_archive.name)
    print_single_result("lz4-best", end - start, get_size(tf_archive.name), original_file_size)

    # lz4 1 ("high")
    start = time.perf_counter()
    compress_shell_lz4(input_file, output_file, 9)
    end = time.perf_counter()
    # os.remove(tf_archive.name)
    print_single_result("lz4-high", end - start, get_size(tf_archive.name), original_file_size)


if __name__ == '__main__':
    file_size = 1024 * 1024 * 500  # in bytes

    with tempfile.NamedTemporaryFile() as tf_input:
        with tempfile.NamedTemporaryFile() as tf_archive:
            print("--- uncompressable file ---")
            create_dummy_file(tf_input.name, file_size)
            run_algorithms(tf_input.name, tf_archive.name, file_size)

            print("--- simple, compressible text-file ---")
            create_dummy_text_file(tf_input.name, file_size)
            run_algorithms(tf_input.name, tf_archive.name, file_size)
