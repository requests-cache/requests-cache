"""requests-cache documentation build config.

Notes:

* MyST-flavored markdown is used instead of rST for all user guide docs
* API reference docs are generated based on module docstrings
* Google-style docstrings are used throughout the project
* apidoc is used to generate source files for the majority of module docs
* The `api/` directory contains manually formatted sources for some modules
* The `_templates` directory contains some Sphinx templates that modify auto-generated sources
"""
import os
import sys
from os.path import join
from pathlib import Path
from shutil import copy

# Add project path
sys.path.insert(0, os.path.abspath('..'))
from requests_cache import __version__  # noqa: E402

DOCS_DIR = Path(__file__).parent.absolute()
PROJECT_DIR = DOCS_DIR.parent
PACKAGE_DIR = PROJECT_DIR / 'requests_cache'
TEMPLATE_DIR = DOCS_DIR / '_templates'
EXTRA_APIDOC_DIR = DOCS_DIR / 'api'
APIDOC_DIR = DOCS_DIR / 'modules'


# General information about the project.
project = 'requests-cache'
needs_sphinx = '4.0'
master_doc = 'index'
source_suffix = ['.md', '.rst']
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
    'sphinx_design',
    'sphinxcontrib.apidoc',
    'sphinxext.opengraph',
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

# Ignore a subset of auto-generated pages
exclude_patterns = [
    '_build',
    f'{APIDOC_DIR.stem}/requests_cache.rst',
    f'{EXTRA_APIDOC_DIR.stem}/*',
]

# Enable automatic links to other projects' Sphinx docs
intersphinx_mapping = {
    'attrs': ('https://www.attrs.org/en/stable/', None),
    'boto3': ('https://boto3.amazonaws.com/v1/documentation/api/latest/', None),
    'botocore': ('https://botocore.readthedocs.io/en/latest/', None),
    'cattrs': ('https://cattrs.readthedocs.io/en/latest/', None),
    'cryptography': ('https://cryptography.io/en/latest/', None),
    'itsdangerous': ('https://itsdangerous.palletsprojects.com/en/2.0.x/', None),
    'pymongo': ('https://pymongo.readthedocs.io/en/stable/', None),
    'python': ('https://docs.python.org/3', None),
    'redis': ('https://redis-py.readthedocs.io/en/stable/', None),
    'requests': ('https://requests.readthedocs.io/en/latest/', None),
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

# Move type hint info to function description instead of signature
autodoc_typehints = 'description'
always_document_param_types = True

# Use apidoc to auto-generate rst sources
apidoc_module_dir = str(PACKAGE_DIR)
apidoc_output_dir = APIDOC_DIR.stem
apidoc_excluded_paths = ['session.py']
apidoc_extra_args = [f'--templatedir={TEMPLATE_DIR}']  # Note: Must be an absolute path
apidoc_module_first = True
apidoc_separate_modules = True
apidoc_toc_file = False

# HTML general settings
html_favicon = join('_static', 'favicon.ico')
html_css_files = [
    'table.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css',
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
    app.connect('builder-inited', copy_module_docs)


def patch_automodapi(app):
    """Monkey-patch the automodapi extension to exclude imported members:
    https://github.com/astropy/sphinx-automodapi/blob/master/sphinx_automodapi/automodsumm.py#L135
    """
    from sphinx_automodapi import automodsumm
    from sphinx_automodapi.utils import find_mod_objs

    automodsumm.find_mod_objs = lambda *args: find_mod_objs(args[0], onlylocals=True)


def copy_module_docs(app):
    """Copy manually written doc sources to apidoc directory"""
    for doc in EXTRA_APIDOC_DIR.iterdir():
        copy(doc, APIDOC_DIR)
