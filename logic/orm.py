import os
import re
import subprocess
import tempfile
from threading import Lock
from typing import List, Tuple, Optional, Union, Iterator

import semver
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Float, Table
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, sessionmaker, scoped_session, reconstructor

from toolbox import get_range_for_installed_solcs
from toolbox import test_bed_path

"""
    Summary
    -------
    Defines the classes Tool, SecurityIssue, ToolSecurityIssue and Contract. Defines an ORM-mapping between instances of this class and the underlying database.
    Also provides methods to query and modify the database.
"""

db_path = f'{test_bed_path}/resources/db.sqlite'

engine = create_engine('sqlite:///{}?check_same_thread=False'.format(db_path), echo=False)
Base = declarative_base()


class Tool(Base):
    """An installed smart contract analyzing tool.

    Attributes
    -------
    name : String
        The name of the tool.
    script : String
        The script of the tool is the paths to the bash-scripts or python module which runs the tool.
    solc_version : String, optional
        The solidity compiler version the tool prefers.
        The String must be in the format specified by semver.VersionInfo
    link : String, optional
        The link to the homepage of the tool.
    bytecode_compatible : Boolean, optional (default=False)
        Whether the tool can also test compiled smart contracts.
        If so, the contract must be compiled in hex decimals.
    only_bytecode : Boolean, optional (default=False)
        Whether the tool can only work with a bytecode contract.
    _security_issues, optional
        The _security_issues the tool looks for and the _security_issues which can occur when terminated the tool.
    tool_security_issues, optional
        The <ToolSecurityIssue>s associated with the tool.
    """

    __tablename__ = 'tools'
    name = Column(String, primary_key=True)
    script = Column(String, nullable=False)
    solc_version = Column(String)
    link = Column(String)
    bytecode_compatible = Column(Boolean, default=False)
    analyses_whole_file = Column(Boolean)

    security_issues = relationship('SecurityIssue', secondary='tool_security_issues', order_by='SecurityIssue.title',
                                   backref='tools', lazy='subquery')
    tool_security_issues = relationship('ToolSecurityIssue', cascade='all,delete,delete-orphan', backref='tool',
                                        lazy='subquery')

    errors = relationship('Error', secondary='tool_errors', order_by='Error.title', lazy='subquery', backref='tools')
    tool_errors = relationship('ToolError', cascade='all,delete,delete-orphan', backref='tool', lazy='subquery')

    def __str__(self):
        return f'Tool(name={self.name}, script={self.script}, link={self.link})'

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return type(other) == type(self) and self.__hash__() == other.__hash__()


class SecurityIssue(Base):
    """A possible error in the smart contract or an error caused by the execution of a tool.

    Attributes
    -------
    id : Integer
    swc_id : Integer, optional
        The SWC-ID of the error. <None> if the error cannot be classified with this schema.
    title : String
        The title of the error.
    description : String, optional
        A description of the error.
    link : String, optional
        A link providing further detail of the error.
    tools, optional
        The tools with which the error can occur.
    tool_security_issues, optional
        The <ToolSecurityIssue>s associated with the tool.

    """
    __tablename__ = 'security_issues'
    swc_id = Column(Integer)
    title = Column(String, primary_key=True)
    description = Column(String)
    link = Column(String)
    tool_security_issues = relationship('ToolSecurityIssue', cascade='all,delete,delete-orphan',
                                        backref='security_issue', lazy='subquery')

    def __str__(self):
        return f'SecurityIssue(swc_id={self.swc_id}, title={self.title})'

    def __hash__(self):
        return hash(self.title)

    def __eq__(self, other):
        return type(other) == type(self) and self.__hash__() == other.__hash__()


class ToolSecurityIssue(Base):
    """Represents that the many-to-many relationship of a tool and an error.

    The relationship between a tool and an error means that the tool can find the error or that the execution of the tool can result in the error.

    Attributes
    -------
    tools_name : String
        The name of the tool.
    errors_id : Integer
        The id of the error.
    identifier : String
        # TODO: remove identifier from ToolSecurityIssue, subclass ToolSecurityIssue as PatternToolError and store the identifier in this class
        A match of this identifier in the output-file produced by the script of the tool indicates that the tool found the error represented by errors_id.

    """
    __tablename__ = 'tool_security_issues'

    # TODO change attribute name to tool_name
    tool_name = Column(String, ForeignKey('tools.name'), primary_key=True)
    security_issue_title = Column(String, ForeignKey('security_issues.title'), primary_key=True)
    identifier = Column(String, primary_key=True, default='')

    def __str__(self):
        return 'ToolSecurityIssue(tools_name={}, security_issues_id={})'.format(self.tool_name,
                                                                                self.security_issue_title)

    def __hash__(self):
        return hash((self.tool_name, self.security_issue_title, self.identifier))

    def __eq__(self, other):
        return type(other) == type(self) and self.__hash__() == other.__hash__()


class Error(Base):
    __tablename__ = 'errors'

    title = Column(String, primary_key=True)
    description = Column(String)
    link = Column(String)
    testbed_level = Column(Boolean, default=False)
    tool_errors = relationship('ToolError', cascade='all,delete,delete-orphan', lazy='subquery', backref='error')

    def __str__(self):
        return f'Error(title={self.title})'

    def __hash__(self):
        return hash(self.title)

    def __eq__(self, other):
        return type(other) == type(self) and self.__hash__() == other.__hash__()


class ToolError(Base):
    __tablename__ = 'tool_errors'

    tool_name = Column(String, ForeignKey('tools.name'), primary_key=True)
    error_title = Column(String, ForeignKey('errors.title'), primary_key=True)
    identifier = Column(String, primary_key=True, default='')

    # id_is_regex = Column(Boolean,default=True)
    # error=relationship('Error')

    def __str__(self):
        return f'ToolError(tool_name={self.tool_name}, error_title={self.error_title})'

    def __hash__(self):
        return hash(self)

    def __eq__(self, other):
        return type(other) == type(self) and self.__hash__() == other.__hash__()


class Contract(Base):
    """A smart contract.

    Attributes
    ----------
    path : String
        The absolute path to the file of the contract.
    name : String
        The name of the contract.
    # TODO (eventually): subclass Contract to Solidity Contract and Bytecode Contract
    solc_from : String, optional
        Must be a semver.VersionInfo compatible String  or None.
        The minimal solidity compiler version allowed to compile this contract.
        None, if the contract is in bytecode format
    solc_to : String, optional
        Same as solc_from but indicates the maximal solidity compiler version allowed to compile the contract.
    address : String, optional
        The address of the contract on the Ethereum blockchain, if it is already deployed.
    source : String, optional
        The source where the contract code comes from.
    filename
    dir_path
    filename_extension
    is_bytecode

    Class Attributes
    ----------------
    bytecode_extensions : List[String]
        file extensions indicating that the contract is in bytecode format.
    file_extensions : List[String]
        all allowed file extensions

    """

    path = Column(String, primary_key=True)
    # TODO: subclass. name -> SolidityContract?
    address = Column(String, unique=True)
    # TODO: rename to reference
    source = Column(String)
    size = Column(Integer)
    class_type = Column(String)

    __tablename__ = 'contracts'

    __mapper_args__ = {
        'polymorphic_identity': 'contract',
        'polymorphic_on': class_type
    }

    bytecode_extensions = ['hex', 'bin']
    file_extensions = bytecode_extensions + ['sol']

    def __init__(self, path, address=None, source=None, size=None):
        self.path = path
        self.address = address
        self.source = source
        self.size = size

    @hybrid_property
    def filename(self):
        return os.path.basename(self.path)

    @hybrid_property
    def dir_path(self):
        return os.path.dirname(self.path)

    @hybrid_property
    def filename_extension(self):
        return self.path[self.path.rfind('.') + 1:]

    @hybrid_property
    def is_solidity_contract(self):
        return type(self) == SolidityContract

    def __str__(self):
        return f'Contract(path={self.path}, size={self.size})'

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        return type(other) == type(self) and hash(self) == hash(other)


class SolidityContract(Contract):
    path = Column(String, ForeignKey('contracts.path'), primary_key=True)
    name = Column(String, primary_key=True, nullable=False)
    solc_from = Column(String, nullable=False)
    solc_to = Column(String, nullable=False)
    file_extensions = ['.sol']

    __tablename__ = 'solidity_contracts'
    __mapper_args__ = {
        'polymorphic_identity': 'solidity_contract'
    }

    def __init__(self, path, address=None, source=None, name=None):
        super().__init__(path, address=address, source=source)
        if name is None:
            name = self._get_name_of_first_contract()
        self.name = name

        self.solc_from = None
        self.solc_to = None
        self._assign_contract_solcs_range()
        self.init_on_load()

    @reconstructor
    def init_on_load(self):
        self.tmp_dir = None
        self._lock = Lock()

    def __str__(self):
        return f'SolidityContract(path={self.path},name={self.name}, size={self.size})'

    def _get_name_of_first_contract(self):
        """finds the name of the first contract in a .sol-file

        Parameters
        ----------
        contract : Contract
            contract.path must point to a .sol file

        Returns
        -------
        str
            the name of the first contract in the .sol-file

        Raises
        ------
        ValueError
            If contract.path does not point to a .sol-file or
            if no contract can be found in the file
        """

        with open(self.path, encoding='utf-8') as f:
            uncommented = '{}\n'.format(re.sub(r'\/\/.*$', '', f.read(), flags=re.MULTILINE))
            uncommented = re.sub(r'/\*.*?\*/', ' ', uncommented, flags=re.DOTALL)

            matcher = re.findall(r'\bcontract\b\s+(\w[\w\d]*)\b', uncommented)
            if matcher:
                return matcher[0]
            else:
                raise ValueError('Could not find the contract\'s name of {}'.format(self))

    def _assign_contract_solcs_range(self) -> Tuple[semver.VersionInfo, semver.VersionInfo]:
        """extracts the minimal and maximal solidity compiler version allowed to compile the contract

        Parameters
        ----------
        contract : Contract

        Returns
        -------
        Tuple[semver.VersionInfo, semver.VersionInfo]
            the minimal and maximal solidity compiler version allowed to compile the contract

        Raises
        -------
        NotImplementedError
            If the pragma directive is either invalid or there are several pragma directives but no solidity compiler version satisfying every directive.
        """
        with open(self.path, encoding='utf-8') as f:
            lines = f.readlines()
        min_version = semver.VersionInfo.parse('0.0.0')
        max_version = semver.VersionInfo.parse('99.99.99')
        for line in lines:
            version_regex = r'(?:<|>|<=|>=|==?|!=|\^)?\d\.\d+\.\d+\b'
            if re.search(r'pragma\s+solidity\s+' + version_regex, line):
                comparators = re.findall(version_regex, line)
                for comparator in comparators:
                    version = semver.VersionInfo.parse(re.findall(r'\d\.\d+\.\d+\b', comparator)[0])
                    if re.search(r'<=', comparator):
                        max_version = min(version, max_version)
                    elif re.search(r'>=', comparator):
                        min_version = max(version, min_version)
                    elif re.search(r'<', comparator):
                        if version.patch == 0:
                            max_version = min(version.replace(minor=version.minor - 1, patch=99), max_version)
                        else:
                            max_version = min(version.replace(patch=version.patch - 1), max_version)
                    elif re.search(r'>', comparator):
                        if version.patch == 99:
                            min_version = max(version.replace(minor=version.minor + 1, patch=0), min_version)
                        else:
                            min_version = max(version.replace(patch=version.patch + 1), min_version)
                    elif re.search(r'!=', comparator):
                        raise NotImplementedError('pragma version directive "!=" is not supported!')
                    elif re.search(r'\^', comparator):
                        min_version = max(version, min_version)
                        max_version = min(version.replace(patch=99), max_version)
                    else:
                        # if there is =,== or no comparator before x.x.x:
                        min_version = max(version, min_version)
                        max_version = min(version, max_version)

        if min_version > max_version:
            raise ValueError(
                f'{self}: Pragma directive is either invalid or there are several pragma directives but no solidity compiler version satisfying every directive.')
        self.solc_from = str(min_version)
        self.solc_to = str(max_version)

    # TODO: move to SolidityContract and change, eigenes dir
    def get_bytecode_file(self) -> str:
        """compiles a .sol-contract and stores the .bin results in output_dir
        Parameters
        ----------
        contract : Contract
        output_dir : str
            The path to the output directory
        """
        with self._lock:
            if not self.tmp_dir:
                self.tmp_dir = tempfile.mkdtemp()
                print(self.solc_from, self.solc_to)
                min_version, _ = get_range_for_installed_solcs(self.solc_from, self.solc_to)
                subprocess.run(
                    f'"{test_bed_path}/resources/solc-versions/{min_version}/solc" -o "{self.tmp_dir}" --bin "{self.path}"',
                    shell=True
                    , stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
            bin_path = f'{self.tmp_dir}/{self.name}.bin'
            if not os.path.exists(bin_path):
                raise FileNotFoundError(
                    f'{bin_path} should contain the compiled contract {self.name} from {self.filename} but does not. Used solc version: {min_version}')
            if os.path.getsize(bin_path) == 0:
                raise ValueError(
                    f'Compiling contract {self.name} in {self.filename} with solc-version {min_version} returned an empty bin file. '
                    f'A possible reason is that the contract is an interface or contains abstract methods.')
            return bin_path


evaluations_security_issues = Table('evaluations_security_issues', Base.metadata,
                                    Column('evaluations_id', Integer, ForeignKey('evaluations.id')),
                                    Column('security_issues_title', String, ForeignKey('security_issues.title')))

evaluations_errors = Table('evaluations_errors', Base.metadata,
                           Column('evaluations_id', Integer, ForeignKey('evaluations.id')),
                           Column('errors_title', String, ForeignKey('errors.title')))


class Evaluation(Base):
    __tablename__ = 'evaluations'
    id = Column(Integer, primary_key=True, autoincrement=True)
    solidity_contract_path = Column(String, ForeignKey('solidity_contracts.path'))
    tool_name = Column(String, ForeignKey('tools.name'))
    execution_time = Column(Float)
    report_file = Column(String)
    used_solc = Column(String)
    security_issues = relationship('SecurityIssue', secondary='evaluations_security_issues')
    errors = relationship('Error', secondary='evaluations_errors')
    solidity_contract = relationship('SolidityContract')
    tool = relationship('Tool')


Base.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)


# TODO: remove server_request
def get_db_session() -> Session:
    return Session()


def get_error(error_title) -> Error:
    return get_db_session().query(Error).filter(Error.title == error_title).one()


def get_tools(tool_names: Union[Optional[List[str]], str] = 'all') -> List[Tool]:
    """

    Parameters
    ----------
    tool_names : List[str] or str, default='all'
        The names of the tools to be returned.
        "all" returns all installed tools.
    Returns
    -------
    List[Tool]
    """
    if tool_names == 'all':
        return get_db_session().query(Tool).order_by(Tool.name).all()
    else:
        return get_db_session().query(Tool).filter(Tool.name.in_(tool_names)).order_by(Tool.name).all()


def tools_to_tool_names(tools: Iterator[Tool]):
    return [tool.name for tool in tools]
