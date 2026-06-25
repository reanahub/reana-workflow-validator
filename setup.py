# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA-Workflow-Validator."""

import os
import re

from setuptools import find_packages, setup

readme = open("README.md").read()

install_requires = [
    # All workflow engines are needed to load and serialize every spec type.
    "reana-commons[cwl,snakemake,yadage]>=0.95.0a22,<0.96.0",
]

extras_require = {
    "docs": [
        "myst-parser",
        "Sphinx>=1.5.1",
        "sphinx-rtd-theme>=0.1.9",
    ],
    "tests": [
        "pytest>=7.0.0,<9.0.0",
        "pytest-cov>=3.0.0,<4.0",
    ],
}
extras_require["all"] = []
for key, reqs in extras_require.items():
    if ":" == key[0]:
        continue
    extras_require["all"].extend(reqs)

packages = find_packages()

with open(os.path.join("reana_workflow_validator", "version.py"), "rt") as f:
    version = re.search(r'__version__\s*=\s*"(?P<version>.*)"\n', f.read()).group(
        "version"
    )

setup(
    name="reana-workflow-validator",
    version=version,
    description=__doc__,
    long_description=readme,
    long_description_content_type="text/markdown",
    author="REANA",
    author_email="info@reana.io",
    url="https://github.com/reanahub/reana-workflow-validator",
    packages=packages,
    zip_safe=False,
    install_requires=install_requires,
    extras_require=extras_require,
    entry_points={
        "console_scripts": [
            "reana-validate-spec=reana_workflow_validator.cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering",
    ],
)
