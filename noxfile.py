"""Runner script for tools used in local development and CI.

Notes:
* 'test' and 'test-<python version>' commands: nox will create separate virtualenvs per python
  version, and use `poetry.lock` to determine dependency versions
* 'lint' command: tools and environments are managed by pre-commit
* All other commands: the current environment will be used instead of creating new ones
* Run `nox -l` to see all available commands
* See Contributing Guide for more usage details:
  https://github.com/requests-cache/requests-cache/blob/main/CONTRIBUTING.md
"""

import platform
from os import getenv
from os.path import join
from pathlib import Path
from shutil import rmtree

import nox
from nox_poetry import session

nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ['lint', 'cov']

LIVE_DOCS_PORT = 8181
LIVE_DOCS_IGNORE = ['*.pyc', '*.tmp', join('**', 'modules', '*')]
LIVE_DOCS_WATCH = ['requests_cache', 'examples']

DOCS_DIR = Path('docs')
DOC_BUILD_DIR = DOCS_DIR / '_build' / 'html'
TEST_DIR = Path('tests')
CLEAN_DIRS = ['dist', 'build', DOCS_DIR / '_build', DOCS_DIR / 'modules']

PYTHON_VERSIONS = ['3.8', '3.9', '3.10', '3.11', '3.12', 'pypy3.9', 'pypy3.10']
UNIT_TESTS = TEST_DIR / 'unit'
INTEGRATION_TESTS = TEST_DIR / 'integration'
COMPAT_TESTS = TEST_DIR / 'compat'
ALL_TESTS = [UNIT_TESTS, INTEGRATION_TESTS, COMPAT_TESTS]
STRESS_TEST_MULTIPLIER = 10
DEFAULT_COVERAGE_FORMATS = ['html', 'term']
# Run tests in parallel, grouped by test module
XDIST_ARGS = ['--numprocesses=auto', '--dist=loadfile']

IS_PYPY = platform.python_implementation() == 'PyPy'


@session(python=PYTHON_VERSIONS)
def test(session):
    """Run tests in a separate virtualenv per python version"""
    test_paths = session.posargs or ALL_TESTS
    session.install('.', 'pytest', 'pytest-xdist', 'requests-mock', 'rich', 'timeout-decorator')
    session.run('pytest', '-rsxX', *XDIST_ARGS, *test_paths)


@session(python=False, name='test-current')
def test_current(session):
    """Run tests using the current virtualenv"""
    test_paths = session.posargs or ALL_TESTS
    session.run('pytest', '-rsxX', *XDIST_ARGS, *test_paths)


@session(python=False)
def clean(session):
    """Clean up temporary build + documentation files"""
    for dir in CLEAN_DIRS:
        print(f'Removing {dir}')
        rmtree(dir, ignore_errors=True)


@session(python=False, name='cov')
def coverage(session):
    """Run tests and generate coverage report"""
    cmd = ['pytest', *ALL_TESTS, '-rsxX', '--cov']
    if not IS_PYPY:
        cmd += XDIST_ARGS

    # Add coverage formats
    cov_formats = session.posargs or DEFAULT_COVERAGE_FORMATS
    cmd += [f'--cov-report={f}' for f in cov_formats]

    # Add verbose flag, if set by environment
    if getenv('PYTEST_VERBOSE'):
        cmd += ['--verbose']
    session.run(*cmd)


@session(python=False, name='stress')
def stress_test(session):
    """Run concurrency tests with a higher stress test multiplier"""
    multiplier = session.posargs[0] if session.posargs else STRESS_TEST_MULTIPLIER
    cmd = ['pytest', *INTEGRATION_TESTS, '-rs', '-k', 'concurrency']
    session.run(
        *cmd,
        env={'STRESS_TEST_MULTIPLIER': str(multiplier)},
    )


@session(python=False)
def docs(session):
    """Build Sphinx documentation"""
    session.run('sphinx-build', 'docs', DOC_BUILD_DIR, '-j', 'auto')


@session(python=False)
def linkcheck(session):
    """Check documentation for dead links"""
    session.run('sphinx-build', 'docs', DOC_BUILD_DIR, '-b', 'linkcheck')


@session(python=False)
def livedocs(session):
    """Auto-build docs with live reload in browser.
    Add `--open` to also open the browser after starting.
    """
    cmd = ['sphinx-autobuild', 'docs', 'docs/_build/html']
    cmd += ['-a']
    cmd += ['--port', str(LIVE_DOCS_PORT), '-j', 'auto']
    for pattern in LIVE_DOCS_WATCH:
        cmd += ['--watch', pattern]
    for pattern in LIVE_DOCS_IGNORE:
        cmd += ['--ignore', pattern]
    if session.posargs == ['open']:
        cmd.append('--open-browser')

    clean(session)
    session.run(*cmd)


@session(python=False)
def lint(session):
    """Run linters and code formatters via pre-commit"""
    session.run('pre-commit', 'run', '--all-files')
