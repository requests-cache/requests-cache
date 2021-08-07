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
    'sphinx_copybutton',
    'sphinx_inline_tabs',
    'sphinxcontrib.apidoc',
    'myst_parser',
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

# Use apidoc to auto-generate rst sources
apidoc_module_dir = PACKAGE_DIR
apidoc_output_dir = 'modules'
apidoc_excluded_paths = []
apidoc_module_first = True
apidoc_toc_file = False


# HTML general settings
# html_favicon = join('images', 'favicon.ico')
html_js_files = ['collapsible_container.js']
html_css_files = ['collapsible_container.css', 'table.css']
html_show_sphinx = False
pygments_style = 'friendly'
pygments_dark_style = 'material'

# HTML theme settings
html_theme = 'furo'
html_theme_options = {
    # 'light_css_variables': {
    #     'color-brand-primary': '#00766c',  # MD light-blue-600; light #64d8cb | med #26a69a
    #     'color-brand-content': '#006db3',  # MD teal-400;       light #63ccff | med #039be5
    # },
    # 'dark_css_variables': {
    #     'color-brand-primary': '#64d8cb',
    #     'color-brand-content': '#63ccff',
    # },
    # 'sidebar_hide_name': True,
}


def setup(app):
    """Run some additional steps after the Sphinx builder is initialized"""
    app.add_css_file('collapsible_container.css')
