# {fa}`download` Installation
Installation instructions:

:::{tab} Pip
Install the latest stable version from [PyPI](https://pypi.org/project/requests-cache/):
```
pip install requests-cache
```
:::
:::{tab} Conda
Or install from [conda-forge](https://anaconda.org/conda-forge/requests-cache), if you prefer:
```
conda install -c conda-forge requests-cache
```
:::
:::{tab} Pre-release
If you would like to use the latest development (pre-release) version:
```
pip install --pre requests-cache
```
:::
:::{tab} Local development
See {ref}`contributing` for setup steps for local development
:::

(requirements)=
## Requirements
You may need additional dependencies depending on which features you want to use. To install with
extra dependencies for all supported {ref}`backends` and {ref}`serializers`:
```
pip install requests-cache[all]
```

## Python Version Compatibility
The latest version of requests-cache requires **python 3.7+**. If you need to use an older version
of python, here are the latest compatible versions and their documentation pages:

* **python 2.6:** [requests-cache 0.4.13](https://requests-cache.readthedocs.io/en/v0.4.13)
* **python 2.7:** [requests-cache 0.5.2](https://requests-cache.readthedocs.io/en/v0.5.0)
* **python 3.4:** [requests-cache 0.5.2](https://requests-cache.readthedocs.io/en/v0.5.0)
* **python 3.5:** [requests-cache 0.5.2](https://requests-cache.readthedocs.io/en/v0.5.0)
* **python 3.6:** [requests-cache 0.7.4](https://requests-cache.readthedocs.io/en/v0.7.4)
