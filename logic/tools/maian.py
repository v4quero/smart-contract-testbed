import shutil
import subprocess
import tempfile
from datetime import datetime
from typing import List

from logic.orm import SolidityContract, SecurityIssue, Error
from logic.tools.tool_test_run import ToolTestRun


class Maian(ToolTestRun):

    def __init__(self, contract, timeout):
        super().__init__(contract, 'maian', timeout)
        self.tmp_dir = tempfile.mkdtemp()
        self.output_files = []
        if contract.is_solidity_contract:
            self.used_solc = self.get_solc_bin()
        self.options = {0: 'suicidal', 1: 'prodigal', 2: 'greedy'}

    def __del__(self):
        super().__del__()
        shutil.rmtree(self.tmp_dir)

    def _execute_tool(self):
        docker_contract_path = f'/root/test-contracts/{self._contract.filename}'
        mount_solc = ''
        if type(self._contract) == SolidityContract:
            mount_solc += f'-v "{self.used_solc}:/root/solc-version"'
            docker_cmd_without_opt = f'bash -c "export PATH=/root/solc-version:\$PATH &&' \
                                     f' python maian.py --soliditycode  {docker_contract_path} {self._contract.name}'
        else:
            docker_cmd_without_opt = f'bash -c "python maian.py -bs  {docker_contract_path}'

        processes: List[subprocess.Popen] = []
        for opt in self.options:
            output_file = '{}/opt_{}.txt'.format(self.tmp_dir, opt)
            self.output_files += [output_file]
            with open(output_file, 'w', encoding='utf-8') as f:
                cmd = f'sudo docker run --rm -w /MAIAN/tool -v "{self._contract.dir_path}":/root/test-contracts ' \
                      f'{mount_solc} cryptomental/maian-augur-ci {docker_cmd_without_opt} --check {opt}"'
                processes += [
                    subprocess.Popen(
                        cmd,
                        stdout=f,
                        stderr=subprocess.STDOUT, shell=True)
                ]

        timestamp = datetime.now()
        runtime = 0
        while processes:
            runtime = (datetime.now() - timestamp).total_seconds()
            if self.timeout and self.timeout < runtime:
                for process in processes:
                    process.kill()
            if processes[0].poll() is not None:
                del processes[0]
        if self.timeout and self.timeout < runtime:
            raise subprocess.TimeoutExpired(cmd, self.timeout)

    def identify_errors(self) -> List[Error]:
        errors = set()
        for file in self.output_files:
            with open(file, encoding='utf-8') as f:
                text = f.read()
            errors |= set(self.match_errors(text))
        return sorted(errors, key=lambda e: e.title)

    def identify_security_issues(self) -> List[SecurityIssue]:
        security_issues = set()
        for file in self.output_files:
            with open(file, encoding='utf-8') as f:
                text = f.read()
            security_issues |= set(self.match_security_issues(text))
        return sorted(security_issues, key=lambda s: s.title)

    def create_report(self) -> str:
        report = self.create_standard_report_intro() \
                 + ToolTestRun.separator + \
                 'Command-Line Output of the Tool:\n'
        for opt, description in self.options.items():
            report += f'Testing for {description} contracts:\n' + \
                      ToolTestRun.separator2
            with open(self.output_files[opt], encoding='utf-8') as f:
                report += f.read()
            report += ToolTestRun.separator2
        report += self.create_standard_security_issues_report()
        return report


def create_tool_test_run(contract, timeout):
    return Maian(contract, timeout)
