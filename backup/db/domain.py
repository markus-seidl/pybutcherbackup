import datetime
from peewee import *
from enum import Enum
import os

from backup.common.util import auto_str, is_enum

database = Proxy()


class FileState(Enum):
    NEW = "NEW"
    UPDATED = "UPDATED"
    DELETED = "DELETED"


class BackupType(Enum):
    FULL = "FULL"
    INCREMENTAL = "INC"


@auto_str
class BaseModel(Model):
    class Meta:
        database = database
        legacy_table_names = False


@auto_str
class BackupsEntry(BaseModel):
    name = TextField(null=True)


@auto_str
class BackupEntry(BaseModel):
    created = DateTimeField(default=datetime.datetime.now)
    backups = ForeignKeyField(BackupsEntry, backref='backups')
    _type = TextField(null=False)
    """Backup type (e.g. full, diff, ...)"""
    version = IntegerField(default=1)  # current backup data model version

    # TODO State (started, completed)

    @property
    def type(self):
        return BackupType(self._type)

    @type.setter
    def type(self, value: BackupType):
        if not is_enum(value):
            raise Exception("Type is not an enum")

        self._type = value.value


@auto_str
class DiscEntry(BaseModel):
    backup = ForeignKeyField(BackupEntry, backref='discs')


@auto_str
class ArchiveEntry(BaseModel):
    disc = ForeignKeyField(DiscEntry, backref='archives')
    name = TextField(null=True)


@auto_str
class FileEntry(BaseModel):
    sha_sum = TextField()
    modified_time = DateTimeField()
    size = IntegerField()
    """Size in bytes"""
    relative_file = TextField()


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
        if not is_enum(value):
            raise Exception("State is not an enum")

        self._state = value.value

    class Meta:
        indexes = (
            # Every file can only be once in the same archive
            (('backup', 'file'), True),
        )
