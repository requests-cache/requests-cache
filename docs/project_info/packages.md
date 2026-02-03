# {fas}`box-open` Downstream Packages
Besides the [PyPI package](https://pypi.org/project/requests-cache/), several downstream builds are available.


Conda ([src](https://anaconda.org/conda-forge/requests-cache)):

```sh
conda install conda-forge::requests-cache
```

Arch Linux ([src](https://archlinux.org/packages/extra/any/python-requests-cache)):
```sh
pacman -S python-requests-cache
```

Debian ([src](https://packages.debian.org/forky/python3-requests-cache)) and Ubuntu ([src](https://packages.ubuntu.com/resolute/python3-requests-cache)):
```sh
apt-get install python3-requests-cache
```

Fedora ([src](https://packages.fedoraproject.org/pkgs/python-requests-cache/python3-requests-cache)):
```sh
dnf install python3-requests-cache
```

FreeBSD ([src](https://www.freshports.org/www/py-requests-cache)):
```sh
pkg install www/py-requests-cache
```

Guix ([src](https://packages.guix.gnu.org/packages/python-requests-cache/)):
```sh
guix install python-requests-cache
```

Nix ([src](https://github.com/NixOS/nixpkgs/blob/master/pkgs/development/python-modules/requests-cache/default.nix)):
```haskell
environment.systemPackages = with pkgs; [
  (python3.withPackages (python-pkgs: [
    python-pkgs.requests-cache
  ]))
];
```

Additional downstream builds (of varying freshness) can be found on [Repology](https://repology.org/project/python:requests-cache/versions).
