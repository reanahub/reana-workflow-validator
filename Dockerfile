# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

# Use the REANA cluster-component baseline
FROM docker.io/library/ubuntu:24.04

# Configure shell options
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Use default answers in installation commands
ENV DEBIAN_FRONTEND=noninteractive

# Allow pip to install packages in the system site-packages dir
ENV PIP_BREAK_SYSTEM_PACKAGES=true

# Install the system Python toolchain and validator dependencies:
# - nodejs: required by cwltool to evaluate CWL InlineJavascript expressions
# - git: yadage may resolve workflow references via git
# hadolint ignore=DL3008
RUN apt-get update -y && \
    apt-get install --no-install-recommends -y \
      git \
      nodejs \
      python3-pip \
      python3-setuptools \
      python3.12 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install the validator and all workflow engines.
# When building inside the REANA monorepo the reana-commons submodule is present
# under modules/; otherwise install reana-commons from PyPI via install_requires.
WORKDIR /code
COPY . /code

# This image runs inside the hardened spec-validation sandbox without the debug
# host source mount, so install the injected Commons checkout non-editably.
# hadolint ignore=DL3013
RUN if test -e modules/reana-commons; then \
      pip install --no-cache-dir "modules/reana-commons[cwl,snakemake,yadage]" --upgrade; \
    fi && \
    pip install --no-cache-dir .

# The read-only bundle is mounted here by reana-workflow-controller.
ENV REANA_VALIDATION_INPUT_DIR=/validation/input

# Ubuntu reserves UID 1000 for its default user; replace it with REANA's runtime
# identity so the image remains non-root by default and matches the controller.
# hadolint ignore=DL3059
RUN userdel -r ubuntu && \
    useradd --uid 1000 --gid 0 --create-home reana
USER reana

ENTRYPOINT ["reana-validate-spec"]
