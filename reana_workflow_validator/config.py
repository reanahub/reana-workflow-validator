# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Configuration for the REANA workflow validator sandbox entrypoint."""

import os

# The report sentinels, loader exit codes, and accepted spec filenames are the
# wire contract shared with reana-workflow-controller and reana-server; import
# them from reana-commons (re-exported here) so the contract has a single source.
from reana_commons.validation.sandbox import (  # noqa: F401
    EXIT_INTERNAL_ERROR,
    EXIT_LOAD_ERROR,
    EXIT_LOADED,
    REANA_SPEC_FILENAMES,
    REPORT_END,
    REPORT_START,
)

INPUT_DIR = os.getenv("REANA_VALIDATION_INPUT_DIR", "/validation/input")
"""Read-only directory where the raw spec bundle (reana.yaml + referenced
workflow/config files) is mounted by reana-workflow-controller."""

WORK_DIR = os.getenv("REANA_VALIDATION_WORK_DIR", "/validation/work")
"""Writable ephemeral directory (an ``emptyDir``) into which the read-only
bundle is copied before loading. Loading Snakemake/CWL workflows writes scratch
files (``.snakemake/``, cwltool temp dirs) next to the workflow, so the workdir
must be writable -- while the shared-volume bundle mount stays read-only, which
keeps the sandbox unable to write anywhere persistent."""

SPEC_BUNDLE_MAX_FILES = int(os.getenv("REANA_SPEC_BUNDLE_MAX_FILES", "1000"))
"""Maximum number of regular files copied from the validation snapshot."""

SPEC_BUNDLE_MAX_BYTES = int(
    os.getenv("REANA_SPEC_BUNDLE_MAX_BYTES", str(100 * 1024 * 1024))
)
"""Maximum cumulative bytes copied from the validation snapshot."""
