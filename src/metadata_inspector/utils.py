"""Utilities for opening datasets."""

from pathlib import Path
from typing import List, cast
from urllib.parse import urlparse

import fsspec
import xarray as xr


def open_with_xarray(uri: str) -> xr.Dataset:
    """Open one dataset with xarray."""
    parsed = urlparse(str(uri))
    scheme = parsed.scheme or "file"
    if Path(uri).exists():
        mapper = uri
    else:
        mapper = fsspec.get_mapper(
            uri, anon=True if scheme in {"s3", "gs"} else False
        )
    if uri.endswith(".zarr") or uri.endswith("/"):
        return xr.open_zarr(
            mapper,
            consolidated=False,
        )
    else:
        return xr.open_dataset(mapper)


def open_mfdataset(files: List[str]) -> xr.Dataset:
    """Open multiple datasets with xarray."""
    datasets = [open_with_xarray(f) for f in files]
    return cast(xr.Dataset, xr.combine_by_coords(datasets, data_vars="minimal"))
