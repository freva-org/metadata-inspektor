# metadata-inspektor

[![Pipeline](https://github.com/freva-org/metadata-inspektor/actions/workflows/tests.yml/badge.svg)](https://github.com/freva-org/metadata-inspektor/actions)
[![codecov](https://codecov.io/gh/freva-org/metadata-inspektor/branch/main/graph/badge.svg)](https://codecov.io/gh/freva-org/metadata-inspektor)
[![Conda](https://anaconda.org/conda-forge/metadata-inspector/badges/installer/conda.svg)](https://anaconda.org/conda-forge/metadata-inspector)
[![PyPI version](https://badge.fury.io/py/metadata-inspector.svg)](https://badge.fury.io/py/metadata-inspector)

A python based cli to inspect climate data metadata using xarray

## Using the command line interface.

The python package is supposed to be used as a command line interface.
Meta data of various datasets can be inspected. To inspect the meta data use the
`metadata-inspector` command:

```console
metadata-inspector --help
usage: metadata-inspector [-h] [--html] [--version] input [input ...]

Inspect meta data of a weather/climate datasets

positional arguments:
  input          Input files that will be processed

options:
  -h, --help     show this help message and exit
  --html         Create html representation of the dataset. (default: False)
  --version, -V  show program's version number and exit
```
