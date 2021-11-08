import os
import subprocess
import tempfile
from typing import List

from logic.orm import Contract, Error, SecurityIssue
from logic.tools.tool_test_run import ToolTestRun


class Mythril(ToolTestRun):

    def __init__(self, contract: Contract, timeout):
        super().__init__(contract, 'mythril', timeout)
        _, self.cmd_file = tempfile.mkstemp('.txt')
        if contract.is_solidity_contract:
            self.used_solc = self.get_solc_bin()

    def __del__(self):
        super().__del__()
        os.remove(self.cmd_file)

    def _execute_tool(self):
        if self._contract.is_solidity_contract:
            tool_cmd = f'analyze --solv {self.used_solc[self.used_solc.rfind("/") + 1:]}  {{docker_contract_path}}:{self._contract.name} -t 3'
        else:
            tool_cmd = f'analyze --codefile {{docker_contract_path}} -t 3'
        command = self.create_docker_cmd('mythril/myth', tool_cmd)
        with open(self.cmd_file, 'w', encoding='utf-8') as f:
            subprocess.run(command,
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
    return Mythril(contract, timeout)
