#!/usr/bin/env python3

import os
import sys
from setuptools import find_packages

# Hack to get version number since it's considered bad practice to import your
# own package in setup.py. This call defines keys 'version', 'authors', and
# 'banner' in the `metadata` dict.
metadata = {}
with open('siliconcompiler/_metadata.py') as f:
    exec(f.read(), metadata)

try:
    from skbuild import setup
except ImportError:
    print(
        "Error finding build dependencies!\n"
        "If you're installing this project using pip, make sure you're using pip version 10 or greater.\n"
        "If you're installing this project by running setup.py, manually install all dependencies listed in requirements.txt.",
        file=sys.stderr
    )
    raise

with open("README.md", "r", encoding="utf-8") as readme:
  long_desc = readme.read()

if not os.path.isdir('third_party/tools/openroad/tools/OpenROAD/src/OpenDB/src/lef'):
    print('Source for LEF parser library not found! Install OpenROAD submodule before continuing with install:\n'
          'git submodule update --init --recursive third_party/tools/openroad')
    sys.exit(1)

# Let us pass in generic arguments to CMake via an environment variable, since
# our automated build servers need to pass in a certain argument when building
# wheels on Windows.
cmake_args = []
if 'SC_CMAKEARGS' in os.environ:
    cmake_args.append(os.environ['SC_CMAKEARGS'])

setup(
    name="siliconcompiler",
    description="Silicon Compiler Collection (SCC)",
    keywords=["HDL", "ASIC", "FPGA", "hardware design"],
    long_description=long_desc,
    long_description_content_type="text/markdown",
    author="Andreas Olofsson",
    url="https://github.com/siliconcompiler/siliconcompiler",
    version=metadata['version'],
    packages=find_packages(where='.', exclude=['tests*']),

    # TODO: hack to work around weird scikit-build behavior:
    # https://github.com/scikit-build/scikit-build/issues/590
    # Once this issue is resolved, we should switch to setting
    # include_package_data to True instead of manually specifying package_data.

    #include_package_data=True,
    package_data={
        'siliconcompiler': ['templates/*.j2'],
        'siliconcompiler.tools': ['**/*.tcl', '**/*.py', '**/*.xml', '**/*.magicrc', '**/*.openfpga']
    },

    python_requires=">=3.6",
    install_requires=[
        "matplotlib >= 3.3",
        "numpy >= 1.19",
        "aiohttp >= 3.7.4.post0",
        "requests >= 2.22.0",
        "PyYAML >= 5.4.1",
        "pytest >= 6.2.4",
        "pytest-xdist >= 2.3.0",
        "defusedxml >= 0.7.1",
        "pandas >= 1.2.3",
        "Jinja2 >= 2.11.3",
        "Sphinx >= 3.5.4",
        "cryptography >= 3.4.7",
        "sphinx-rtd-theme >= 0.5.2",
        "graphviz >=0.17"
    ],
    entry_points={"console_scripts": ["sc=siliconcompiler.__main__:main", "sc-server=siliconcompiler.server:main", "sc-crypt=siliconcompiler.crypto:main"]},
    cmake_install_dir="siliconcompiler/leflib",
    cmake_args=cmake_args
)
