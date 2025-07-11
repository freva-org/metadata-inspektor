"""Tests for the command line interface."""

import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest


def test_cli(capsys: pytest.CaptureFixture, patch_file: Path) -> None:
    """Test the help stirng."""
    from metadata_inspector import cli

    with NamedTemporaryFile(suffix=".nc") as temp_file:
        cli([temp_file.name])
        cap = capsys.readouterr()
        assert cap.out == ""
        assert "No data found" in cap.err
        cli([temp_file.name, "--html"])
        cap = capsys.readouterr()
        assert cap.err == ""
        assert "Error" in cap.out
    with pytest.raises(SystemExit):
        cli(["--help"])


def test_zarr(zarr_file: Path, patch_file: Path) -> None:
    """Test reading a zarr file."""
    from metadata_inspector import main

    out, text_io = main([])
    assert out == "No files found"
    assert text_io == sys.stderr

    out, text_io = main([zarr_file], html=False)
    assert "precip" in out
    assert text_io == sys.stdout

    out, text_io = main([zarr_file], html=True)
    assert "html" in out


def test_netcdf(netcdf_files: Path, patch_file: Path) -> None:
    """Test reading netcdf files."""
    from metadata_inspector import main

    out, text_io = main([])
    assert out == "No files found"
    assert text_io == sys.stderr
    out, text_io = main([netcdf_files], html=False)
    assert "precip" in out
    assert text_io == sys.stdout

    out, text_io = main([netcdf_files], html=True)
    assert "html" in out
    out, text_io = main(["README.md", "-v"])
    assert text_io == sys.stderr


def test_login(patch_file: Path) -> None:
    """Test logging in to the hsm archive."""
    from metadata_inspector._slk import login

    assert not patch_file.is_file()
    login()
    assert patch_file.is_file()


def test_fileiter(netcdf_files: Path, patch_file: Path) -> None:
    """Test searchig for files."""
    from metadata_inspector import _get_files

    nc_files = sorted([str(f) for f in netcdf_files.rglob("*.nc")])
    out, _ = _get_files([netcdf_files])
    assert out == nc_files
    out, _ = _get_files([Path(f) for f in nc_files])
    assert out == nc_files
    out, _ = _get_files([netcdf_files / "*.nc"])
    assert out == nc_files


def test_s3() -> None:
    """Test s3 data."""
    from metadata_inspector import main

    out, text_io = main(
        ["s3://ncar-cesm2-lens/ocn/monthly/cesm2LE-ssp370-smbb-WTT.zarr", "-v"]
    )
    assert "WTT" in out


def test_hsm_with_key(patch_file: Path) -> None:
    """Test reading metadata from the hsm."""
    from metadata_inspector import main

    out, text_io = main([Path("/arch/foo/bar.tar")])
    assert "orog" in out


def test_hsm_without_key(patch_file: Path) -> None:
    from metadata_inspector import main

    out, text_io = main([Path("/arch/foo/bar.nc")])
    assert "ua" in out
