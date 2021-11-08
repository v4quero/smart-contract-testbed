import os
from datetime import timedelta
from typing import Union, Tuple

import semver

"""
summary
-------
This module provides useful methods which didn't fit in any other module
"""

test_bed_path = os.path.realpath(os.path.dirname(__file__))
tools_path = '{}/resources/tools'.format(test_bed_path)
test_contracts_rel_path = 'resources/tests/contracts'
server = False
test_mode = False

def get_range_for_installed_solcs(min_version: Union[semver.VersionInfo, str],
                                  max_version: Union[semver.VersionInfo, str]) -> Tuple[
    semver.VersionInfo, semver.VersionInfo]:
    """finds the minimal and maximal installed solidity compiler version between min_version and max_version

    Parameters
    ----------
    min_version : semver.VersionInfo or str
    max_version : semver.VersionInfo or str

    Returns
    -------
    Tuple[semver.VersionInfo, semver.VersionInfo]

    Raises
    -------
    NotImplementedError
        If there are no installed solidity compilers between min_version and max_version

    """
    if type(min_version) == str:
        min_version = semver.VersionInfo.parse(min_version)
    if type(max_version) == str:
        max_version = semver.VersionInfo.parse(max_version)

    versions = [semver.VersionInfo.parse(v) for v in os.listdir('{}/resources/solc-versions'.format(test_bed_path))]
    min_installed_version = min(versions)
    max_installed_version = max(versions)
    try:
        new_min_version = min(filter(lambda v: min_version <= v, versions))
        new_max_version = max(filter(lambda v: v <= max_version, versions))
    except ValueError:
        raise NotImplementedError(
            'There is no installed version >={} and <={}. The minimal (maximal) installed version is {} ({})'.format(
                min_version, max_version, min_installed_version, max_installed_version))
    return new_min_version, new_max_version


def timedelta_to_string(td: timedelta):
    minutes, seconds = divmod(td.total_seconds(), 60)
    milliseconds = (td / timedelta(milliseconds=1)) % 1000
    string = ''
    if minutes > 0:
        string += f'{int(minutes)} min. and '
    if seconds > 0:
        string += f'{int(seconds)} secs. and '
    string += f'{int(milliseconds)} millisecs.'
    return string
