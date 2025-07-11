"""Module that interacts with slk.

Until we do have access to the rest api we'll have to rely on the command line
tools.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import warnings
from datetime import datetime, timedelta
from getpass import getuser
from pathlib import Path
from subprocess import PIPE, SubprocessError, run

import requests
from hurry.filesize import alternative, size

SLK_HELPERS_BIN = "/sw/spack-levante/slk_helpers-1.9.3-5hmec4/bin"
SLK_BIN = "/sw/spack-levante/slk-3.3.91-wuylnb/bin/slk"
JDK_BIN = "/sw/spack-levante/openjdk-17.0.0_35-k5o6dr/bin"
JAVA_HOME = "/sw/spack-levante/openjdk-17.0.0_35-k5o6dr"
SLK = "slk"

SESSION_PATH = Path("~").expanduser() / ".slk" / "config.json"


def get_env() -> dict[str, str]:
    """Load the slk module."""
    env: dict[str, str] = os.environ.copy()
    if shutil.which("slk") is not None:
        return env  # pragma: no cover
    env["PATH"] = f"{SLK_BIN}:{SLK_HELPERS_BIN}:{JDK_BIN}:{env['PATH']}"
    env["JAVA_HOME"] = JAVA_HOME
    return env


def get_file_size(input_path: str) -> str:
    """Extract the size of an object on the HSM store.

    Parameters
    ----------
    input_path: str
        The path to the hsm ojbect

    Returns
    -------
    str: A string representation of the size of the ojbect
    """
    env = get_env()
    helpers_cmd = shutil.which("slk_helpers", path=env["PATH"])
    command = [helpers_cmd or "slk_helpers", "size", input_path]
    try:
        res = run(command, env=env, check=True, stdout=PIPE, stderr=PIPE)
    except SubprocessError as error:  # pragma: no cover
        warnings.warn(
            f"Error: could not get meta-data: {error}"
        )  # pragma: no cover
        return "unkown"  # pragma: no cover
    try:
        fsize = int(res.stdout.decode().strip() or "0")
    except TypeError:  # pragma: no cover
        return "unkown"  # pragma: no cover
    return size(fsize, system=alternative)


def get_slk_metadata(input_path: str) -> dict[str, dict[str, str]]:
    """Extract dataset metdata from path in the hsm.

    Parameters
    ----------
    input_path: str
        The hsm path the metdata is extracted from


    Returns
    -------
    str: string representation of the metdata
    """
    env = get_env()
    helpers_cmd = shutil.which("slk_helpers", path=env["PATH"])
    command = [helpers_cmd or "slk_helpers", "metadata", input_path]
    try:
        res = run(command, env=env, check=True, stdout=PIPE, stderr=PIPE)
    except SubprocessError as error:  # pragma: no cover
        warnings.warn(
            f"Error: could not get meta-data: {error}"
        )  # pragma: no cover
        return {}  # pragma: no cover
    # This needs to be done because the output of the command is only nearly
    # yaml. That is the ":" for the first keys are missing:
    # For example:
    # document
    #      Version: foo
    # netcdf
    #     id: bar
    #     var_name: tas
    # Since yaml needs could not handle this we have to add the ':' to the
    # keys manually.
    data: dict[str, dict[str, str]] = {}
    data.setdefault("netcdf", {})
    for line in res.stdout.decode().split("\n"):
        if line.startswith("netcdf") or line.startswith("document"):
            main_key = line.strip()
            data[main_key] = {}
            continue
        if line and not line[0].strip():
            key, _, value = line.partition(":")
            current_key = key.strip()
            data[main_key][current_key] = value.strip()
        elif line:
            data[main_key][current_key] += line.strip()
    data["netcdf"]["file_size"] = get_file_size(input_path)
    return data


def get_expiration_date() -> datetime:
    """Get the expiration date of the session key."""
    session_path = Path("~").expanduser() / ".slk" / "config.json"
    now = datetime.now()
    for fmt in ("%a %b %d %H:%M:%S %Z %Y", "%a %b %d %H:%M:%S %Y"):
        try:
            with session_path.open() as f_obj:
                date = json.load(f_obj).get("expireDate", now.strftime(fmt))
            return datetime.strptime(date, fmt)
        except FileNotFoundError:  # pragma: no cover
            break  # pragma: no cover
        except ValueError:  # pragma: no cover
            pass  # pragma: no cover
    return now


def _login_via_request(passwd: str) -> None:
    data = {
        "data": {
            "attributes": {
                "domain": "ldap",
                "name": getuser(),
                "password": passwd,
            },
            "type": "authentication",
        }
    }
    headers = {"Content-type": "application/json"}
    fmt = "%a %b %d %H:%M:%S %Z %Y"
    exp_date = (datetime.now() + timedelta(days=20)).astimezone().strftime(fmt)
    url = "https://archive.dkrz.de/api/v2/authentication"
    res = requests.post(url, data=json.dumps(data), headers=headers, verify=False)
    key = res.json().get("data", {}).get("attributes", {}).get("session_key", "")
    if key:
        sec = {"user": getuser(), "sessionKey": key, "expireDate": exp_date}
        SESSION_PATH.parent.mkdir(exist_ok=True, parents=True)
        with SESSION_PATH.open("w") as f_obj:
            json.dump(sec, f_obj)
        SESSION_PATH.chmod(0o600)


def login() -> None:
    """Login to the system."""
    passwd = os.environ.get("LC_TELEPHONE", "")
    now = datetime.now()
    exp_date = get_expiration_date()
    diff = (exp_date - now).total_seconds()
    env = get_env()
    slk_cmd = shutil.which("slk", path=env["PATH"])
    if passwd:
        passwd = base64.b64decode(passwd.encode()).decode()
        _login_via_request(passwd)
    elif diff <= 0:
        print("Your session has expired, login to slk")
        run([slk_cmd or "slk", "login"], shell=False, check=True, env=get_env())
