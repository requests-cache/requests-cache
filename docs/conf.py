# requests-cache documentation build configuration file
import os
import sys

# Add project path
sys.path.insert(0, os.path.abspath('..'))

from requests_cache import __version__  # noqa: E402

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
    # 'sphinxcontrib.apidoc',
    'm2r2',
]

# Enable automatic links to other projects' Sphinx docs
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.io/en/master/', None),
    'urllib3': ('http://urllib3.readthedocs.org/en/latest', None),
}

# Enable Google-style docstrings
napoleon_google_docstring = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = False

# Strip prompt text when copying code blocks with copy button
copybutton_prompt_text = r'>>> |\.\.\. |\$ '
copybutton_prompt_is_regexp = True

# HTML theme settings
pygments_style = 'sphinx'
html_theme = 'sphinx_rtd_theme'
