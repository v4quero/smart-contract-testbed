import os
import subprocess
import tempfile
from typing import List

from logic.orm import Contract, Error, SecurityIssue
from logic.tools.tool_test_run import ToolTestRun


class Securify2(ToolTestRun):

    def __init__(self, contract: Contract, timeout):
        super().__init__(contract, 'securify2', timeout)
        _, self.cmd_file = tempfile.mkstemp('.txt')
        if self._contract.is_solidity_contract:
            self.used_solc = self.get_solc_bin()

    def __del__(self):
        super().__del__()
        os.remove(self.cmd_file)

    def _execute_tool(self):
        with open(self.cmd_file, 'w', encoding='utf-8') as f:
            solc_mount = ''
            solc_command = ''
            contract_name = ''
            if self._contract.is_solidity_contract:
                solc_mount = f'-v "{self.used_solc}":/home/solc-version'
                solc_command = f'--solidity /home/solc-version/solc'
                contract_name = self._contract.name
            command = f'sudo docker run --rm  {solc_mount} ' \
                      f'-v "{self._contract.dir_path}":/share securify /share/"{self._contract.filename}" --include-contracts {contract_name} {solc_command}'
            subprocess.run(command, stdout=f, stderr=subprocess.STDOUT, shell=True,
                           timeout=self.timeout)

    def identify_errors(self) -> List[Error]:
        with open(self.cmd_file, encoding='utf-8') as f:
            return self.match_errors(f.read())

    def identify_security_issues(self) -> List[SecurityIssue]:
        with open(self.cmd_file, encoding='utf-8') as f:
            return self.match_security_issues(f.read())

    def create_report(self) -> str:
        return self._create_standard_report(self.cmd_file)


def create_tool_test_run(contract, timeout):
    return Securify2(contract, timeout)
