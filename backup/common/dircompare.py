from backup.core.luke import LukeFilewalker, FileEntryDTO


class DirCompare:

    def __init__(self, src_dir: str, dest_dir: str):
        self.src_dir = src_dir
        self.dest_dir = dest_dir

    def compare(self):
        src_files = self.walk(self.src_dir)
        dest_files = self.walk(self.dest_dir)

        ret = True
        # check all src_files in dest_files
        for src_rel_path in src_files:
            if src_rel_path not in dest_files:
                print("Dest doesn't have <%s>" % src_rel_path)
                ret = False
            else:
                dest_file = dest_files[src_rel_path]
                src_file = src_files[src_rel_path]

                if dest_file.sha_sum != src_file.sha_sum:
                    print("Sha doesn't match on file <%s>" % src_rel_path)
                    ret = False

        if len(dest_files) > len(src_files):
            print("Destination has more files than source? Weird.")
            ret = False

        return ret

    def walk(self, directory: str) -> {str: FileEntryDTO}:
        luke = LukeFilewalker(False)
        ret = dict()
        for file in luke.walk_directory(directory, True):
            ret[file.relative_file] = file

        return ret
