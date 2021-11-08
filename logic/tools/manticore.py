import os
import subprocess
import tempfile
from typing import List, Union

from logic.orm import Contract, SolidityContract, Error, SecurityIssue
from logic.tools.tool_test_run import ToolTestRun


class Manticore(ToolTestRun):

    def __init__(self, contract: Union[Contract, SolidityContract], timeout):
        super().__init__(contract, 'manticore', timeout)
        self.tmp_dir = tempfile.mkdtemp()
        _, self.cmd_file = tempfile.mkstemp('.txt')
        self.findings_file = None
        if type(contract) == SolidityContract:
            self.used_solc = self.get_solc_bin()

    def _execute_tool(self):
        with open(self.cmd_file, 'w', encoding='utf-8') as f:
            docker_output_dir = '/root/test-output'
            docker_contract_dir = '/root/test-contract'
            docker_solc_dir = '/root/solc-version'
            solc_command = ''
            solc_mount = ''
            contract_command = ''
            if self._contract.is_solidity_contract:
                solc_mount = f'-v "{self.used_solc}":{docker_solc_dir}'
                solc_command = f'--solc {docker_solc_dir}/solc'
                contract_command = f'--contract "{self._contract.name}"'

            command = f'sudo docker run --rm --ulimit stack=100000000:100000000 {solc_mount} -v "{self.tmp_dir}":{docker_output_dir}' + \
                      f' -v {self._contract.dir_path}:{docker_contract_dir} -w {docker_output_dir} trailofbits/manticore manticore ' + \
                      f' {solc_command} {contract_command} "{docker_contract_dir}/{self._contract.filename}"'
            subprocess.run(command,
                           shell=True, stdout=f, stderr=subprocess.STDOUT, timeout=self.timeout)

            try:
                output_dir = f'{self.tmp_dir}/{next(filter(lambda dir_name: "mcore_" in dir_name, os.listdir(self.tmp_dir)))}'
                subprocess.run(f'sudo chmod -R 777 {output_dir}', shell=True
                                            , stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL
                                            )
                self.findings_file = f'{output_dir}/global.findings'
            except StopIteration as e:
                self.check_findings_file()

    def identify_errors(self) -> List[Error]:
        with open(self.cmd_file, encoding='utf-8') as f:
            return self.match_errors(f.read())

    def identify_security_issues(self) -> List[SecurityIssue]:
        if self.check_findings_file():
            with open(self.findings_file, encoding='utf-8') as f:
                return self.match_security_issues(f.read())
        return []

    def create_report(self) -> str:
        return self._create_standard_report(self.cmd_file, self.findings_file)

    def check_findings_file(self):
        if not self.findings_file or not os.path.isfile(self.findings_file):
            self._exceptions |= {FileNotFoundError('Could not find Manticore\'s output file.')}
            return False
        return True


def create_tool_test_run(contract, timeout):
    return Manticore(contract, timeout)
