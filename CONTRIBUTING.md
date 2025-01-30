# Contributing Guide

## Bug Reports, Feedback, and Discussion
If you discover a bug or want to request a new feature, please
[create an issue](https://github.com/requests-cache/requests-cache/issues/new/choose).

If you want to discuss ideas about the project in general, or have a more open-ended question or feedback,
please use [Discussions](https://github.com/orgs/requests-cache/discussions).

## Development Status
Requests-cache is in a relatively mature state, but is still under active maintenance. Contributions are very welcome, and will be attributed on the
[Contributors](https://requests-cache.readthedocs.io/en/main/project_info/contributors.html)
page.

## How to Help
If you are interested in helping out, here are a few ways to get started:

* Give feedback on open issues
* Make or suggest improvements for the documentation; see [#355](https://github.com/requests-cache/requests-cache/issues/355) for details.
* See the [help-wanted](https://github.com/requests-cache/requests-cache/labels/help-wanted) issue label
* See the [shelved](https://github.com/requests-cache/requests-cache/issues?q=label%3Ashelved) issue
  label for features that have been previously proposed and are not currently planned, but not
  completely ruled out either
* If you find an issue you want to work on, please comment on it so others know it's in progress

## Dev Installation

To setup `requests-cache` for development, first install these tools:

* [git](https://git-scm.com/) (required)
* [Python 3](https://www.python.org/) (required)
* [poetry](https://python-poetry.org/docs/#installation) (required)
* [virtualenv](https://virtualenv.pypa.io/en/latest/installation.html) (recommended, see below)
* [docker] and [docker compose][docker-compose] (partially required and recommended, see below)
* [pre-commit] (optional)

Next, clone the repository:

```sh
git clone https://github.com/requests-cache/requests-cache.git
cd requests-cache
```

You have these options to setup the development environment:

1. Use a virtual environment (recommended):

   ```sh
   virtualenv -p python3 .venv
   source .venv/bin/activate
   poetry install -v -E all
   ```

2. Only use `poetry`. If you choose this option, all of the following commands need to be prefixed by `poetry run`. For example:

   ```sh
   poetry run pytest  # instead of just pytest
   ```

### Linting & Formatting

Code linting and formatting tools used include:

* [ruff (linter)](https://docs.astral.sh/ruff/linter)
* [ruff (formatter)](https://docs.astral.sh/ruff/formatter)
* [mypy](https://mypy.readthedocs.io/en/stable/getting_started.html)

All of these will be run by [GitHub Actions] on pull requests. You can also run them locally with:

```sh
nox -e lint
```

[GitHub Actions]: https://github.com/requests-cache/requests-cache/actions

#### Pre-Commit Hooks

Optionally, you can use [pre-commit] to automatically
run all of code checks before a commit is made.

[pre-commit]: https://github.com/pre-commit/pre-commit

* **Automatically** run all code checks before commit:

    ```sh
    pre-commit install
    ```

* Disable checks before commit:

    ```sh
    pre-commit uninstall
    ```

* **Manually** run all code checks before committing:

    ```sh
    nox -e lint
    ```

Running a `pre-commit` hook can save you some time in that it will show you errors immediately rather than waiting for CI
jobs to complete, or if you forget to manually run the checks before committing.

## Testing

### Test Layout

Tests are divided into unit and integration tests:

* **Unit tests** can be run without any additional setup, and **don't depend on any external services**.
* **Integration tests** **depend on additional services**, which are easiest to run using Docker
    (see Integration Tests section below).

Have a look at [conftest.py](https://github.com/requests-cache/requests-cache/blob/main/tests/conftest.py) for
[pytest fixtures](https://docs.pytest.org/en/stable/fixture.html) that apply the most common
mocking steps and other test setup.

Overview:

* Run `pytest` to run all tests
* Run `pytest tests/unit` to run only unit tests
* Run `pytest tests/integration` to run only integration tests

### Running Unit Tests

We use `pytest` to run the tests. It should be installed if you followed the installation instructions above.

The **Unit tests** do not depend on external services. They should all run:

```sh
pytest tests/unit
```

Output:

```text
===== 392 passed in 8.12s =====
```

### Integration Tests with Docker

A live web server and backend databases are required to run integration tests, and a docker-compose
config is included to make this easier. First, [install docker][docker]
and [docker compose][docker-compose].

[docker]: https://docs.docker.com/get-docker/
[docker-compose]: https://docs.docker.com/compose/install/

Start the docker containers:

```sh
docker compose up -d
```

Output:

```text
[+] Running 5/0
 ✔ Container httpbin                         0.0s
 ✔ Container mongo-test                      0.0s
 ✔ Container valkey-test                     0.0s
 ✔ Container dynamodb-test                   0.0s
 ✔ Container redis-test                      0.0s
```

After this, you can run all the tests:

```sh
pytest
```

or just the integration tests:

```sh
pytest tests/integration
```

Output:

```text
===== 1194 passed in 110.27s (0:01:50) =====
```

After, you are done testing, shutdown the docker containers:

```sh
docker compose down
```

### Integration Tests with HTTP-Bin

If you can't easily run Docker containers in your environment but still want to run **some of the
integration tests**, you can use [pytest-httpbin](https://github.com/kevin1024/pytest-httpbin) instead
of the httpbin container. This just requires installing an extra package and setting an environment
variable:

```sh
pip install pytest-httpbin
export USE_PYTEST_HTTPBIN=true
pytest tests/integration/test_memory.py
pytest tests/integration/test_filesystem.py
pytest tests/integration/test_sqlite.py
pytest tests/integration/test_upgrade.py
```

For backend databases, you can install and run them on the host instead of in a container, as long
as they are running on the default port.

### Testing all Python Versions

For CI jobs (including PRs), all tests will be run for each supported Python version.
We use [nox](https://nox.thea.codes) to do this locally, if needed:

```sh
nox -e test
```

Or to run tests for a specific python version:

```sh
nox -e test-3.10
```

To generate a coverage report:

```sh
nox -e cov
```

See `nox --list` for a full list of available commands.

## Documentation

[Sphinx](https://www.sphinx-doc.org/en/master/) is used to generate documentation.

First, install documentation dependencies:

```sh
poetry install -E all --with docs
```

To build the docs locally:

```sh
nox -e docs
```

To preview:

```sh
# MacOS:
open docs/_build/html/index.html
# Linux:
xdg-open docs/_build/html/index.html
```

You can also use [sphinx-autobuild](https://github.com/executablebooks/sphinx-autobuild) to rebuild the docs and live reload in the browser whenever doc contents change:
```sh
nox -e livedocs
```

### Readthedocs
Sometimes, there are differences in the Readthedocs build environment that can cause builds to
succeed locally but fail remotely. To help debug this, you can use the
[readthedocs/build](https://github.com/readthedocs/readthedocs-docker-images) container to build
the docs. A configured build container is included in `docs/docker-compose.yml` to simplify this.

Run with:
```sh
# Optionally add --build to rebuild with updated dependencies
docker-compose -f docs/docker-compose.yml up -d
docker exec readthedocs make all
```

## Pull Requests
Here are some general guidelines for submitting a pull request:

* If the changes are trivial, just briefly explain the changes in the PR description
* Otherwise, please submit an issue describing the proposed change prior to submitting a PR
* Add unit test coverage for your changes
* If your changes add or modify user-facing behavior, add documentation describing those changes
* Submit the PR to be merged into the `main` branch

## Notes for Maintainers

### Releases
* Releases are built and published to PyPI based on **git tags.**
* [Milestones](https://github.com/requests-cache/requests-cache/milestones) will be used to track
progress on major and minor releases.
* GitHub Actions will build and deploy packages to PyPI on tagged commits
on the `main` branch.

Release steps:
* Update the version in both `pyproject.toml` and `requests_cache/__init__.py`
* Update the release notes in `HISTORY.md`
* Generate a sample cache for the new version (used by unit tests) with `python tests/generate_test_db.py`
* Merge changes into the `main` branch
* Push a new tag, e.g.: `git tag v0.1 && git push origin --tags`
* This will trigger a deployment. Verify that this completes successfully and that the new version
  can be installed from pypi with `pip install`
* A [readthedocs build](https://readthedocs.org/projects/requests-cache/builds/) will be triggered by the new tag. Verify that this completes successfully.

Downstream builds:
* We also maintain a [Conda package](https://anaconda.org/conda-forge/requests-cache), which is automatically built and published by conda-forge whenever a new release is published to PyPI. The [feedstock repo](https://github.com/conda-forge/requests-cache-feedstock) only needs to be updated manually if there are changes to dependencies.
* For reference: [repology](https://repology.org/project/python:requests-cache) lists additional downstream packages maintained by other developers.

### Pre-Releases
Pre-release builds are convenient for letting testers try out in-development changes. Versions with
the suffix `.dev` (among others) can be deployed to PyPI and installed by users with `pip install --pre`,
and are otherwise ignored by `pip install`:
```sh
# Install latest pre-release build:
pip install -U --pre requests-cache

# Install latest stable build
pip install -U requests-cache
```

Notes:
* See python packaging docs on
[pre-release versioning](https://packaging.python.org/en/latest/guides/distributing-packages-using-setuptools/#pre-release-versioning) for more info on how this works
* requests-cache pre-release docs can be found here: https://requests-cache.readthedocs.io/en/main/
* Any collaborator can trigger a pre-release build for requests-cache by going to
  **Actions > Deploy > Run workflow**
* A complete list of builds can by found on [PyPI under 'Release History'](https://pypi.org/project/requests-cache/#history)
