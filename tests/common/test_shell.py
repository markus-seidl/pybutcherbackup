import os
import tempfile
from unittest import TestCase, main
from unittest.mock import Mock
from backup.common.shell import Shell
from tests.common.customtestcase import CustomTestCase


class TestShell(CustomTestCase):
    def test_cmd_1(self):
        s = Shell()

        cmd = list()
        cmd.append("/usr/bin/tar")
        cmd.append("--version")

        res = s.run_cmd(cmd)

        assert "tar" in str(res.data)

