import os
import shutil
import tempfile
from typing import Dict, List, Union, Tuple

from logic.orm import Tool, SecurityIssue, ToolSecurityIssue, ToolError, SolidityContract, Contract, get_db_session, \
    Error
from logic.tools.tool_test_run import ToolTestRun
from logic.tools import maian, manticore, mythril, osiris, oyente, securify2, smartcheck


class TestRun:

    def __init__(self, contract: Union[SolidityContract, Contract], tools: List[Tool], timeout=None):
        self._contract = contract
        self._tools = tools
        self._tool_test_runs: Dict[Tool, ToolTestRun] = dict()
        self._started = False
        self.timeout = timeout
        if type(self._contract) == SolidityContract:
            self._tmp_dir = tempfile.mkdtemp()

    def __del__(self):
        if self._tmp_dir and os.path.exists(self._tmp_dir):
            shutil.rmtree(self._tmp_dir)

    def __create_tool_test_run(self, tool: Tool) -> ToolTestRun:
        if tool.name == 'maian':
            module = maian
        elif tool.name == 'manticore':
            module = manticore
        elif tool.name == 'mythril':
            module = mythril
        elif tool.name == 'osiris':
            module = osiris
        elif tool.name == 'oyente':
            module = oyente
        elif tool.name == 'securify2':
            module = securify2
        elif tool.name == 'smartcheck':
            module = smartcheck
        else:
            raise AttributeError(f'The tool {tool} is not imported in {__name__}.')
        return module.create_tool_test_run(self._contract, self.timeout)

    def run(self):
        self._started = True
        for tool in self._tools:
            tool_test_run: ToolTestRun = self.__create_tool_test_run(tool)
            self._tool_test_runs[tool] = tool_test_run
            tool_test_run.run()

    def get_terminated_tools(self) -> List[Tool]:
        terminated_tools = []
        for tool, tool_test_run in self._tool_test_runs.items():
            if tool_test_run.get_terminated():
                terminated_tools += [tool]
        return terminated_tools

    def get_tool_test_run(self, tool: Tool) -> ToolTestRun:
        return self._tool_test_runs[tool]

    def get_status(self) -> str:
        if not self._started:
            return 'Before Run'
        if len(self.get_terminated_tools()) < len(self._tools):
            return 'Running'
        return 'Terminated'

    def get_security_issues_statuses(self) -> Dict[SecurityIssue, Dict[Tool, str]]:
        """Returns the statuses of any _security_issues searched for by any of the tools of the <analyze>-method.

            The statuses:
                "loading" : The tool is still terminated.
                "found", "not found" : self-explaining
                "not checked" : The tool does not check for this error.

            Returns
            -------
            Dict[SecurityIssue,str]
                str is one of the statuses defined above.

            """
        security_issues_statuses = {}
        sess = get_db_session()

        # !!!
        security_issues = sess.query(SecurityIssue).join(ToolSecurityIssue).filter(
            ToolSecurityIssue.tool_name.in_([tool.name for tool in self._tools])) \
            .distinct().order_by(SecurityIssue.swc_id == None, SecurityIssue.swc_id, SecurityIssue.title,
                                 ToolSecurityIssue.tool_name).all()
        for issue in security_issues:
            security_issues_statuses[issue] = {}
            for tool in self._tools:
                if tool in issue.tools:
                    status = 'loading'
                else:
                    status = 'not checked'
                security_issues_statuses[issue][tool] = status

        for tool in self.get_terminated_tools():
            discovered_security_issues = self._tool_test_runs[tool].get_security_issues()
            for issue in security_issues:
                if issue in discovered_security_issues:
                    status = 'found'
                else:
                    if issue in tool.security_issues:
                        status = 'not found'
                    else:
                        status = 'not checked'
                security_issues_statuses[issue][tool] = status

        security_issues_statuses = {key: value for key, value in
                                    sorted(security_issues_statuses.items(), key=discovered_errors_count, reverse=True)}
        return security_issues_statuses

    def get_errors_statuses(self) -> Dict[Error, str]:
        """Returns the statuses of any _error searched for by any of the tools of the <analyze>-method.

            The statuses:
                "loading" : The tool is still terminated.
                "found", "not found" : self-explaining
                "not checked" : The tool does not check for this error.

            Returns
            -------
            Dict[Error,str]
                str is one of the statuses defined above.

            """
        error_statuses = {}
        sess = get_db_session()

        # !!!
        errors = sess.query(Error).join(ToolError).filter(
            ToolError.tool_name.in_([tool.name for tool in self._tools])) \
            .distinct().order_by(Error.title,
                                 ToolError.tool_name).all()
        for error in errors:
            error_statuses[error] = {}
            for tool in self._tools:
                if tool in error.tools:
                    status = 'loading'
                else:
                    status = 'not checked'
                error_statuses[error][tool] = status

        for tool in self.get_terminated_tools():
            discovered_errors = self._tool_test_runs[tool].get_errors()
            for error in errors:
                if error in discovered_errors:
                    status = 'found'
                else:
                    status = 'not found'
                error_statuses[error][tool] = status

        error_statuses = {key: value for key, value in
                          sorted(error_statuses.items(), key=discovered_errors_count, reverse=True)}
        return error_statuses


def discovered_errors_count(error_tool_status: Tuple[SecurityIssue, Dict[Tool, str]]) -> int:
    count = 0
    for tool, status in error_tool_status[1].items():
        if status == 'found':
            count += 1
    return count
