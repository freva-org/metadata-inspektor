"""Metadata inspector."""

import argparse
import json
import logging
import sys
import warnings
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, TextIO, Tuple, Union

import numpy as np
import xarray as xr
from cftime import num2date
from dask import array as dask_array
from hurry.filesize import alternative, size

from ._slk import get_slk_metadata, login
from ._version import __version__
from .utils import open_mfdataset

Logger = logging.getLogger("metadata-inspector")
Logger.setLevel(1000)


def _summarize_datavar(name: str, var: xr.DataArray, col_width: int) -> str:
    out = [xr.core.formatting.summarize_variable(name, var.variable, col_width)]
    if var.attrs:
        n_spaces = 0
        for k in out[0]:
            if k == " ":
                n_spaces += 1
            else:
                break
        out += [
            n_spaces * " " + line
            for line in xr.core.formatting.attrs_repr(var.attrs).split("\n")
        ]
    return "\n".join(out)


def parse_args(
    args: Optional[List[str]] = None,
) -> Tuple[List[Union[Path, str]], bool]:
    """Construct command line argument parser."""

    argp = argparse.ArgumentParser
    app = argp(
        prog="metadata-inspector",
        description=(
            "Inspect meta data of a weather/climate datasets "
            "with help of xarray"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    app.add_argument(
        "input",
        metavar="input",
        type=str,
        nargs="+",
        help="Input files that will be processed",
    )
    app.add_argument(
        "--html",
        action="store_true",
        help="Create html representation of the dataset.",
    )
    app.add_argument(
        "--version",
        "-V",
        action="version",
        version="%(prog)s {version}".format(version=__version__),
    )
    app.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Turn on debug mode for more information.",
    )
    parsed_args = app.parse_args(args)
    if parsed_args.verbose:
        Logger.setLevel(logging.ERROR)
    else:
        Logger.setLevel(1000)
    return parsed_args.input, parsed_args.html


def dataset_from_hsm(input_file: str) -> xr.Dataset:
    """Create a dataset view from attributes."""
    global_attrs: Dict[str, Dict[str, str]] = get_slk_metadata(input_file)
    attrs = json.loads(global_attrs.pop("document", {}).pop("Keywords", "{}"))
    nc_attrs = {}
    for key in ("netcdf", "netcdf_header"):
        for k, value in global_attrs.get(key, {}).items():
            nc_attrs[k] = value
    dset = xr.Dataset({}, attrs=attrs.pop("global", {}) or nc_attrs)
    for dim in attrs.pop("dims", []):
        size = int(attrs[dim].pop("size"))
        start, end = float(attrs[dim].pop("start")), float(attrs[dim].pop("end"))
        vec = np.linspace(start, end, size)
        if dim == "time":
            vec = num2date(vec, attrs[dim]["units"], attrs[dim]["calendar"])
        dset[dim] = xr.DataArray(vec, name=dim, dims=(dim,), attrs=attrs[dim])
    for data_var in attrs.pop("data_vars", []):
        dims = attrs[data_var].pop("dims")
        sizes = [dset[d].size for d in dims]
        dset[data_var] = xr.DataArray(
            dask_array.empty(sizes),
            name=data_var,
            dims=dims,
            attrs=attrs[data_var],
        )
    return dset


def _get_files(input_: list[Union[str, Path]]) -> Tuple[List[str], List[str]]:
    """Get all files from given input"""

    files_fs: List[str] = []
    files_archive: List[str] = []
    extensions: Tuple[str, ...] = (
        ".nc",
        ".nc4",
        ".grb",
        ".grib",
        ".grib2",
        ".grb2",
        ".h5",
        ".hdf5",
    )
    for inp_file in map(str, input_):
        schema, _, path = inp_file.rpartition("://")
        schema = schema or "file"
        if schema in ["file", "slk", "hsm"]:
            path = str(Path(path).expanduser().absolute())
        inp = Path(path)
        if schema in ("hsm", "slk") or inp.parts[1] == "arch":
            files_archive.append(path)
        elif inp.exists() and inp.suffix in (".zarr",):
            files_fs.append(path)
        elif inp.is_dir() and inp.exists():
            files_fs += [
                str(inp_file)
                for inp_file in inp.rglob("*")
                if inp_file.suffix.lower() in extensions
            ]
        elif inp.is_file() and inp.exists():
            files_fs.append(str(inp))
        elif inp.parent.exists() and inp.parent.is_dir():
            files_fs += [
                str(inp_file)
                for inp_file in inp.parent.rglob(inp.name)
                if inp_file.suffix in extensions
            ]
        else:
            files_fs.append(inp_file)
    return sorted(files_fs), sorted(files_archive)


def _open_datasets(files_fs: List[str], files_hsm: List[str]) -> xr.Dataset:
    dsets: list[xr.Dataset] = []
    if files_fs:
        dsets.append(open_mfdataset(files_fs))
    if files_hsm:
        login()
        for inp_file in files_hsm:
            dsets.append(dataset_from_hsm(inp_file))
    return xr.merge(dsets)


def main(
    input_files: List[Union[str, Path]], html: bool = False
) -> Tuple[str, TextIO]:
    """Print the representation of a dataset.

    Parameters
    ----------

    input_files: list[Path]
        Collection of input files that are to be inspected
    html: bool, default: True
        If true a representation suitable for html is displayed.
    """
    xr.core.formatting.EMPTY_REPR = "    *not enough information for display*"
    files_fs, files_hsm = _get_files(input_files)
    if not files_fs and not files_hsm:
        return "No files found", sys.stderr
    try:
        dset = _open_datasets(files_fs, files_hsm)
    except Exception as error:

        Logger.exception(error)
        error_header = (
            "No data found, file(s) might be corrupted. "
            "See err. message below:"
        )
        error_msg = str(error)
        if html:
            error_msg = error_msg.replace("\n", "<br>")
            msg = (
                "<p><b>Error:</b>Could not open dataset for more details "
                "do not use the --html flag.</p>"
            )
            return msg, sys.stdout

        else:
            msg = f"{error_header}\n{error_msg}"
            return msg, sys.stderr
    if dset.nbytes == 0:
        fsize = dset.attrs.pop("file_size", "unkown")
    else:
        fsize = size(dset.nbytes, system=alternative)
    if html:
        out_str = xr.core.formatting_html.dataset_repr(dset)
    else:
        xr.core.options.OPTIONS["display_expand_data_vars"] = True
        xr.core.options.OPTIONS["display_expand_attrs"] = True
        xr.core.options.OPTIONS["display_expand_data"] = True
        xr.core.options.OPTIONS["display_max_rows"] = 100
        xr.core.formatting.data_vars_repr = partial(
            xr.core.formatting._mapping_repr,
            title="Data variables",
            summarizer=_summarize_datavar,
            expand_option_name="display_expand_data_vars",
        )
        out_str = xr.core.formatting.dataset_repr(dset)
    replace_str = (
        ("xarray.Dataset", f"Dataset (dataset-size: {fsize})"),
        (
            "<svg class='icon xr-icon-file-text2'>",
            "<i class='fa fa-file-text-o'>",
        ),
        ("<svg class='icon xr-icon-database'>", "<i class='fa fa-database'>"),
        ("</use></svg>", "</use></i>"),
        ("numpy.", ""),
        ("np.", ""),
        ("dask.", ""),
    )
    for entry, replace in replace_str:
        out_str = out_str.replace(entry, replace)

    return out_str, sys.stdout


def cli(args: Optional[List[str]] = None) -> None:
    """Command line argument inteface."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        try:
            msg, text_io = main(*parse_args(args))
        except Exception as error:
            msg, text_io = f"Error: {error}", sys.stderr
            Logger.exception(error)
    print(msg, file=text_io, flush=True)
