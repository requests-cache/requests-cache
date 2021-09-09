# Contributing Guide

## Bug Reports & Feedback
If you discover a bug, want to propose a new feature, or have other feedback about requests-cache, please
[create an issue](https://github.com/reclosedev/requests-cache/issues/new/choose)!

## Project Discussion
If you want to discuss ideas about the project in general, or if you have an issue or PR that hasn't
received a response in a timely manner, please reach out on the Code Shelter chat server, under
[projects/requests-cache](https://codeshelter.zulipchat.com/#narrow/stream/186993-projects/topic/requests-cache).

## Development Status
Requests-cache is under active development!  Contributions are very welcome, and will be attributed on the
[Contributors](https://requests-cache.readthedocs.io/en/latest/project_info/contributors.html)
page.

## How to Help
If you are interested in helping out, here are a few ways to get started:

* Give feedback on open issues
* Make or suggest improvements for the documentation; see [#355](https://github.com/reclosedev/requests-cache/issues/355) for details.
* See the [help-wanted](https://github.com/reclosedev/requests-cache/labels/help-wanted) issue label
* See the [shelved](https://github.com/reclosedev/requests-cache/issues?q=label%3Ashelved) issue
  label for features that have been previously proposed and are not currently planned, but not
  completely ruled out either
* If you find an issue you want to work on, please comment on it so others know it's in progress

## Pre-release Installation
If you want to test out the latest in-development changes, you can install pre-release versions:
```bash
pip install --pre requests-cache
```
Pre-release documentation can be found here: https://requests-cache.readthedocs.io/en/latest/

## Dev Installation
To set up for local development (requires [poetry](https://python-poetry.org/docs/#installation)):

```bash
git clone https://github.com/reclosedev/requests-cache.git
cd requests-cache
poetry install -v -E all
```

## Pre-commit Hooks
CI jobs will run code style checks, type checks, linting, etc. If you would like to run these same
checks locally, you can use [pre-commit](https://github.com/pre-commit/pre-commit).
This is optional but recommended.

To install pre-commit hooks:
```bash
pre-commit install
```

To manually run checks on all files:
```bash
pre-commit run --all-files
# Alternative alias with nox:
nox -e lint
```

To disable pre-commit hooks:
```bash
pre-commit uninstall
```

## Testing

### Test Layout
* Tests are divided into unit and integration tests:
    * Unit tests can be run without any additional setup, and **don't depend on any external services**.
    * Integration tests **depend on additional services**, which are easiest to run using Docker
      (see Integration Tests section below).
* See [conftest.py](https://github.com/reclosedev/requests-cache/blob/master/tests/conftest.py) for
  [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html) that apply the most common
  mocking steps and other test setup.

### Running Tests
* Run `pytest` to run all tests
* Run `pytest tests/unit` to run only unit tests
* Run `pytest tests/integration` to run only integration tests

For CI jobs (including PRs), these tests will be run for each supported python version.
You can use [nox](https://nox.thea.codes) to do this locally, if needed:
```bash
nox -e test
```

Or to run tests for a specific python version:
```bash
nox -e test-3.10
```

To generate a coverage report:
```bash
nox -e cov
```

See `nox --list` for a ful list of available commands.

### Integration Test Containers
A live web server and backend databases are required to run integration tests, and docker-compose
config is included to make this easier. First, [install docker](https://docs.docker.com/get-docker/)
and [install docker-compose](https://docs.docker.com/compose/install/).

Then, run:
```bash
docker-compose up -d
pytest tests/integration
```

### Integration Test Alternatives
If you can't easily run Docker containers in your environment but still want to run some of the
integration tests, you can use [pytest-httpbin](https://github.com/kevin1024/pytest-httpbin) instead
of the httpbin container. This just requires installing an extra package and setting an environment
variable:
```bash
pip install pytest-httpbin
export USE_PYTEST_HTTPBIN=true
pytest tests/integration/test_cache.py
```

For backend databases, you can install and run them on the host instead of in a container, as long
as they are running on the default port.

## Documentation
[Sphinx](http://www.sphinx-doc.org/en/master/) is used to generate documentation.

To build the docs locally:
```bash
nox -e docs
```

To preview:
```bash
# MacOS:
open docs/_build/html/index.html
# Linux:
xdg-open docs/_build/html/index.html
```

You can also use [sphinx-autobuild](https://github.com/executablebooks/sphinx-autobuild) to rebuild the docs and live reload in the browser whenver doc contents change:
```bash
nox -e livedocs
```

### Readthedocs
Sometimes, there are differences in the Readthedocs build environment that can cause builds to
succeed locally but fail remotely. To help debug this, you can use the
[readthedocs/build](https://github.com/readthedocs/readthedocs-docker-images) container to build
the docs. A configured build container is included in `docs/docker-compose.yml` to simplify this.

Run with:
```bash
# Optionally add --build to rebuild with updated dependencies
docker-compose -f docs/docker-compose.yml up -d
docker exec readthedocs make all
```

## Pull Requests
Here are some general guidelines for submitting a pull request:

- If the changes are trivial, just briefly explain the changes in the PR description
- Otherwise, please submit an issue describing the proposed change prior to submitting a PR
- Add unit test coverage for your changes
- If your changes add or modify user-facing behavior, add documentation describing those changes
- Submit the PR to be merged into the `master` branch

## Notes for Maintainers

### Releases
- Releases are built and published to PyPI based on **git tags.**
- [Milestones](https://github.com/reclosedev/requests-cache/milestones) will be used to track
progress on major and minor releases.
- GitHub Actions will build and deploy packages to PyPI on tagged commits
on the `master` branch.

Release steps:
- Update the version in `requests_cache/__init__.py`
- Update the release notes in `HISTORY.md`
- Generate a sample cache for the new version (used by unit tests) with `python tests/generate_test_db.py`
- Merge changes into the `master` branch
- Push a new tag, e.g.: `git tag v0.1 && git push origin --tags`
- This will trigger a deployment. Verify that this completes successfully and that the new version
  can be installed from pypi with `pip install`

### Pre-Releases
Pre-release builds are convenient for letting testers try out in-development changes. Versions with
the suffix `.dev` (among others) can be deployed to PyPI and installed by users with `pip install --pre`,
and are otherwise ignored by `pip install`:
```
# Install latest pre-release build:
pip install -U --pre requests-cache

# Install latest stable build
pip install -U requests-cache
```

Notes:
* See python packaging docs on
[pre-release versioning](https://packaging.python.org/guides/distributing-packages-using-setuptools/#pre-release-versioning) for more info on how this works
* Any collaborator can trigger a pre-release build for requests-cache by going to
  **Actions > Deploy > Run workflow**
* A complete list of builds can by found on [PyPI under 'Release History'](https://pypi.org/project/requests-cache/#history)
