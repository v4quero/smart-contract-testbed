# from fpdf import FPDF
import json
import shutil
import threading
import time
from datetime import datetime, timedelta
from typing import Dict

from flask import Flask, render_template, request, session, abort, send_file
from sqlalchemy.orm import subqueryload

import logic.orm as db
from logic.orm import *
from logic.test_runner import TestRun

"""
    Summary
    -------
    This module provides the server for the testbed.
    
"""
app = Flask(__name__)
app.config['SECRET_KEY'] = ',s@e@.5X5#T2[#kKbv%a[E2kj6e4,fUm'
app.config['SESSION_COOKIE_HTTPONLY'] = False


class OverloadError(Exception):
    pass


with open(f'{test_bed_path}/server/config.json', encoding='utf-8') as f:
    server_config = json.loads(f.read())


class TestRunsManager:
    """
        Manages all running TestRun instances.
        @raises
            OverloadError: Raised if there are more than <allowed_active_test_runs> TestRun instances running.
    """
    def __init__(self, allowed_active_test_runs=10):
        self.lock = threading.Lock()
        self.test_runs: Dict[float, TestRun] = {}
        self.allowed_active_test_runs = allowed_active_test_runs

    def put(self, test_run: TestRun):
        with self.lock:
            active_test_runs = 0
            for id in self.test_runs:
                if self.test_runs[id].get_status() != 'Terminated':
                    active_test_runs += 1
                id_datetime = datetime.fromtimestamp(id)
                if datetime.now() - id_datetime > timedelta(days=1):
                    test_run = self.test_runs.pop(id, None)
                    contract_path = test_run._contract.dir_path
                    shutil.rmtree(contract_path, ignore_errors=True)
            if active_test_runs > self.allowed_active_test_runs:
                raise OverloadError
            timestamp = time.time()
            self.test_runs[timestamp] = test_run
        return timestamp

    def get(self, timestamp) -> TestRun:
        return self.test_runs[timestamp]


test_runs_manager = TestRunsManager(server_config['allowed_active_test_runs'])
timeout = server_config['timeout']


@app.route('/')
@app.route('/upload')
def upload():
    """Creates the html web-page used to upload a smart contract.

    Returns
    -------
        See description above.

    """
    get_db_session()
    tools = db.get_tools()
    bytecode_incompatible_tool_names = [tool.name for tool in filter(lambda t: not t.bytecode_compatible, tools)]
    return render_template('upload.html', tools=tools,
                           bytecode_incompatible_tool_names=bytecode_incompatible_tool_names,
                           contract_extensions=','.join([f'.{extension}' for extension in Contract.file_extensions]))


@app.route('/results', methods=('POST',))
def results():
    """Requesting this method with an empty session or changed form parameters starts the analysis of the smart contract with the tools given by the form.
    All further requests will check for the statuses of the tools and the _security_issues they have found.

    Returns
    -------
        If requested with an empty session or changed form parameters: A web-page showing the tools which are used to analyze the contract.
        Otherwise: The statuses of the tools and the _security_issues they have found.

    """
    if 'id' in session:
        timestamp = session['id']
        try:
            test_run = test_runs_manager.get(timestamp)
        except KeyError:
            raise abort(404, 'ID not found. Maybe your session is expired.')
    else:
        sess = get_db_session()
        tools = sess.query(Tool).options(subqueryload(Tool.tool_errors).subqueryload(ToolError.error)). \
            options(subqueryload(Tool.tool_security_issues).subqueryload(ToolSecurityIssue.security_issue)).filter(
            Tool.name.in_(request.form.keys())).order_by(Tool.name).all()

        contract_name = None
        if 'contract_name' in request.form and request.form['contract_name']:
            contract_name = request.form['contract_name']
        file = request.files['file']
        contract_extension = file.filename[file.filename.rfind('.'):]
        tmd_dir = tempfile.mkdtemp()
        contract_path = f'{tmd_dir}/{file.filename}'
        file.save(contract_path)
        if contract_extension in SolidityContract.file_extensions:
            contract = SolidityContract(contract_path, name=contract_name)
        else:
            contract = Contract(contract_path)

        test_run = TestRun(contract, tools, timeout)
        try:
            id = test_runs_manager.put(test_run)
            session['id'] = id
        except OverloadError:
            abort(503)
        test_run.run()
    return render_template('results.html', test_run=test_run)


@app.route('/results/<tool_name>')
def get_result_file(tool_name):
    if 'id' not in session:
        raise abort(404, 'ID not in session')
    try:
        test_run = test_runs_manager.get(session['id'])
    except KeyError:
        abort(404, 'Invalid session ID')
    tool = get_tools([tool_name])[0]
    tool_test_run = test_run.get_tool_test_run(tool)
    return send_file(tool_test_run.get_report(), as_attachment=True,
                     attachment_filename=f'{test_run._contract.name}_{tool.name}_{datetime.now().strftime("%d.%m.%Y %H-%M-%S")}.txt',
                     )


if __name__ == '__main__':
    app.run(host='0.0.0.0')
