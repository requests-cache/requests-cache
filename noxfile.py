"""An optional wrapper for common commands used in local development and CI.

TODO: This will likely be replaced by uv tasks, when released:
https://github.com/astral-sh/uv/issues/5903

Notes:
* 'test' and 'test-<python version>' commands: nox will create separate virtualenvs per python
  version
* 'lint' command: tools and environments are managed by pre-commit
* All other commands: the current environment will be used instead of creating new ones
    * If using uv to manage virtualenvs, manually activate it first with `source .venv/bin/activate`
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

nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ['lint', 'cov']

LIVE_DOCS_PORT = 8181
LIVE_DOCS_IGNORE = ['*.pyc', '*.tmp', join('**', 'modules', '*')]
LIVE_DOCS_WATCH = ['requests_cache', 'examples']

DOCS_DIR = Path('docs')
DOC_BUILD_DIR = DOCS_DIR / '_build' / 'html'
TEST_DIR = Path('tests')
CLEAN_DIRS = ['dist', 'build', DOCS_DIR / '_build', DOCS_DIR / 'modules']

PYTHON_VERSIONS = ['3.13', '3.12', '3.11', '3.10', '3.9', '3.8', 'pypy3.9', 'pypy3.10']
UNIT_TESTS = TEST_DIR / 'unit'
INTEGRATION_TESTS = TEST_DIR / 'integration'
COMPAT_TESTS = TEST_DIR / 'compat'
ALL_TESTS = [UNIT_TESTS, INTEGRATION_TESTS, COMPAT_TESTS]
STRESS_TEST_MULTIPLIER = 10
DEFAULT_COVERAGE_FORMATS = ['html', 'term']
# Run tests in parallel, grouped by test module
XDIST_ARGS = ['--numprocesses=auto', '--dist=loadfile']

IS_PYPY = platform.python_implementation() == 'PyPy'


def install_deps(session):
    """Install project and test dependencies into a test-specific virtualenv using uv"""
    session.env['UV_PROJECT_ENVIRONMENT'] = session.virtualenv.location
    session.run_install(
        'uv',
        'sync',
        '--frozen',
        '--all-extras',
    )


@nox.session(python=PYTHON_VERSIONS, venv_backend='uv')
def test(session):
    """Run tests in a separate virtualenv per python version"""
    test_paths = session.posargs or ALL_TESTS
    install_deps(session)
    session.run('pytest', '-rsxX', *XDIST_ARGS, *test_paths)


@nox.session(python=False, name='test-current')
def test_current(session):
    """Run tests using the current virtualenv"""
    test_paths = session.posargs or ALL_TESTS
    session.run('python', '-m', 'pytest', '-rsxX', *XDIST_ARGS, *test_paths)


@nox.session(python=False)
def clean(session):
    """Clean up temporary build + documentation files"""
    for dir in CLEAN_DIRS:
        print(f'Removing {dir}')
        rmtree(dir, ignore_errors=True)


@nox.session(python=False, name='cov')
def coverage(session):
    """Run tests and generate coverage report"""
    cmd = ['pytest', *ALL_TESTS, '-rsxX']

    # Exclude concurrency tests to run separately without xdist
    cmd += ['-k', 'not concurrency']
    if not IS_PYPY:
        cmd += XDIST_ARGS

    # Add coverage formats
    cmd += ['--cov']
    cov_formats = session.posargs or DEFAULT_COVERAGE_FORMATS
    cmd += [f'--cov-report={f}' for f in cov_formats]

    # Add verbose flag, if set by environment
    if getenv('PYTEST_VERBOSE'):
        cmd += ['--verbose']
    session.run(*cmd)


@nox.session(python=False, name='stress')
def stress_test(session):
    """Run concurrency tests with a higher stress test multiplier"""
    multiplier = session.posargs[0] if session.posargs else STRESS_TEST_MULTIPLIER
    cmd = ['pytest', INTEGRATION_TESTS, '-rs', '-k', 'concurrency']
    session.run(
        *cmd,
        env={'STRESS_TEST_MULTIPLIER': str(multiplier)},
    )


@nox.session(python=False)
def docs(session):
    """Build Sphinx documentation"""
    session.run('sphinx-build', 'docs', DOC_BUILD_DIR, '-j', 'auto')


@nox.session(python=False)
def linkcheck(session):
    """Check documentation for dead links"""
    session.run('sphinx-build', 'docs', DOC_BUILD_DIR, '-b', 'linkcheck')


@nox.session(python=False)
def livedocs(session):
    """Auto-build docs with live reload in browser.
    Add `--open` to also open the browser after starting.
    """
    cmd = ['sphinx-autobuild', 'docs', 'docs/_build/html']
    cmd += ['-a']
    cmd += ['--host', '0.0.0.0']
    cmd += ['--port', str(LIVE_DOCS_PORT), '-j', 'auto']
    for pattern in LIVE_DOCS_WATCH:
        cmd += ['--watch', pattern]
    for pattern in LIVE_DOCS_IGNORE:
        cmd += ['--ignore', pattern]
    if session.posargs == ['open']:
        cmd.append('--open-browser')

    clean(session)
    session.run(*cmd)


@nox.session(python=False)
def lint(session):
    """Run linters and code formatters via pre-commit"""
    session.run('pre-commit', 'run', '--all-files')
