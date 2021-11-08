import argparse
import csv
import json
import os.path
import shutil
import time
from datetime import datetime
from typing import Dict

from tabulate import tabulate

import toolbox
from logic.orm import *
from logic.test_runner import TestRun

"""
    Summary
    -------
    This module allows users to use the testbed with the command-line.

"""

if __name__ == '__main__':

    def file_type_checker(path, extensions):
        if not os.path.exists(path):
            raise argparse.ArgumentTypeError(f'The File {path} does not exist.')
        if not os.access(path, os.R_OK):
            raise argparse.ArgumentTypeError(f'Can\'t read the file {path}.')
        if not re.match(r'.*\.(' + '|'.join(extensions) + r')', path):
            raise argparse.ArgumentTypeError(f'Path must be of type {extensions}')
        return os.path.abspath(path)


    def contract_file_type(path):
        return file_type_checker(path, Contract.file_extensions)


    def json_file_type(path):
        return file_type_checker(path, ['json'])


    def py_file_type(path):
        return file_type_checker(path, ['py'])


    def csv_file_type(path):
        return file_type_checker(path, ['csv'])


    def validate_dir(dir_path):
        if not os.path.isdir(dir_path):
            raise argparse.ArgumentTypeError(f'{dir_path} is not a directory')
        if not os.access(dir_path, os.W_OK) or not os.access(dir_path, os.R_OK):
            raise argparse.ArgumentTypeError('Missing read or write permissions to the directory.')
        return os.path.abspath(dir_path)


    def import_security_issues_or_errors(file, tool_name, add_security_issues, sess):
        """

        Parameters
        ----------
        file The CSV file containing the security issues and the regex patterns with which they can be identified from the tool's output.
        tool_name The name of the tool.
        add_security_issues True - if security issues are added. False - if errors are added.
        sess The database session.

        Returns
        -------

        """
        with open(file, encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                title = row[0]
                identifier = row[1]
                if not identifier:
                    identifier = ''
                if add_security_issues and not sess.query(ToolSecurityIssue) \
                        .filter(ToolSecurityIssue.tool_name == tool_name,
                                ToolSecurityIssue.security_issue_title == title,
                                ToolSecurityIssue.identifier == identifier).first():
                    if not sess.query(SecurityIssue).filter(SecurityIssue.title == title).first():
                        raise argparse.ArgumentTypeError(
                            f'The security issue "{title}" must be added to the "security_issues" table first.')
                    obj = ToolSecurityIssue(tool_name=tool_name, security_issue_title=title, identifier=identifier)
                    sess.add(obj)
                elif not sess.query(ToolError) \
                        .filter(ToolError.tool_name == tool_name, ToolError.error_title == title,
                                ToolError.identifier == identifier).first():
                    if not sess.query(Error).filter(Error.title == title).first():
                        raise argparse.ArgumentTypeError(
                            f'The error "{title}" must be added to the "errors" table first.')
                    obj = ToolError(tool_name=tool_name, error_title=title, identifier=identifier)
                    sess.add(obj)

    # add the parameters for the command line tool
    parser = argparse.ArgumentParser('testbed.sh')
    tool_names = [tool.name for tool in get_tools()]
    subparsers = parser.add_subparsers(dest='sub_command')

    parser_analyze = subparsers.add_parser('analyze', help='Analyze a smart contract.')
    parser_analyze.add_argument('contract_path', type=contract_file_type,
                                help='Path to the file containing the smart contract.')
    parser_analyze.add_argument('-n', '--contract_name',
                                help='The name of the contract to be analyzed. Defaults to the first contract in the file.')
    parser_analyze.add_argument('-t', '--tools', action='extend', nargs='+', choices=tool_names,
                                help='The smart contract analyzing tools the testbed should use. Default are all tools. To choose several tools, use " " as a separator.')
    parser_analyze.add_argument('-o', '--output', type=validate_dir, default='.',
                                help='The directory to store the results.')

    parser_server = subparsers.add_parser('server', help='Start the server.')
    parser_server.add_argument('-t', '--timeout', help='Set the timeout of a test-run in secs.. Default: 10s', type=int,
                               default=30 * 60)
    parser_server.add_argument('-a', '--active_test_runs',
                               help='Limit the number of active test-runs on the server. Default: 10', type=int,
                               default=10)
    parser_server.add_argument('-p', '--port', help='The port on which the webserver should listen to.', type=int,
                               default=5000)

    parser_update = subparsers.add_parser('update', help='Install a new tool or update an old one.')
    parser_update.add_argument('name', help='The name of the tool.')
    parser_update.add_argument('-s', '--script', type=py_file_type,
                               help='The path to the script with the "get_tool_test_run" function. '
                                    'This function must return the subclass which interacts with the tool.'
                                    ' Required when adding a new tool.')
    parser_update.add_argument('-l', '--link', help='The link to the tool\'s homepage.')
    parser_update.add_argument('-b', '--bytecode', help='Specify if the tool can analyse byte-code files. '
                                                        'Defaults to "False" if the option is not provided.',
                               action='store_false')
    parser_update.add_argument('-a', '--analyses_all_contracts', action='store_false',
                               help='Specify if the tool analyses all contracts in a Solidity file. '
                                    'Defaults to "False" if the option is not provided.')
    parser_update.add_argument('-sol', '--solidity',
                               help='The tools preferred Solidity compiler version. '
                                    '   Must be one of the installed compilers in "resources/solc-versions". '
                                    'Leave empty if the tool does not have a preferred version.',
                               default='')
    parser_update.add_argument('-i', '--tool_security_issues', type=csv_file_type,
                               help='A CSV-file with the security issues a tool looks for. Can only be called when '
                                    'the testbed already knows the tool. To tell the testbed about the tool, '
                                    'use "update <tool-name> <optional parameters>. The first column of the CSV file represents '
                                    'the title, the second one the identifier. For more information see the thesis: "'
                                    'Testbed for Security Testing of Smart Contracts" by Lukas Denk. Look in chapter Implementation->'
                                    'The Command-Line-Interface-> Options of the Command-Line Interface.')
    parser_update.add_argument('-e', '--tool_errors', type=csv_file_type,
                               help='Similar to --tool_security_issue, only that the CSV-File should contain the errors the tool might encounter'
                                    ' during the testing process.')

    parser_remove = subparsers.add_parser('remove', help='Remove an embedded tool.')
    parser_remove.add_argument('tool', choices=tool_names, help='The tool to remove.')

    # get the requested subparser and process the given command accordingly
    args = parser.parse_args()
    attributes = vars(args)
    if args.sub_command == 'analyze':
        if not args.tools:
            tools = get_tools()
        else:
            tools = get_tools(args.tools)
        if not args.contract_name:
            args.contract_name=os.path.splitext(os.path.basename(args.contract_path))[0]
        output = f'{os.path.abspath(args.output)}/{args.contract_name}-{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}'
        os.mkdir(output)
        if os.path.splitext(args.contract_path)[1] in SolidityContract.file_extensions:
            contract = SolidityContract(path=args.contract_path, name=args.contract_name)
        else:
            contract = Contract(path=args.contract_path)
        test_run = TestRun(contract, tools)
        test_run.run()
        terminated_tools_last_poll = set()
        terminated_tools = set()
        duration = 0
        while len(terminated_tools) != len(tools) or duration == 0:
            terminated_tools = set(test_run.get_terminated_tools())
            if duration % 60 == 1:
                print(
                    f'Checking for tools to finish. Still running: {",".join([tool.name for tool in sorted(set(tools) - terminated_tools, key=lambda t: t.name)])}')
            time.sleep(1)
            duration += 1
            recently_terminated_tools = terminated_tools - terminated_tools_last_poll
            terminated_tools_last_poll = terminated_tools
            for tool in recently_terminated_tools:
                tool_test_run = test_run.get_tool_test_run(tool)
                report_file = f'{output}/{tool.name}.txt'
                shutil.copyfile(tool_test_run.get_report(), report_file)
                print(
                    f'Tool {tool.name} has terminated in {toolbox.timedelta_to_string(tool_test_run.get_execution_time())}.\n'
                    f'The report-file can be seen here: {report_file}\n')

        table_dicts: Dict[SecurityIssue, Dict[Tool, str]] = test_run.get_security_issues_statuses()
        table = []
        headers = ['Security Issues']
        done = False
        for issue, tool_status_dict in table_dicts.items():
            table += [[issue.title] + list(iter(tool_status_dict.values()))]
            if not done:
                headers += tools_to_tool_names(iter(tool_status_dict.keys()))
                done = True
        tab = tabulate(table, headers)
        print(tab)
        summary_path = f'{output}/summary.txt'
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(tab)
        print(f'Testing {contract.path} has terminated.')


    elif args.sub_command == 'server':
        server_config = {'allowed_active_test_runs': args.active_test_runs, 'timeout': args.timeout}
        with open('server/config.json', 'w', encoding='utf-8') as f:
            f.write(json.dumps(server_config))
        from server.web_pages import app

        app.run(host='0.0.0.0', debug=True, port=args.port)

    elif args.sub_command == 'update':
        sess = get_db_session()
        sess.commit()
        tool = sess.query(Tool).filter(Tool.name == args.name).first()
        added = False
        if tool:
            if hasattr(args, 'script') and args.script:
                tool.script = args.script
        else:
            if hasattr(args, 'script') and args.script:
                tool = Tool(name=args.name, script=args.script)
                added = True
            else:
                raise argparse.ArgumentError('"--script" must be provided when a new tool is added.')
        if hasattr(args, 'link') and args.link:
            tool.link = args.link
        tool.analyses_whole_file = args.analyses_all_contracts
        tool.bytecode_compatible = args.bytecode
        if added:
            sess.add(tool)
        sess.commit()
        if args.solidity:
            tool.solc_version = args.solidity
        if hasattr(args, 'tool_security_issues') and args.tool_security_issues:
            import_security_issues_or_errors(args.tool_security_issues, tool.name, True, sess)
            sess.commit()
            print(f'Successfully imported {args.tool_security_issues}.')
        if hasattr(args, 'tool_errors') and args.tool_errors:
            import_security_issues_or_errors(args.tool_errors, tool.name, False, sess)
            sess.commit()
            print(f'Successfully imported {args.tool_errors}.')
        if added:
            print(f'Successfully added {tool}.')
        else:
            print(f'Successfully updated {tool}')

    elif args.sub_command == 'remove':
        sess = get_db_session()
        sess.query(Tool).filter(Tool.name == args.tool).delete()
        sess.commit()
        print(f'Successfully removed tool {args.tool}.')
