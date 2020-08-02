from backup.common.shell import Shell
from backup.core.parameters import GeneralSettings


class HookHelper:

    def __init__(self, general_settings: GeneralSettings):
        self._general_settings = general_settings

    def execute_hook(self, name: str, parameters: list):
        s = Shell()
        cmd = list()
        cmd.append("/finish_backup.sh")
        cmd.extend(parameters)
        s.run_cmd(cmd)
