import logging
from backup.core.controller import GeneralSettings
from backup.core.controller import BackupController, BackupParameters
from backup.core.controller import RestoreController, RestoreParameters
from backup.common.logger import configure_logger

logger = configure_logger(logging.getLogger(__name__))

if __name__ == '__main__':
    # Dummy backup code
    bp = BackupParameters()
    bp.destination = "/Volumes/right-hemi/butch_dest/"
    bp.source = "/Volumes/right-hemi/butch_src/"

    bc = BackupController(GeneralSettings())
    bc.execute(bp)
