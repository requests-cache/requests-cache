# Contributing Guide

## Development status
While the original author no longer has time to work on requests-cache
([see note here](https://github.com/reclosedev/requests-cache/blob/master/CODESHELTER.md)),
one or more maintainers are available via [Code Shelter](https://www.codeshelter.co) to help keep
this project going.

Maintenance will mainly focus on bugfixes, security and compatibility updates, etc.
If there is a new feature you would like to see, the best way to make that happen is to submit a PR
for it!

## Project Discussion
If you have an issue or PR that hasn't received a response in a timely manner, or if you want to
discuss ideas about the project in general, please reach out on the Code Shelter chat server, under
[projects/requests-cache](https://codeshelter.zulipchat.com/#narrow/stream/186993-projects/topic/requests-cache).

## Installation
To set up for local development:

```bash
$ git clone https://github.com/reclosedev/requests-cache.git
$ cd requests-cache
$ pip install -Ue ".[dev]"
```

## Pre-commit hooks
[Pre-commit](https://github.com/pre-commit/pre-commit) config is included to run the same checks
locally that are run in CI jobs by GitHub Actions. This is optional but recommended.
```bash
$ pre-commit install --config .github/pre-commit.yml
```

To uninstall:
```bash
$ pre-commit uninstall
```

## Integration Tests
Local databases are required to run integration tests, and docker-compose config is included to make
this easier. First, [install docker](https://docs.docker.com/get-docker/) and
[install docker-compose](https://docs.docker.com/compose/install/).

Then, run:
```bash
$ docker-compose up -d
pytest test/integration
```

## Documentation
[Sphinx](http://www.sphinx-doc.org/en/master/) is used to generate documentation.

To build the docs locally:
```bash
$ make -C docs html
```

To preview:
```bash
# MacOS:
$ open docs/_build/index.html
# Linux:
$ xdg-open docs/_build/index.html
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
- Update the version in `pyinaturalist/__init__.py`
- Update the release notes in `HISTORY.md`
- Merge changes into the `master` branch
- Push a new tag, e.g.: `git tag v0.1 && git push origin --tags`
- This will trigger a deployment. Verify that this completes successfully and that the new version
  can be installed from pypi with `pip install`
