import os
import subprocess
import tempfile
from typing import List

from logic.orm import Contract, Error, SecurityIssue
from logic.tools.tool_test_run import ToolTestRun


class SmartCheck(ToolTestRun):

    def __init__(self, contract: Contract, timeout):
        super().__init__(contract, 'smartcheck', timeout)
        _, self.cmd_file = tempfile.mkstemp('.txt')

    def __del__(self):
        super().__del__()
        os.remove(self.cmd_file)

    def _execute_tool(self):
        with open(self.cmd_file, 'w', encoding='utf-8') as f:
            subprocess.run(f'sudo docker run --rm -v "{self._contract.dir_path}:'
                           f'/root/test-contract" smartcheck smartcheck -p /root/test-contract/{self._contract.filename}',
                           shell=True, stdout=f, stderr=subprocess.STDOUT, timeout=self.timeout)

    def identify_errors(self) -> List[Error]:
        with open(self.cmd_file, encoding='utf-8') as f:
            return self.match_errors(f.read())

    def identify_security_issues(self) -> List[SecurityIssue]:
        with open(self.cmd_file, encoding='utf-8') as f:
            return self.match_security_issues(f.read())

    def create_report(self) -> str:
        return self._create_standard_report(self.cmd_file)


def create_tool_test_run(contract, timeout):
    return SmartCheck(contract, timeout)
