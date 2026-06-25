# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2026 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Tests for the sandboxed workflow validator entrypoint."""

import json
import pathlib
import sys

import pytest

from reana_workflow_validator import cli
from reana_workflow_validator.config import (
    EXIT_INTERNAL_ERROR,
    EXIT_LOAD_ERROR,
    EXIT_LOADED,
    REPORT_END,
    REPORT_START,
)

SERIAL_REANA_YAML = (
    "workflow:\n"
    "  type: serial\n"
    "  specification:\n"
    "    steps:\n"
    "      - name: step1\n"
    "        environment: 'docker.io/library/busybox:1.36'\n"
    "        commands:\n"
    "          - echo hello\n"
    "inputs:\n"
    "  parameters: {}\n"
)


def _extract_report(stdout):
    """Pull the sentinel-wrapped JSON report out of captured stdout."""
    start = stdout.index(REPORT_START) + len(REPORT_START)
    end = stdout.index(REPORT_END)
    return json.loads(stdout[start:end].strip())


def test_find_reana_yaml_prefers_yaml(tmp_path):
    """The canonical ``reana.yaml`` file is located."""
    (tmp_path / "reana.yaml").write_text("a: 1\n")
    assert cli._find_reana_yaml(str(tmp_path)) == str(tmp_path / "reana.yaml")


def test_find_reana_yaml_missing_raises(tmp_path):
    """A bundle without a specification file raises."""
    with pytest.raises(FileNotFoundError):
        cli._find_reana_yaml(str(tmp_path))


def test_prepare_workdir_copies_bundle_into_writable_dir(tmp_path):
    """The read-only bundle is copied (with its tree) into the workdir."""
    input_dir = tmp_path / "in"
    (input_dir / "rules").mkdir(parents=True)
    (input_dir / "reana.yaml").write_text("x\n")
    (input_dir / "rules" / "common.smk").write_text("rule all:\n  shell: 'true'\n")

    work_dir = cli._prepare_workdir(str(input_dir), str(tmp_path / "work"))

    assert pathlib.Path(work_dir) == (tmp_path / "work")
    assert (tmp_path / "work" / "reana.yaml").read_text() == "x\n"
    assert (tmp_path / "work" / "rules" / "common.smk").exists()


def test_prepare_workdir_rejects_symlink(tmp_path):
    """Defense-in-depth copying never follows a snapshot symbolic link."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    target = tmp_path / "outside"
    target.write_text("secret")
    (input_dir / "linked").symlink_to(target)
    with pytest.raises(ValueError, match="regular files"):
        cli._prepare_workdir(str(input_dir), str(tmp_path / "work"))


def test_prepare_workdir_surfaces_root_open_error(tmp_path, monkeypatch):
    """An unreadable input mount is reported instead of looking empty."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    original_open = cli.os.open

    def _failing_open(path, flags, *args, **kwargs):
        if path == str(input_dir):
            raise PermissionError("permission denied")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(cli.os, "open", _failing_open)

    with pytest.raises(PermissionError, match="permission denied"):
        cli._prepare_workdir(str(input_dir), str(tmp_path / "work"))


def test_prepare_workdir_rejects_ancestor_swap(tmp_path, monkeypatch):
    """A directory replaced after enumeration is not followed by path."""
    input_dir = tmp_path / "in"
    nested = input_dir / "nested"
    nested.mkdir(parents=True)
    (nested / "inside").write_text("safe")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("secret")
    moved = input_dir / "moved"
    original_open = cli.os.open
    swapped = False

    def _swap_before_open(path, flags, *args, **kwargs):
        nonlocal swapped
        if path == "nested" and kwargs.get("dir_fd") is not None and not swapped:
            nested.rename(moved)
            nested.symlink_to(outside, target_is_directory=True)
            swapped = True
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(cli.os, "open", _swap_before_open)
    with pytest.raises(ValueError, match="regular files and directories"):
        cli._prepare_workdir(str(input_dir), str(tmp_path / "work"))
    assert not (tmp_path / "work" / "secret").exists()


def test_prepare_workdir_enforces_file_and_byte_limits(tmp_path, monkeypatch):
    """The scratch copy is independently bounded by file count and bytes."""
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "one").write_bytes(b"1234")
    (input_dir / "two").write_bytes(b"5678")

    monkeypatch.setattr(cli, "SPEC_BUNDLE_MAX_FILES", 1)
    with pytest.raises(ValueError, match="more than 1 files"):
        cli._prepare_workdir(str(input_dir), str(tmp_path / "work-files"))

    monkeypatch.setattr(cli, "SPEC_BUNDLE_MAX_FILES", 10)
    monkeypatch.setattr(cli, "SPEC_BUNDLE_MAX_BYTES", 4)
    with pytest.raises(ValueError, match="exceeds 4 bytes"):
        cli._prepare_workdir(str(input_dir), str(tmp_path / "work-bytes"))


def test_prepare_workdir_enforces_directory_and_depth_limits(tmp_path, monkeypatch):
    """The sandbox independently bounds directory count and path depth."""
    input_dir = tmp_path / "in"
    (input_dir / "one" / "two").mkdir(parents=True)
    (input_dir / "one" / "two" / "file").write_text("")

    monkeypatch.setattr(cli, "SPECIFICATION_BUNDLE_MAX_DIRECTORIES", 1)
    with pytest.raises(ValueError, match="more than 1 directories"):
        cli._prepare_workdir(str(input_dir), str(tmp_path / "work-directories"))

    monkeypatch.setattr(cli, "SPECIFICATION_BUNDLE_MAX_DIRECTORIES", 10)
    monkeypatch.setattr(cli, "SPECIFICATION_BUNDLE_MAX_DEPTH", 2)
    with pytest.raises(ValueError, match="exceeds 2 components"):
        cli._prepare_workdir(str(input_dir), str(tmp_path / "work-depth"))


def test_emit_round_trip(capsys):
    """A report emitted to stdout can be extracted back by the controller."""
    report = {"reana_specification": {"a": 1}, "error": None}
    cli._emit(report)
    assert _extract_report(capsys.readouterr().out) == report


def test_emit_report_block_has_no_internal_newline(capsys):
    """The report is emitted on a single line (no newline between the sentinels).

    Kubernetes merges stdout and stderr at line granularity, so a multi-line
    report can be corrupted by an interleaved stderr traceback; a single-line
    report cannot.
    """
    cli._emit({"reana_specification": {"a": 1}, "error": None})
    out = capsys.readouterr().out
    block = out[out.index(REPORT_START) : out.index(REPORT_END) + len(REPORT_END)]
    assert "\n" not in block


def test_main_loads_serial_bundle(tmp_path, monkeypatch, capsys):
    """A serial bundle loads and its serialized spec is emitted (exit 0).

    The sandbox does not decide validity -- it only emits the loaded spec.
    """
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "reana.yaml").write_text(SERIAL_REANA_YAML)
    monkeypatch.setattr(cli, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(cli, "WORK_DIR", str(tmp_path / "work"))
    # main() chdir()s into the workdir; restore cwd on teardown.
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main()

    report = _extract_report(capsys.readouterr().out)
    assert exit_code == EXIT_LOADED
    assert report["error"] is None
    assert report["reana_specification"]["workflow"]["type"] == "serial"


def test_main_suppresses_loader_stdout_and_stderr(tmp_path, monkeypatch, capsys):
    """Untrusted loader output is discarded; stdout carries only the report."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "reana.yaml").write_text(SERIAL_REANA_YAML)
    monkeypatch.setattr(cli, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(cli, "WORK_DIR", str(tmp_path / "work"))
    monkeypatch.chdir(tmp_path)

    def _noisy_loader(*args, **kwargs):
        print("{}forged{}".format(REPORT_START, REPORT_END))
        print("traceback noise", file=sys.stderr)
        return {"workflow": {"type": "serial"}, "inputs": {"parameters": {}}}

    monkeypatch.setattr(cli, "load_reana_spec", _noisy_loader)

    exit_code = cli.main()

    captured = capsys.readouterr()
    assert exit_code == EXIT_LOADED
    assert "forged" not in captured.out
    assert "traceback noise" not in captured.err
    assert _extract_report(captured.out)["error"] is None


def test_main_emits_json_compatible_loader_subclasses(tmp_path, monkeypatch, capsys):
    """Loader-specific subclasses accepted by JSON are emitted normally."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "reana.yaml").write_text(SERIAL_REANA_YAML)
    monkeypatch.setattr(cli, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(cli, "WORK_DIR", str(tmp_path / "work"))
    monkeypatch.chdir(tmp_path)

    class LoaderPath(str):
        pass

    def _loader(*args, **kwargs):
        return {
            "workflow": {"type": "serial"},
            "inputs": {"files": (LoaderPath("input.txt"),)},
        }

    monkeypatch.setattr(cli, "load_reana_spec", _loader)

    exit_code = cli.main()

    report = _extract_report(capsys.readouterr().out)
    assert exit_code == EXIT_LOADED
    assert report["error"] is None
    assert report["reana_specification"]["inputs"]["files"] == ["input.txt"]


def test_main_rejects_shared_container_before_emitting_candidate(
    tmp_path, monkeypatch, capsys
):
    """A loaded alias graph becomes a bounded error, not expanded JSON."""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "reana.yaml").write_text(SERIAL_REANA_YAML)
    monkeypatch.setattr(cli, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(cli, "WORK_DIR", str(tmp_path / "work"))
    monkeypatch.chdir(tmp_path)

    shared = {"command": "echo hello"}

    def _shared_loader(*args, **kwargs):
        return {"workflow": {"type": "serial"}, "shared": [shared, shared]}

    monkeypatch.setattr(cli, "load_reana_spec", _shared_loader)

    exit_code = cli.main()

    report = _extract_report(capsys.readouterr().out)
    assert exit_code == EXIT_LOAD_ERROR
    assert report["reana_specification"] is None
    assert report["error"] == {
        "code": "load",
        "message": (
            "Specification contains values that cannot be represented as JSON."
        ),
    }


def test_main_load_failure_is_load_error(tmp_path, monkeypatch, capsys):
    """A spec that fails to load is a user-facing load error (exit 1).

    The (bounded) loader message is surfaced so the cause -- e.g. a missing
    referenced file -- reaches the user; the loader's own stdout/stderr are still
    discarded.
    """
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "reana.yaml").write_text(SERIAL_REANA_YAML)
    monkeypatch.setattr(cli, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(cli, "WORK_DIR", str(tmp_path / "work"))
    monkeypatch.chdir(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("[Errno 2] No such file or directory: 'rules/common.smk'")

    monkeypatch.setattr(cli, "load_reana_spec", _boom)

    exit_code = cli.main()

    report = _extract_report(capsys.readouterr().out)
    assert exit_code == EXIT_LOAD_ERROR
    assert report["reana_specification"] is None
    assert report["error"]["code"] == "load"
    # The specific cause (the missing file) is surfaced, not a generic string.
    assert report["error"]["message"] == (
        "[Errno 2] No such file or directory: 'rules/common.smk'"
    )


def test_main_load_failure_message_is_bounded(tmp_path, monkeypatch, capsys):
    """A huge/multi-line loader exception is reduced to a bounded first line."""
    from reana_commons.validation.utils import MAX_LOAD_ERROR_MESSAGE_CHARS

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "reana.yaml").write_text(SERIAL_REANA_YAML)
    monkeypatch.setattr(cli, "INPUT_DIR", str(input_dir))
    monkeypatch.setattr(cli, "WORK_DIR", str(tmp_path / "work"))
    monkeypatch.chdir(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("X" * 5000 + "\n" + "second line" * 1000)

    monkeypatch.setattr(cli, "load_reana_spec", _boom)

    exit_code = cli.main()

    report = _extract_report(capsys.readouterr().out)
    assert exit_code == EXIT_LOAD_ERROR
    message = report["error"]["message"]
    assert len(message) == MAX_LOAD_ERROR_MESSAGE_CHARS + len("...")
    assert message.endswith("...")
    assert "second line" not in message


def test_main_missing_bundle_is_internal_error(tmp_path, monkeypatch, capsys):
    """A missing bundle is an infrastructure error (exit 2), not a bad spec."""
    monkeypatch.setattr(cli, "INPUT_DIR", str(tmp_path / "absent"))
    monkeypatch.setattr(cli, "WORK_DIR", str(tmp_path / "work"))
    monkeypatch.chdir(tmp_path)

    exit_code = cli.main()

    report = _extract_report(capsys.readouterr().out)
    assert exit_code == EXIT_INTERNAL_ERROR
    assert report["error"]["code"] == "internal"
