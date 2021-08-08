"""Notes:
* 'test' command: nox will use poetry.lock to determine dependency versions
* 'lint' command: tools and environments are managed by pre-commit
* All other commands: the current environment will be used instead of creating new ones
"""
from os.path import join
from shutil import rmtree

import nox
from nox_poetry import session

nox.options.reuse_existing_virtualenvs = True
nox.options.sessions = ['lint', 'cov']

LIVE_DOCS_PORT = 8181
LIVE_DOCS_IGNORE = ['*.pyc', '*.tmp', '**/modules/*']
LIVE_DOCS_WATCH = ['requests_cache', 'examples']
CLEAN_DIRS = ['dist', 'build', join('docs', '_build'), join('docs', 'modules')]

UNIT_TESTS = join('tests', 'unit')
INT_TESTS = join('tests', 'integration')


@session(python=['3.6', '3.7', '3.8', '3.9', '3.10'])
def test(session):
    """Run tests for a specific python version"""
    test_paths = session.posargs or [UNIT_TESTS]
    session.install('.', 'pytest', 'pytest-order', 'pytest-xdist', 'requests-mock', 'timeout-decorator')
    session.run('pytest', '-vv', '-n', 'auto', *test_paths)


@session(python=False)
def clean(session):
    """Clean up temporary build + documentation files"""
    for dir in CLEAN_DIRS:
        print(f'Removing {dir}')
        rmtree(dir, ignore_errors=True)


@session(python=False)
@session(python=False, name='cov')
def coverage(session):
    """Run tests and generate coverage report"""
    coverage_args = '--cov --cov-report=term --cov-report=html'
    cmd_1 = f'pytest {UNIT_TESTS} --numprocesses=auto {coverage_args}'
    cmd_2 = f'pytest {INT_TESTS} --cov-append {coverage_args}'
    session.run(*cmd_1.split(' '))
    session.run(*cmd_2.split(' '))


@session(python=False)
def docs(session):
    """Build Sphinx documentation"""
    cmd = 'sphinx-build docs docs/_build/html -j auto'
    session.run(*cmd.split(' '))


@session(python=False)
def livedocs(session):
    """Auto-build docs with live reload in browser.
    Add `-- open` to also open the browser after starting.
    """
    args = ['-a']
    args += [f'--watch {pattern}' for pattern in LIVE_DOCS_WATCH]
    args += [f'--ignore {pattern}' for pattern in LIVE_DOCS_IGNORE]
    args += [f'--port {LIVE_DOCS_PORT}', '-j auto']
    if session.posargs == ['open']:
        args.append('--open-browser')

    clean(session)
    cmd = 'sphinx-autobuild docs docs/_build/html ' + ' '.join(args)
    session.run(*cmd.split(' '))


@session(python=False)
def lint(session):
    """Run linters and code formatters via pre-commit"""
    cmd = 'pre-commit run --all-files'
    session.run(*cmd.split(' '))
