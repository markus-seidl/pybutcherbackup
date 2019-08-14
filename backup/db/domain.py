import datetime
from peewee import *
from enum import Enum

from util import util

database = Proxy()


class FileState(Enum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    IDENTICAL = "IDENTICAL"


class BackupType(Enum):
    FULL = "FULL"
    DIFFERENTIAL = "DIFF"


class BaseModel(Model):
    class Meta:
        database = database
        legacy_table_names = False


class BackupsEntry(BaseModel):
    pass
    # def __init__(self, *args, **kwargs):
    #    super().__init__(*args, **kwargs)


class BackupEntry(BaseModel):
    created = DateTimeField(default=datetime.datetime.now)
    backups = ForeignKeyField(BackupsEntry, backref='backups')
    _type = TextField(null=False)
    """Backup type (e.g. full, diff, ...)"""

    # TODO State (started, completed)

    @property
    def type(self):
        return BackupType(self._type)

    @type.setter
    def type(self, value: BackupType):
        if not util.is_enum(value):
            raise Exception("Type is not an enum")

        self._type = value.value


class DiscEntry(BaseModel):
    number = IntegerField()
    backup = ForeignKeyField(BackupEntry, backref='discs')

    # number = None
    # """Number of disc in backup."""
    # archives = None
    # """List of ArchiveEntry s."""

    # def __init__(self, *args, **kwargs):
    # self.archives = list()
    #    super().__init__(*args, **kwargs)

    # def size(self):
    #     ret = 0
    #     for archive in self.archives:
    #         ret += archive.size
    #
    #     return ret


class ArchiveEntry(BaseModel):
    number = IntegerField()
    disc = ForeignKeyField(DiscEntry, backref='archives')


# number = None
# """Number of the archive on the disc."""
# files = None
# """List of FileEntry s inside this archive."""
# size = None
# """Size of the compressed archive."""
#
# def __init__(self):
#     self.files = list()


class FileEntry(BaseModel):
    original_filepath = TextField()
    original_filename = TextField()
    sha_sum = TextField()
    modified_time = DateTimeField()
    size = IntegerField()
    """Size in bytes"""
    part_number = IntegerField(null=True)
    relative_path = TextField()

    def is_deleted(self):
        return self.size == -1

    def set_deleted(self):
        self.size = -1

    # def __init__(self):
    #     self.archives = list()
    #
    # def original_file(self):
    #     return os.path.join(self.originalFilepath, self.originalFilename)
    #
    # def __repr__(self):
    #     return "(%s, %s, %s)" % (self.originalFilepath, self.originalFilename, self.shaSum)


class ArchiveFileMap(BaseModel):
    archive = ForeignKeyField(ArchiveEntry, backref='files')
    file = ForeignKeyField(FileEntry)

    class Meta:
        indexes = (
            # Every file can only be once in the same archive
            (('archive', 'file'), True),
        )


class BackupFileMap(BaseModel):
    backup = ForeignKeyField(BackupEntry, backref='all_files')
    file = ForeignKeyField(FileEntry)
    _state = TextField(null=False)  # NEW, UPDATED, DELETED, IDENTICAL
    """ [NEW, UPDATED, DELETED, IDENTICAL] """

    @property
    def state(self):
        return FileState(self._state)

    @state.setter
    def state(self, value: FileState):
        if not util.is_enum(value):
            raise Exception("State is not an enum")

        self._state = value.value

    class Meta:
        indexes = (
            # Every file can only be once in the same archive
            (('backup', 'file'), True),
        )
