[![Unit Tests](https://github.com/mpm-tu-berlin/eflips-model/actions/workflows/unittests.yml/badge.svg)](https://github.com/mpm-tu-berlin/eflips-model/actions/workflows/unittests.yml) 
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# eflips-model

---

Part of the [eFLIPS/simBA](https://github.com/stars/ludgerheide/lists/ebus2030) list of projects.

---


This repository contains both the *reference specification*, an *SQLALchemy implementation* and a *usage example* of the eFLIPS database.

## Reference Specification

The reference specification is located (for now) in the huge PDF file [`schema.pdf`](schema.pdf). It is a UML diagram of the database schema. The diagram was created using [OmniGraffle](https://www.omnigroup.com/omnigraffle) (proprietary).

## SQLAlchemy Implementation

The SQLAlchemy implementation is located in the `eflips/model` directory. It is a Python package that contains the SQLAlchemy models and the database migration scripts. The package is structured as follows:

### Installation

Releases of the package will be made available on [https://pypi.org/](https://pypi.org/project/eflips-model/). As such, it is installable with `pip install eflips-model`. However, it should be used by including it in other packages as a dependency. The versioning scheme is [semantic versioning](https://semver.org/). This means that:

- patch releases (e.g. `1.0.0` to `1.0.1`) are backwards compatible bug fixes, without schama changes
- minor releases (e.g. `1.0.0` to `1.1.0`) are backwards compatible feature additions, with the schema changes being optional
- major releases (e.g. `1.0.0` to `2.0.0`) are backwards incompatible changes, with the schema changes being mandatory

Supported database backends are

- [PostgreSQL](https://www.postgresql.org) with the [PostGIS](https://postgis.net/) extension (`CREATE EXTENSION postgis;`)
  and `btree_gist` (`CREATE EXTENSION btree_gist;`)

### Usage

This package is not expected to be used directly. It is a dependency of the `eflips-*` packages.

This package utilizes GIS extensions through [GeoAlchemy](https://geoalchemy-2.readthedocs.io/en/latest/index.html).
However, we are not handling geometry on the python side in any special way. When developing a paclage that uses `eflips-model`, you will probably additionally
need [Shapely](https://shapely.readthedocs.io/en/stable/manual.html)
and [pyProj](https://pyproj4.github.io/pyproj/stable/), which are not pure python packages and require additional
dependencies to be installed on the system.

#### Schema updates

The schema updates are handled by [Alembic](https://alembic.sqlalchemy.org/en/latest/). The migration scripts are located in the `eflips/model/migrations` directory. To create a new migration script, execute the following commands in the root directory of the repository:

```bash
cd eflips/model
alembic revision --autogenerate -m "vx.y.z"
# Edit the migration script, as necessary
```

**Creating a migration script is required for every change to the database schema, which should also correspond to a minor or major version change in the package version.**

To apply the migration scripts, execute the following command in the root directory of the repository:

```bash
cd eflips/model
export DATABASE_URL=postgresql://user:pass@hostname:port/dbname # Change to your database URL
alembic upgrade head
```

### Testing

We use [pytest](https://docs.pytest.org/en/stable/) for testing. The tests are located in the `tests` directory. To run the tests, execute the following command in the root directory of the repository (after installing the `dev` dependencies):

---

**NOTE**: Be aware that the tests will clear the database specified in the `DATABASE_URL` environment variable. Make sure that you are not using a database that you want to keep.

---
 
```bash
# Change to your database URL
export DATABASE_URL=postgresql://user:pass@hostname:port/dbname 
pytest
```

### Documentation

Documentation is available on [Read the Docs](https://eflips-model.readthedocs.io/en/latest/).

To locally create the documentaiton from the docstrings in the code
using [sphinx-autoapi](https://sphinx-autoapi.readthedocs.io/en/latest/), you can create the documentation execute the
following command in the root directory of the repository:

```bash
sphinx-build doc/ doc/_build -W
```

### Development

We utilize the [GitHub Flow](https://docs.github.com/get-started/quickstart/github-flow) branching structure. This means  that the `main` branch is always deployable and that all development happens in feature branches. The feature branches are merged into `main` via pull requests. We utilize the [semantic versioning](https://semver.org/) scheme for versioning.

Dependencies are managed using [poetry](https://python-poetry.org/). To install the dependencies, execute the following command in the root directory of the repository:

```bash
poetry install
```

We use black for code formatting. You can use `black .` to format the code.

We use [MyPy](https://mypy.readthedocs.io/en/stable/) for static type checking. You can
use ` mypy --strict --explicit-package-bases  eflips/` to run MyPy on the code.

Please make sure that your `poetry.lock` and `pyproject.toml` files are consistent before committing. You can use `poetry check` to check this. This is also checked by pre-commit.

You can use [pre-commit](https://pre-commit.com/) to ensure that MyPy, Black, and Poetry are run before committing. To
install pre-commit, execute the following command in the root directory of the repository:

We recommend utilizing linters such as [PyLint](https://pylint.readthedocs.io/en/latest/index.html) for static code
analysis (but not
doing everything it says blindly).


## Usage Example

In [examples](examples/) a well-documented (german-language) [Jupyter](https://jupyter.org/) notebook can be found that explains how all pieces of the data structure fit together using the SQLAlchemy Implementation. See its [README](examples/simple_scenario_and_depot_creation_de/README.md) for details.

## License

This project is licensed under the AGPLv3 license - see the [LICENSE](LICENSE.md) file for details.

## Funding Notice

This code was developed as part of the project [eBus2030+](https://www.eflip.de/) funded by the Federal German Ministry for Digital and Transport (BMDV) under grant number 03EMF0402.


