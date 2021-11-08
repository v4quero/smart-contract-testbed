import subprocess
import tempfile
from typing import List

from logic.orm import Contract, Error, SecurityIssue
from logic.tools.tool_test_run import ToolTestRun


class Oyente(ToolTestRun):

    def __init__(self, contract: Contract, timeout):
        super().__init__(contract, 'oyente', timeout)
        _, self.cmd_file = tempfile.mkstemp('.txt')
        if self._contract.is_solidity_contract:
            self.used_solc = self.get_solc_bin()

    def _execute_tool(self):
        if self._contract.is_solidity_contract:
            solc_dir = self.used_solc
            bytecode_opt = ''
        else:
            solc_dir = None
            bytecode_opt = '--bytecode'
        tool_cmd = f'python /oyente/oyente/oyente.py {bytecode_opt} --source  {{docker_contract_path}}'
        command = self.create_docker_cmd('luongnguyen/oyente', tool_cmd, solc_dir=solc_dir)
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
    return Oyente(contract, timeout)
