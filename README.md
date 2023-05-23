# perceval-public-inbox

Perceval backend for public-inbox repositories.

## Backends

The backend currently managed by this package support the next repository:

* public-inbox

## Requirements

 * Python >= 3.7

You will also need some other libraries for running the tool, you can find the
whole list of dependencies in [pyproject.toml](pyproject.toml) file.

## Installation

There are several ways to install perceval-public-inbox on your system: packages or source 
code using Poetry or pip.

### PyPI

perceval-public-inbox can be installed using pip, a tool for installing Python packages. 
To do it, run the next command:
```
$ pip install perceval-public-inbox
```

### Source code

To install from the source code you will need to clone the repository first:
```
$ git clone https://github.com/bitergia-analytics/grimoirelab-perceval-public-inbox
$ cd grimoirelab-perceval-public-inbox
```

Then use pip or Poetry to install the package along with its dependencies.

#### Pip
To install the package from local directory run the following command:
```
$ pip install .
```
In case you are a developer, you should install perceval-public-inbox in editable mode:
```
$ pip install -e .
```

#### Poetry
We use [poetry](https://python-poetry.org/) for dependency management and 
packaging. You can install it following its [documentation](https://python-poetry.org/docs/#installation).
Once you have installed it, you can install perceval-public-inbox and the dependencies in 
a project isolated environment using:
```
$ poetry install
```
To spaw a new shell within the virtual environment use:
```
$ poetry shell
```

## Example

### Public Inbox

```
$ perceval public-inbox
```

## License

Licensed under GNU General Public License (GPL), version 3 or later.
