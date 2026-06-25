# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""REANA-Workflow-Validator sandbox entrypoint.

Runs inside a defense-in-depth Kubernetes Job (no service-account token, no
secrets, no workspace, and a read-only root filesystem). The Job requests
egress restrictions through NetworkPolicy; actual enforcement depends on the
cluster CNI and standard NetworkPolicy cannot isolate it from the resident node.
The entrypoint is a pure **loader**: it loads the raw spec bundle -- which for
Snakemake/CWL/Yadage
means executing the real engines, i.e. *running untrusted code* -- and prints
the resulting serialized specification as a single JSON report to stdout
(wrapped in sentinels), exiting with a status code the controller reads:

* ``0`` loaded -- the report carries the serialized ``reana_specification``,
* ``1`` the specification could not be loaded (a user-facing error; the report's
  ``error`` explains why),
* ``2`` internal/infrastructure error (e.g. bundle missing).

It does **not** apply cluster policy (vetted images, backends, quota, retention).
Because this process runs untrusted code, nothing it computes could be trusted
anyway, so the valid/invalid decision is made entirely by reana-server, which
re-loads none of it but runs the pure policy checks in-process on the emitted
specification. That is why no policy is injected here and no verdict is emitted.

All diagnostic logging goes to stderr so stdout carries only the report.
"""

import json
import logging
import os
import stat
import sys
from contextlib import redirect_stderr, redirect_stdout

from reana_commons.specification import load_reana_spec
from reana_commons.specification_paths import (
    SPECIFICATION_BUNDLE_MAX_DEPTH,
    SPECIFICATION_BUNDLE_MAX_DIRECTORIES,
)
from reana_commons.validation.sandbox import ERROR_CODE_INTERNAL, ERROR_CODE_LOAD
from reana_commons.validation.utils import bound_error_message, validate_json_tree

from reana_workflow_validator.config import (
    EXIT_INTERNAL_ERROR,
    EXIT_LOAD_ERROR,
    EXIT_LOADED,
    INPUT_DIR,
    REANA_SPEC_FILENAMES,
    REPORT_END,
    REPORT_START,
    SPEC_BUNDLE_MAX_BYTES,
    SPEC_BUNDLE_MAX_FILES,
    WORK_DIR,
)


def _prepare_workdir(input_dir, work_dir):
    """Copy the read-only bundle into a writable workdir and return its path.

    Loading Snakemake/CWL workflows writes scratch files next to the workflow,
    so we never load directly from the read-only shared-volume mount.

    File *contents* are copied without metadata: the bundle is mounted read-only
    and owned by a different user, so preserving permissions/ownership (as
    ``shutil.copytree``/``copy2`` would) fails with "Operation not permitted".
    """
    os.makedirs(work_dir, exist_ok=True)
    os.makedirs(os.environ.get("TMPDIR", "/tmp"), exist_ok=True)
    copied_files = 0
    copied_bytes = 0
    copied_directories = 0

    source_flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
    source_flags |= getattr(os, "O_NOFOLLOW", 0)
    root_flags = source_flags | getattr(os, "O_DIRECTORY", 0)

    def copy_directory(source_directory, destination_directory, relative_directory=""):
        """Copy from a pinned directory descriptor without reopening ancestors."""
        nonlocal copied_directories, copied_files, copied_bytes
        with os.scandir(source_directory) as entries:
            names = []
            for entry in entries:
                names.append(entry.name)
                if (
                    len(names)
                    > SPEC_BUNDLE_MAX_FILES + SPECIFICATION_BUNDLE_MAX_DIRECTORIES
                ):
                    raise ValueError(
                        "Validation snapshot contains too many filesystem entries."
                    )
        names.sort()
        for name in names:
            relative_path = (
                os.path.join(relative_directory, name) if relative_directory else name
            )
            depth = len(relative_path.split(os.sep))
            if depth > SPECIFICATION_BUNDLE_MAX_DEPTH:
                raise ValueError(
                    "Validation snapshot path exceeds {} components: {}".format(
                        SPECIFICATION_BUNDLE_MAX_DEPTH, relative_path
                    )
                )
            try:
                source_descriptor = os.open(name, source_flags, dir_fd=source_directory)
            except OSError as error:
                raise ValueError(
                    "Validation snapshots may contain only regular files and "
                    "directories: {} ({})".format(relative_path, error)
                ) from error
            try:
                mode = os.fstat(source_descriptor).st_mode
                if stat.S_ISDIR(mode):
                    copied_directories += 1
                    if copied_directories > SPECIFICATION_BUNDLE_MAX_DIRECTORIES:
                        raise ValueError(
                            "Validation snapshot contains more than {} "
                            "directories.".format(SPECIFICATION_BUNDLE_MAX_DIRECTORIES)
                        )
                    destination_path = os.path.join(destination_directory, name)
                    os.mkdir(destination_path, 0o700)
                    copy_directory(source_descriptor, destination_path, relative_path)
                    continue
                if not stat.S_ISREG(mode):
                    raise ValueError(
                        "Validation snapshots may contain only regular files and "
                        "directories: {}".format(relative_path)
                    )

                copied_files += 1
                if copied_files > SPEC_BUNDLE_MAX_FILES:
                    raise ValueError(
                        "Validation snapshot contains more than {} files.".format(
                            SPEC_BUNDLE_MAX_FILES
                        )
                    )

                destination_path = os.path.join(destination_directory, name)
                destination_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
                destination_flags |= getattr(os, "O_NOFOLLOW", 0)
                destination_descriptor = os.open(
                    destination_path, destination_flags, 0o600
                )
                try:
                    while True:
                        chunk = os.read(source_descriptor, 1024 * 1024)
                        if not chunk:
                            break
                        copied_bytes += len(chunk)
                        if copied_bytes > SPEC_BUNDLE_MAX_BYTES:
                            raise ValueError(
                                "Validation snapshot exceeds {} bytes.".format(
                                    SPEC_BUNDLE_MAX_BYTES
                                )
                            )
                        offset = 0
                        while offset < len(chunk):
                            offset += os.write(destination_descriptor, chunk[offset:])
                except Exception:
                    os.close(destination_descriptor)
                    try:
                        os.unlink(destination_path)
                    except OSError:
                        pass
                    raise
                else:
                    os.close(destination_descriptor)
            finally:
                os.close(source_descriptor)

    try:
        root_descriptor = os.open(input_dir, root_flags)
    except OSError as error:
        if isinstance(error, PermissionError):
            raise
        raise ValueError(
            "Validation snapshot root must be a regular directory: {}".format(input_dir)
        ) from error
    try:
        if not stat.S_ISDIR(os.fstat(root_descriptor).st_mode):
            raise ValueError(
                "Validation snapshot root must be a regular directory: {}".format(
                    input_dir
                )
            )
        copy_directory(root_descriptor, work_dir)
    finally:
        os.close(root_descriptor)
    return work_dir


def _find_reana_yaml(input_dir):
    """Return the path to the REANA specification file in the bundle."""
    for name in REANA_SPEC_FILENAMES:
        candidate = os.path.join(input_dir, name)
        if os.path.isfile(candidate):
            return candidate
    raise FileNotFoundError(
        "No REANA specification file ({}) found in {}".format(
            " or ".join(REANA_SPEC_FILENAMES), input_dir
        )
    )


def _emit(report):
    """Write the JSON report to stdout as a single sentinel-wrapped line.

    The whole report is emitted on **one** line
    (``<START><json><END>``). Kubernetes merges the container's stdout and
    stderr into one log stream at *line* granularity, so diagnostic output on
    stderr (notably a load-failure traceback written just before this) can
    interleave *between* lines; keeping the report to a single line means such
    output can land before or after it but never corrupt it. ``json.dumps``
    emits no newlines, so the report is always one line.
    """
    sys.stdout.write("\n{}{}{}\n".format(REPORT_START, json.dumps(report), REPORT_END))
    sys.stdout.flush()


def _load_reana_spec_silently(reana_yaml_path, work_dir):
    """Load the spec while discarding stdout/stderr from untrusted loader code."""
    with open(os.devnull, "w") as devnull:
        with redirect_stdout(devnull), redirect_stderr(devnull):
            return load_reana_spec(reana_yaml_path, workspace_path=work_dir)


def main():
    """Load the bundle, emit the serialized spec, and return the exit code."""
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    report = {"reana_specification": None, "error": None}

    # 1. Stage the bundle into a writable workdir (failures here are
    #    infrastructure errors, not a problem with the user's specification).
    try:
        work_dir = _prepare_workdir(INPUT_DIR, WORK_DIR)
        # Load from inside the workdir so that specifications referencing files
        # by a path relative to the bundle root resolve correctly, matching how
        # the spec directory was the CWD on the client.
        os.chdir(work_dir)
        reana_yaml_path = _find_reana_yaml(work_dir)
    except Exception as e:
        logging.exception("Could not prepare validation inputs")
        report["error"] = {"code": ERROR_CODE_INTERNAL, "message": str(e)}
        _emit(report)
        return EXIT_INTERNAL_ERROR

    # 2. Load the spec -- THE UNTRUSTED STEP, and the only thing this sandbox
    #    does. A failure means the spec cannot be loaded, which is a user-facing
    #    error (the server surfaces it as an invalid specification).
    try:
        reana_yaml = _load_reana_spec_silently(reana_yaml_path, work_dir)
        # The loaded candidate must be a finite JSON tree before _emit() runs.
        # In particular, never let a YAML alias graph expand in json.dumps().
        validate_json_tree(reana_yaml)
    except Exception as e:
        # Surface the (bounded) first line of the loader error -- it names the
        # cause (e.g. a missing referenced file) without letting untrusted loader
        # output flood the report. The loader's own stdout/stderr are discarded
        # inside ``_load_reana_spec_silently``; only this exception text is kept.
        report["error"] = {"code": ERROR_CODE_LOAD, "message": bound_error_message(e)}
        _emit(report)
        return EXIT_LOAD_ERROR

    # Emit the full loaded spec (loaded workflow + resolved input parameters).
    # reana-server re-runs the pure policy checks on it in-process and makes the
    # authoritative valid/invalid decision; this sandbox never does.
    report["reana_specification"] = reana_yaml
    _emit(report)
    return EXIT_LOADED


if __name__ == "__main__":
    sys.exit(main())
