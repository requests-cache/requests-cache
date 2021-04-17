# requests-cache documentation build configuration file
import os
import sys
from os.path import abspath, dirname, join

# Add project path
sys.path.insert(0, os.path.abspath('..'))

from requests_cache import __version__  # noqa: E402

PROJECT_DIR = abspath(dirname(dirname(__file__)))
PACKAGE_DIR = join(PROJECT_DIR, 'requests_cache')

# General information about the project.
project = 'requests-cache'
copyright = '2021, Roman Haritonov'
needs_sphinx = '3.0'
master_doc = 'index'
source_suffix = ['.rst', '.md']
version = release = __version__
html_static_path = ['_static']
exclude_patterns = ['_build']
templates_path = ['_templates']

# Sphinx extension modules
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosectionlabel',
    'sphinx.ext.intersphinx',
    'sphinx.ext.napoleon',
    'sphinx.ext.viewcode',
    'sphinx_autodoc_typehints',
    'sphinx_copybutton',
    'sphinxcontrib.apidoc',
    'm2r2',
]

# Exclude auto-generated page for top-level __init__.py
exclude_patterns = ['_build', 'modules/requests_cache.rst']

# Enable automatic links to other projects' Sphinx docs
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://docs.python-requests.org/en/master/', None),
    'urllib3': ('https://urllib3.readthedocs.io/en/latest/', None),
}

# Enable Google-style docstrings
napoleon_google_docstring = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False

# Strip prompt text when copying code blocks with copy button
copybutton_prompt_text = r'>>> |\.\.\. |\$ '
copybutton_prompt_is_regexp = True

# Use apidoc to auto-generate rst sources
apidoc_module_dir = PACKAGE_DIR
apidoc_output_dir = 'modules'
apidoc_excluded_paths = []
apidoc_module_first = True
apidoc_toc_file = False
autosectionlabel_prefix_document = True

# HTML theme settings
pygments_style = 'sphinx'
html_theme = 'sphinx_rtd_theme'


def setup(app):
    """Run some additional steps after the Sphinx builder is initialized"""
    app.add_css_file('collapsible_container.css')
