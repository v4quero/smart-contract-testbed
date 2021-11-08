import subprocess
import tempfile
import traceback
from abc import ABC
from datetime import datetime, timedelta
from threading import Thread
from typing import List, Union

import os
import re
import semver
from sqlalchemy.orm import subqueryload

import toolbox
from logic.orm import Contract, Tool, SolidityContract, SecurityIssue, Error, get_db_session, ToolError, \
    ToolSecurityIssue
from toolbox import get_range_for_installed_solcs
from toolbox import test_bed_path

solc_versions_dir = f'{test_bed_path}/resources/solc-versions'


class ToolTestRun(ABC):
    separator = '####################################################\n'
    separator2 = '---------------------------------------------------\n'

    def __init__(self, contract: Contract, tool_name, timeout):
        self._contract: Union[Contract, SolidityContract] = contract
        sess = get_db_session()
        self._tool: Tool = sess.query(Tool).options(
            subqueryload(Tool.tool_errors).subqueryload(ToolError.error)).options(
            subqueryload(Tool.tool_security_issues).subqueryload(ToolSecurityIssue.security_issue)).filter(
            Tool.name == tool_name).one()
        self._status = 'Before Run'
        self._exceptions = set()
        self.__errors: List[Error] = list()
        self.__security_issues: List[SecurityIssue] = list()
        self._execution_time: timedelta = None
        self.__report_file = None
        self._thread: Thread = None
        self.timeout = timeout

    def __del__(self):
        if self.__report_file and os.path.exists(self.__report_file):
            os.remove(self.__report_file)

    def __str__(self):
        return f'ToolTestRun({self._contract},{self._tool})'

    def run(self):
        if self._status != 'Before Run':
            raise PermissionError(f'Can only run {self} once.')
        print(f'start {self._tool}')
        self._thread = Thread(target=self.__run, name='Thread-me-1')
        self._thread.start()

    def __run(self):
        try:
            start = datetime.now()
            try:
                self._execute_tool()
            except subprocess.TimeoutExpired:
                try:
                    sess = get_db_session()
                except Exception as e:
                    print(e.with_traceback())
                tool_timeout = sess.query(Error).filter(Error.title == 'testbed timeout').one()
                self._exceptions |= {tool_timeout}
            self._execution_time = datetime.now() - start
            self._status = 'Terminated'
            print(f'terminated {self._tool}')
        except Exception as e:
            print(f'{self._tool}: {e}\n\n{traceback.print_exc()}')

    # abstract method
    def _execute_tool(self):
        pass

    def get_errors(self) -> List[Error]:
        self._check_terminated()
        if not self.__errors:
            self.__errors = self.identify_errors()
        return self.__errors

    def get_security_issues(self) -> List[SecurityIssue]:
        self._check_terminated()
        if not self.__security_issues:
            self.__security_issues = self.identify_security_issues()
        return self.identify_security_issues()

    def get_report(self):
        self._check_terminated()
        if not self.__report_file:
            report = self.create_report()
            _, report_file = tempfile.mkstemp('.txt')
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report.replace('\n', '\r\n'))
            self.__report_file = report_file
        return self.__report_file

    def get_terminated(self):
        return self._status == 'Terminated'

    def get_execution_time(self) -> timedelta:
        self._check_terminated()
        return self._execution_time

    def _check_terminated(self):
        if not self.get_terminated():
            raise RuntimeError('Tool has not terminated yet.')

    # abstract method
    def create_report(self) -> str:
        pass

    # abstract method
    def identify_security_issues(self) -> List[SecurityIssue]:
        pass

    # abstract method
    def identify_errors(self) -> List[Error]:
        pass

    def _create_standard_report(self, cmd_file, findings_file=None) -> str:
        report = self.create_standard_report_intro() + '\n' \
                                                       f'The Command-Line Output of the Tool-Execution'
        if not findings_file:
            report += ' including the Tool\'s Findings'
        report += ':\n' + ToolTestRun.separator2
        with open(cmd_file, encoding='utf-8') as f:
            report += f.read()
        report += ToolTestRun.separator
        if findings_file:
            report += f'\n{ToolTestRun.separator}' + \
                      f'The Output File of the Tool:\n' + \
                      ToolTestRun.separator2
            if os.path.exists(findings_file):
                with open(findings_file, encoding='utf-8') as f:
                    report += f.read()
            else:
                report += f'Could not find the findings file of the tool.'
            report += f'\n{ToolTestRun.separator}'
        report += self.create_standard_security_issues_report()
        return report

    def create_standard_report_intro(self) -> str:
        used_solc = None
        if hasattr(self, 'used_solc'):
            used_solc = self.used_solc
        report = ToolTestRun.separator + \
                 f'++++++++++++Test-Run Report++++++++++++\n\n' + \
                 ToolTestRun.separator + \
                 f'Created on:\t\t\t{datetime.now().strftime("%d.%m.%Y %H:%M")}\n' + \
                 ToolTestRun.separator + \
                 f'Tested Contract-File:\t\t{self._contract.filename}\n'
        if type(self._contract) == SolidityContract:
            report += f'Tested contracts of the File:\t'
            if self._tool.analyses_whole_file:
                report += f'all\n'
            else:
                report += f'{self._contract.name}\n'

        report += ToolTestRun.separator + \
                  f'Used Tool:\t\t\t{self._tool.name}\n' \
                  f'Execution Time:\t\t\t{toolbox.timedelta_to_string(self._execution_time)}\n'

        if type(self._contract) == SolidityContract and used_solc is not None:
            report += f'Used Solidity Compiler Version:\t{used_solc[used_solc.rfind("/") + 1:]}\n'
        # make sure that the errors list is complete
        self.get_errors()
        if self.__errors:
            report += ToolTestRun.separator + \
                      f'Errors during the execution of the Tools:\n'
            for error in self.__errors:
                report += ToolTestRun.separator2 + \
                          f'\t{error.title}\n'
                if error.description:
                    report += f'\t\tDescription:\t{error.description}\n'
                if error.link:
                    report += f'\t\tFurther Information:\t{error.link}\n'
        report += ToolTestRun.separator + '\n'
        return report

    def create_standard_security_issues_report(self) -> str:
        # make sure that the security-issues list is complete
        self.get_security_issues()
        if self.__security_issues:
            report = 'The Testbed\'s Analysis of the Tool\'s Output identified the following Security Issues:\n'
            for issue in self.__security_issues:
                report += ToolTestRun.separator2 + \
                          f'\t{issue.title}\n'
                if issue.description:
                    report += f'\t\tDescription:\t{issue.description}\n'
                if issue.link:
                    report += f'\t\tFurther Information:\t{issue.link}\n'
        else:
            report = 'The Testbed\'s Analysis of the Tool\'s Output identified no Security Issue.\n'
        report += ToolTestRun.separator
        return report

    def get_solc_bin(self):
        if type(self._contract) == Contract:
            raise ValueError(f'{self._contract} must be a SolidityContract to call this method.')

        min_version, max_version = get_range_for_installed_solcs(self._contract.solc_from, self._contract.solc_to)
        if self._tool.solc_version:
            if min_version < self._tool.solc_version < max_version:
                version = self._tool.solc_version
            elif semver.VersionInfo.parse(self._tool.solc_version) < min_version:
                version = min_version
            else:
                version = max_version
        else:
            version = max_version
        return f'{solc_versions_dir}/{version}'

    def match_security_issues(self, text) -> List[SecurityIssue]:
        matches = set()
        for tool_security_issue in self._tool.tool_security_issues:
            if re.search(tool_security_issue.identifier, text):
                matches |= {tool_security_issue.security_issue}
        return sorted(matches, key=lambda s: s.title)

    def get_exceptions(self):
        self._check_terminated()
        return self._exceptions

    def match_errors(self, text) -> List[Error]:
        matches = set()
        for tool_error in self._tool.tool_errors:
            if tool_error.identifier and re.search(tool_error.identifier, text):
                matches |= {tool_error.error}
                if not tool_error.error:
                    print(f'ToolError: {tool_error}, Error: {tool_error.error}')
        return sorted(matches, key=lambda e: e.title)

    def create_docker_cmd(self, docker_image, tool_cmd: str, docker_opts=None, output_dir=None, solc_dir=None,
                          working_dir_to_output_dir=False):
        if docker_opts is None:
            docker_opts = []

        docker_contract_dir = '/testbed/contract'
        mount_contract = f'-v "{self._contract.dir_path}":{docker_contract_dir}'

        docker_solc_dir = '/root/solc-version'
        mount_solc = ''
        if self._contract.is_solidity_contract and solc_dir:
            mount_solc = f'-v "{solc_dir}":"{docker_solc_dir}"'

        docker_output_dir = '/testbed/output'
        mount_output = ''
        if output_dir:
            mount_output = f'-v "{output_dir}":"{docker_output_dir}"'

        working_dir = ''
        if working_dir_to_output_dir:
            if not mount_output:
                raise ValueError('output_dir must be provided when using working_dir_to_output_dir=True')
            working_dir = f'-w {docker_output_dir}'
        tool_cmd = tool_cmd.format(docker_contract_path=f'{docker_contract_dir}/{self._contract.filename}',
                                   output_dir=output_dir)
        if mount_solc:
            tool_cmd = f'bash -c "PATH={docker_solc_dir}:\$PATH;{tool_cmd}"'
        return f'sudo docker run --rm {" ".join(docker_opts)} {working_dir} {mount_solc} {mount_contract} {mount_output}' \
               f' {docker_image} {tool_cmd}'
