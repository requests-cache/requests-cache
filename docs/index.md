(index-page)=
<!-- Include Readme contents, except for the links to readthedocs, which would be redundant here -->
```{include} ../README.md
:end-before: <!-- RTD-IGNORE -->
```
```{include} ../README.md
:start-after: <!-- END-RTD-IGNORE -->
:end-before: <!-- RTD-IGNORE -->
:relative-docs: docs/
:relative-images:
```

# Contents
```{toctree}
:maxdepth: 2

user_guide
advanced_usage
examples
security
reference
contributing
contributors
related_projects
history
````
