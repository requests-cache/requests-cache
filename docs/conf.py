# requests-cache documentation build configuration file
import logging
import os
import sys
from os.path import abspath, dirname, join

# Add project path
sys.path.insert(0, os.path.abspath('..'))
from requests_cache import __version__  # noqa: E402

PROJECT_DIR = abspath(dirname(dirname(__file__)))
PACKAGE_DIR = join(PROJECT_DIR, 'requests_cache')
TEMPLATE_DIR = join(PROJECT_DIR, 'docs', '_templates')


# General information about the project.
project = 'requests-cache'
needs_sphinx = '3.0'
master_doc = 'index'
source_suffix = ['.rst', '.md']
version = release = __version__
html_static_path = ['_static']
exclude_patterns = ['_build']
templates_path = ['_templates']

# Sphinx extensions
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.autosummary',
    'sphinx.ext.extlinks',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'sphinx_automodapi.automodapi',
    'sphinx_automodapi.smart_resolver',
    'sphinx_copybutton',
    'sphinx_inline_tabs',
    'sphinx_panels',
    'sphinxcontrib.apidoc',
    'myst_parser',
    'notfound.extension',
]

# MyST extensions
myst_enable_extensions = [
    'colon_fence',
    'html_image',
    'linkify',
    'replacements',
    'smartquotes',
]

# Exclude auto-generated page for top-level __init__.py
exclude_patterns = ['_build', 'modules/requests_cache.rst']

# Enable automatic links to other projects' Sphinx docs
intersphinx_mapping = {
    'boto3': ('https://boto3.amazonaws.com/v1/documentation/api/latest/', None),
    'botocore': ('http://botocore.readthedocs.io/en/latest/', None),
    'cryptography': ('https://cryptography.io/en/latest/', None),
    'itsdangerous': ('https://itsdangerous.palletsprojects.com/en/2.0.x/', None),
    'pymongo': ('https://pymongo.readthedocs.io/en/stable/', None),
    'python': ('https://docs.python.org/3', None),
    'redis': ('https://redis-py.readthedocs.io/en/stable/', None),
    'requests': ('https://docs.python-requests.org/en/master/', None),
    'urllib3': ('https://urllib3.readthedocs.io/en/latest/', None),
}
extlinks = {
    'boto3': ('https://boto3.amazonaws.com/v1/documentation/api/latest/reference/%s', None),
}

# Enable Google-style docstrings
napoleon_google_docstring = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False

# Strip prompt text when copying code blocks with copy button
copybutton_prompt_text = r'>>> |\.\.\. |\$ '
copybutton_prompt_is_regexp = True

# Generate labels in the format <page>:<section>
autosectionlabel_prefix_document = True

# Use sphinx_autodoc_typehints extension instead of autodoc's built-in type hints
autodoc_typehints = 'none'
always_document_param_types = True

# Use apidoc to auto-generate rst sources
apidoc_module_dir = PACKAGE_DIR
apidoc_output_dir = 'modules'
apidoc_excluded_paths = ['session.py']
apidoc_extra_args = [f'--templatedir={TEMPLATE_DIR}']  # Note: Must be an absolute path
apidoc_module_first = True
apidoc_separate_modules = True
apidoc_toc_file = False

# HTML general settings
html_favicon = join('_static', 'favicon.ico')
html_js_files = ['collapsible_container.js']
html_css_files = [
    'collapsible_container.css',
    'table.css',
    'https://use.fontawesome.com/releases/v5.15.3/css/all.css',
    'https://use.fontawesome.com/releases/v5.15.3/css/v4-shims.css',
]
html_show_copyright = False
html_show_sphinx = False
notfound_default_version = 'stable'
pygments_style = 'friendly'
pygments_dark_style = 'material'

# HTML theme settings
html_theme = 'furo'
html_theme_options = {
    'light_logo': 'requests-cache-logo-light.webp',
    'dark_logo': 'requests-cache-logo-dark.webp',
    'sidebar_hide_name': True,
    'light_css_variables': {
        'color-brand-primary': '#0288d1',
        'color-brand-content': '#2a5adf',
    },
    'dark_css_variables': {
        'color-brand-primary': '#5eb8ff',
        'color-brand-content': '#368ce2',
    },
}


def setup(app):
    """Run some additional steps after the Sphinx builder is initialized"""
    app.add_css_file('collapsible_container.css')
    app.connect('builder-inited', patch_automodapi)


def patch_automodapi(app):
    """Monkey-patch the automodapi extension to exclude imported members:
    https://github.com/astropy/sphinx-automodapi/blob/master/sphinx_automodapi/automodsumm.py#L135

    Also patches an unreleased fix for Sphinx 4 compatibility:
    https://github.com/astropy/sphinx-automodapi/pull/129
    """
    from sphinx_automodapi import automodsumm
    from sphinx_automodapi.automodsumm import Automodsumm
    from sphinx_automodapi.utils import find_mod_objs

    automodsumm.find_mod_objs = lambda *args: find_mod_objs(args[0], onlylocals=True)
    Automodsumm.warn = lambda *args: logging.getLogger('sphinx_automodapi').warn(*args)
