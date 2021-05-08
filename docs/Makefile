# Minimal makefile for Sphinx documentation.
# This is only used for local builds, and is not used by Readthedocs.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SOURCEDIR     = .
AUTOSOURCEDIR = $(SOURCEDIR)/modules
BUILDDIR      = _build

# Put this first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help all clean-apidoc Makefile

all: clean clean-apidoc html

clean-apidoc:
	rm -rf "$(AUTOSOURCEDIR)"

# Catch-all target: route all unknown targets to Sphinx builder
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
	# E.g: sphinx-build -M html . _build
