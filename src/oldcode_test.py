import core
import os
import unittest
import tempfile
import oldcode


class OldCodeTest(unittest.TestCase):
    def test_backup_restore_blackbox(self):
        oldcode.ARCHIVE_SIZE = 1 * 1024 * 1024  # 1M in bytes
        oldcode.MAX_DISC_SIZE = 300 * 1024 * 1024  # 300M in bytes

        directories = 2
        files = 10

        with tempfile.TemporaryDirectory() as tmp_dir:
            print("Using dir <%s>" % tmp_dir)
            # Prepare directories
            src_dir = tmp_dir + "/src_dir"
            work_dir = tmp_dir + "/work"
            bck_dir = tmp_dir + "/bck_dir"
            out_dir = tmp_dir + "/out_dir"

            os.mkdir(src_dir)
            os.mkdir(work_dir)
            os.mkdir(bck_dir)
            os.mkdir(out_dir)

            created_files = self.create_directories(directories, files, src_dir)

            # Backup -> Restore
            oldcode.backup(src_dir, work_dir, bck_dir, list())
            oldcode.restore(bck_dir, work_dir, out_dir)

            # Compare src and out
            for file in created_files:
                src_file = src_dir + "/" + file
                dest_file = out_dir + "/" + file

                src_hash = oldcode.calculate_hash(src_file)
                dest_hash = oldcode.calculate_hash(dest_file)

                if src_hash != dest_hash:
                    print("%s: %s vs. %s" % (file, src_hash, dest_hash))

    def create_directories(self, directories, files, src_dir):
        ret = list()
        for d in range(directories):
            cur_dir = "%s/%03i/" % (src_dir, d)
            os.mkdir(cur_dir)

            for f in range(files):
                filename = "%s/%05i" % (cur_dir, f)
                self.create_file(filename, oldcode.ARCHIVE_SIZE * 5)
                ret.append("/%03i/%05i" % (d, f))

        return ret

    def create_file(self, file, length):
        with open(file, "wb") as f:
            b = core.BufferedWriter(f)
            for i in range(length):
                b.write((i % 255).to_bytes(1, byteorder='big'))


if __name__ == '__main__':
    unittest.main()
