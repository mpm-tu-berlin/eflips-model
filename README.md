# eflips-db

This repository contains both the *reference specification* and an *SQLALchemy implementation* of the eFLIPS database.



## Reference Specification

The reference specification is located (for now) in the huge SVG file [`schema.svg`](schema.svg). It is a UML diagram of the database schema. The diagram was created using [OmniGraffle](https://www.omnigroup.com/omnigraffle) (proprietary).

## SQLAlchemy Implementation

The SQLAlchemy implementation is located in the `eflips/db` directory. It is a Python package that contains the SQLAlchemy models and the database migration scripts. The package is structured as follows:

### Installation

Releases of the package will be made available on [https://pypi.org/](https://pypi.org/project/eflips-db/). As such, it is installable with `pip install eflips-db`. However, it should be used by including it in other packages as a dependency. The versioning scheme is [semantic versioning](https://semver.org/). This means that:

- patch releases (e.g. `1.0.0` to `1.0.1`) are backwards compatible bug fixes, without schama changes
- minor releases (e.g. `1.0.0` to `1.1.0`) are backwards compatible feature additions, with the schema changes being optional
- major releases (e.g. `1.0.0` to `2.0.0`) are backwards incompatible changes, with the schema changes being mandatory

Supported databadse backends are [PostgreSQL](https://www.postgresql.org) with the [PostGIS](https://postgis.net/) extension and [SQLite](https://www.sqlite.org/index.html) with the [SpatiaLite](https://www.gaia-gis.it/fossil/libspatialite/index) extension.

### Usage

This package is not expected to be used directly. It is a dependency of the `eflips-*` packages.

### Development

We utilize the [GitHub Flow](https://docs.github.com/get-started/quickstart/github-flow) branching structure. This means  that the `main` branch is always deployable and that all development happens in feature branches. The feature branches are merged into `main` via pull requests. We utilize the [semantic versioning](https://semver.org/) scheme for versioning.

Dependencies are managed using [poetry](https://python-poetry.org/). To install the dependencies, execute the following command in the root directory of the repository:

```bash
poetry install
```

We use black for code formatting. You can use `black .` to format the code.

Please make sure that your `poetry.lock` and `pyproject.toml` files are consistent before committing. You can use `poetry check` to check this. This is also checked by pre-commit.

You can use [pre-commit](https://pre-commit.com/) to ensure the code is formatted correctly before committing.

We recommend utilizing [PyLint](https://pylint.readthedocs.io/en/latest/index.html) for static code analysis. You can use `pylint eflips` to run PyLint on the code.

#### Testing

We use [pytest](https://docs.pytest.org/en/stable/) for testing. The tests are located in the `tests` directory. To run the tests, execute the following command in the root directory of the repository (after installing the `dev` dependencies):

```bash
pytest
```

## License

This project is licensed under the AGPLv3 license - see the [LICENSE](LICENSE.md) file for details.


