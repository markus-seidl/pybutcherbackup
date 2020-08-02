from backup.core.parameters import GeneralSettings


class HookHelper:

    def __init__(self, general_settings: GeneralSettings):
        self._general_settings = general_settings

    def execute_hook(self, name: str, parameters: list):
        pass
