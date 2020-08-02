import logging
import os

import tempfile
import re

import click

from backup.core.parameters import GeneralSettings, BackupParameters, RestoreParameters
from backup.core.basecontroller import BackupController
from backup.core.basecontroller import RestoreController
from backup.core.encryptor import GpgEncryptor
from backup.common.logger import configure_logger
from backup.db.db import DatabaseManager
from backup.storage.directory import DirectoryStorageBackupParameters

from backup.terminal.table import Table, TableColumn
from backup.common.progressbar import set_pg_type

logger = configure_logger(logging.getLogger(__name__))


@click.group()
def cli_base():
    pass


@click.group()
def cli_backup():
    pass


@click.group()
def cli_restore():
    pass


@cli_backup.command('backup')
@click.argument('src', type=click.Path(exists=True))
@click.argument('dest', type=click.Path(exists=True))
@click.option("--index", help='Path to the index to use.', default=None)
@click.option("--passphrase", help='Passphrase to use on the backup', default=None)
@click.option("--threading/--no-threading", help='Use threading if specified, no threading is default '
                                                 'but will change in the future. '
                                                 'Currently threading is *experimental*.', default=False)
@click.option("--name", help="User name for that backup repository", default=None)
@click.option("--terminal", help="Switch the progress type between SIMPLE, SILENT and TQDM",
              type=click.Choice(['SIMPLE', 'SILENT', 'TQDM']), case_sensitive=False, default="TQDM")
@click.option("--dir-medium-size", help="Maximum size of a medium directory in GB", type=int, default=44)
def action_backup(src: str, dest: str, index: str, passphrase: str, threading: bool, name: str, terminal: str,
                  dir_medium_size: int):
    bp = BackupParameters()
    bp.source = src
    bp.encryption_key = passphrase
    bp.use_threading = threading
    bp.backup_name = name

    if str(dest).startswith('dir://'):
        dest = dest[len('dir://'):]
        dp = DirectoryStorageBackupParameters()
        dp.medium_size = dir_medium_size
        bp.backup_parameters = dp

    bp.destination = dest

    if index:
        bp.database_location = index  # TODO path should be relative to source?

    set_pg_type(terminal)

    bc = BackupController(GeneralSettings())
    bc.execute(bp)


@cli_base.command('list-files')
@click.option("--passphrase", help='Passphrase to use on the backup', default=None)
@click.argument("index")
def action_list_files(passphrase: str, index: str):
    if not os.path.exists(index):
        print("Database not found <%s>" % index)
        return

    index_file = index
    if passphrase:
        e = GpgEncryptor(passphrase)
        index_file = tempfile.NamedTemporaryFile().name
        e.decrypt_file(index, index_file)
        print(index_file)

    db = DatabaseManager(index_file)
    reader = db.read_backup(None)

    af = reader.all_files
    af_keys = af.keys()
    sorted_af_keys = sorted(af_keys)

    table_data = list()
    for original_file in sorted_af_keys:
        file_entry = af[original_file]
        table_data.append([
            file_entry.relative_file,
            file_entry.size,
            file_entry.modified_time,
            file_entry.sha_sum
        ])

    Table(
        table_data,
        [
            TableColumn('Path'),
            TableColumn('Size'),
            TableColumn('Mod Time'),
            TableColumn('SHA')
        ]
    ).print()


@cli_restore.command('restore')
@click.argument('src', type=click.Path(exists=True))
@click.argument('dest', type=click.Path(exists=True))
@click.option("--index", help='Path to the index to use.', default=None)
@click.option("--passphrase", help='Passphrase to use on the backup', default=None)
@click.option("--filter", help='Regex to filter the restored filepath/name for. Use quotes to escape the string.',
              default=".*")
@click.option("--terminal", help="Switch the progress type between SIMPLE, SILENT and TQDM", default="TQDM")
def action_restore(src: str, dest: str, index: str, passphrase: str, filter: str, terminal: str):
    # input validation
    if filter:
        regex = re.compile(filter)  # if this fails, regex is incorrect
        if not regex:
            print("Regex invalid.")  # TODO is this necessary?
            return

    # dummy restore code
    rp = RestoreParameters()
    rp.source = src
    rp.destination = dest
    rp.encryption_key = passphrase
    rp.restore_glob = filter
    if index:
        rp.database_location = index

    set_pg_type(terminal)

    rc = RestoreController(GeneralSettings())
    rc.execute(rp)


cli = click.CommandCollection(sources=[cli_base, cli_backup, cli_restore])

# backup "/Volumes/right-hemi/butch_src/" "/Volumes/right-hemi/butch_dest/" asdfasdf
if __name__ == '__main__':
    cli()
