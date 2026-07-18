"""Unit tests for command-line workflow selection and exclusivity."""

import argparse
import sys

import pytest

from ipa_clutch_batch import main


def test_ssh22_mode_runs_without_an_input_directory(monkeypatch):
    """Select only the standalone port 22 tunnel workflow."""
    arguments = argparse.Namespace(input_path=None, clutch=False, ssh22=True)
    recorded_calls = []

    def parse_ssh22_arguments():
        return arguments

    def initialize_environment():
        recorded_calls.append("init")

    def run_mock_ssh22_tunnel():
        recorded_calls.append("ssh22")
        return 0

    monkeypatch.setattr(main, "_parse_arguments", parse_ssh22_arguments)
    monkeypatch.setattr(main, "init_app_env", initialize_environment)
    monkeypatch.setattr(main, "run_ssh22_tunnel", run_mock_ssh22_tunnel)

    exit_code = main.main()

    assert exit_code == 0
    assert recorded_calls == ["init", "ssh22"]


@pytest.mark.parametrize(
    "command_arguments",
    [
        ["ipa-clutch-batch", "-ssh22", "--clutch"],
        ["ipa-clutch-batch", "-ssh22", "input"],
    ],
)
def test_ssh22_rejects_other_workflow_arguments(
    monkeypatch,
    command_arguments,
):
    """Reject Clutch checks and IPA paths when -ssh22 is selected."""
    monkeypatch.setattr(sys, "argv", command_arguments)

    with pytest.raises(SystemExit) as system_exit:
        main._parse_arguments()

    assert system_exit.value.code == 2
