# Contributing Guide

## Development status
While the original author no longer has time to work on requests-cache
([see note here](https://github.com/reclosedev/requests-cache/blob/master/CODESHELTER.md)),
one or more maintainers are available via [Code Shelter](https://www.codeshelter.co) to help keep
this project going.

Maintenance will mainly focus on bugfixes, security and compatibility updates, etc.
If there is a new feature you would like to see, the best way to make that happen is to submit a PR
for it!

## Bug Reports & Feedback
If you discover a bug, want to propose a new feature, or have other feedback about requests-cache, please
[create an issue](https://github.com/reclosedev/requests-cache/issues/new/choose)!

## Project Discussion
If you want to discuss ideas about the project in general, or if you have an issue or PR that hasn't
received a response in a timely manner, please reach out on the Code Shelter chat server, under
[projects/requests-cache](https://codeshelter.zulipchat.com/#narrow/stream/186993-projects/topic/requests-cache).

## Dev Installation
To set up for local development:

```bash
$ git clone https://github.com/reclosedev/requests-cache.git
$ cd requests-cache
$ pip install -Ue ".[dev]"
```

## Pre-commit Hooks
[Pre-commit](https://github.com/pre-commit/pre-commit) config is included to run the same checks
locally that are run in CI jobs by GitHub Actions. This is optional but recommended.
```bash
$ pre-commit install --config .github/pre-commit.yml
```

To uninstall:
```bash
$ pre-commit uninstall
```

## Testing

### Test Layout
* Tests are divided into unit and integration tests:
    * Unit tests can be run without any additional setup, and don't depend on any external services
    * Integration tests depend on additional services, which are easiest to run using Docker
      (see Integration Tests section below).
* See [conftest.py](https://github.com/reclosedev/requests-cache/blob/master/tests/conftest.py) for
  [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html) that apply the most common
  mocking steps and other test setup.
  
### Running Tests
* Run `pytest` to run all tests
* Run `pytest tests/unit` to run only unit tests
* Run `pytest tests/integration` to run only integration tests
* Run `./runtests.sh` to run all tests with some useful options for test coverage reports,
  multiprocessing, and debugging.

### Integration Tests
Live databases are required to run integration tests, and docker-compose config is included to make
this easier. First, [install docker](https://docs.docker.com/get-docker/) and
[install docker-compose](https://docs.docker.com/compose/install/).

Then, run:
```bash
$ docker-compose up -d
pytest tests/integration
```

## Debugging
When you run into issues while working on new features and/or tests, it will make your life much easier
to use a debugger instead of `print` statements. Most IDEs have a built-in debugger, but if
you prefer the command line, [ipdb](https://github.com/gotcha/ipdb) is a good option. To install:
```bash
pip install ipython ipdb
```

The `runtests.sh` script will use ipdb by default, if it's installed.

## Documentation
[Sphinx](http://www.sphinx-doc.org/en/master/) is used to generate documentation.

To build the docs locally:
```bash
$ make -C docs all
```

To preview:
```bash
# MacOS:
$ open docs/_build/index.html
# Linux:
$ xdg-open docs/_build/index.html
```

### Readthedocs
Sometimes, there are differences in the Readthedocs build environment that can cause builds to
succeed locally but fail remotely. To help debug this, you can use the Readthedocs Docker container
(`readthedocs/build`) to perform the build. Example:
```bash
docker pull readthedocs/build
docker run --rm -ti \
  -v (pwd):/home/docs/project \
  readthedocs/build \
  /bin/bash -c \
  "cd /home/docs/project \
    && pip3 install '.[docs,backends]' \
    && make -C docs html"
```

## Pull Requests
Here are some general guidelines for submitting a pull request:

- If the changes are trivial, just briefly explain the changes in the PR description.
- Otherwise, please submit an issue describing the proposed change prior to submitting a PR.
- Please add unit test coverage and updated docs (if applicable) for your changes.
- Submit the PR to be merged into the `master` branch.

## Releases
Notes for maintainers:
- Releases are built and published to pypi based on **git tags.**
- [Milestones](https://github.com/reclosedev/requests-cache/milestones) will be used to track
progress on major and minor releases. 
- GitHub Actions will build and deploy packages to PyPi on tagged commits
on the `master` branch.
  
Release steps:
- Update the version in `requests_cache/__init__.py`
- Update the release notes in `HISTORY.md`
- Merge changes into the `master` branch
- Push a new tag, e.g.: `git tag v0.1 && git push origin --tags`
- This will trigger a deployment. Verify that this completes successfully and that the new version
  can be installed from pypi with `pip install`
