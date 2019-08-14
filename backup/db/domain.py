import datetime
from peewee import *
from enum import Enum
import os

from util import util
from util.util import auto_str

database = Proxy()


class FileState(Enum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    DELETED = "DELETED"
    IDENTICAL = "IDENTICAL"


class BackupType(Enum):
    FULL = "FULL"
    DIFFERENTIAL = "DIFF"


@auto_str
class BaseModel(Model):
    class Meta:
        database = database
        legacy_table_names = False


@auto_str
class BackupsEntry(BaseModel):
    pass
    # def __init__(self, *args, **kwargs):
    #    super().__init__(*args, **kwargs)


@auto_str
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


@auto_str
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


@auto_str
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

@auto_str
class FileEntry(BaseModel):
    original_filepath = TextField()
    original_filename = TextField()
    sha_sum = TextField()
    modified_time = DateTimeField()
    size = IntegerField()
    """Size in bytes"""
    part_number = IntegerField(null=True)
    relative_path = TextField()

    @property
    def original_file(self):
        return self.original_filepath + os.sep + self.original_filename

    # def __init__(self):
    #     self.archives = list()
    #
    # def original_file(self):
    #     return os.path.join(self.originalFilepath, self.originalFilename)
    #
    # def __repr__(self):
    #     return "(%s, %s, %s)" % (self.originalFilepath, self.originalFilename, self.shaSum)


@auto_str
class ArchiveFileMap(BaseModel):
    archive = ForeignKeyField(ArchiveEntry, backref='files')
    file = ForeignKeyField(FileEntry)

    class Meta:
        indexes = (
            # Every file can only be once in the same archive
            (('archive', 'file'), True),
        )


@auto_str
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
