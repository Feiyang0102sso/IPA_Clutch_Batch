"""Unit tests for the native terminal progress display."""

from io import StringIO
import logging
from pathlib import Path

from ipa_clutch_batch import logger as logger_module
from ipa_clutch_batch.progress import (
    BAR_WIDTH,
    FINISHED_MESSAGE,
    IpaProcessingStep,
    WorkflowProgress,
)


def test_progress_display_renders_all_three_completed_stages():
    """Render SSH, Clutch, and exact IPA processed counts."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(stream=output_stream)

    progress_display.start_ssh_stage()
    progress_display.complete_ssh_stage()
    progress_display.start_clutch_stage()
    progress_display.complete_clutch_stage()
    progress_display.start_ipa_processing(2)

    first_ipa_path = Path("first.ipa")
    second_ipa_path = Path("second.ipa")
    for ipa_path in (first_ipa_path, second_ipa_path):
        with progress_display.track_ipa(ipa_path):
            for step in IpaProcessingStep:
                with progress_display.track_ipa_step(ipa_path, step):
                    pass

    progress_display.close()

    rendered_output = output_stream.getvalue()
    assert "SSH Connection" in rendered_output
    assert "1/1" in rendered_output
    assert "Clutch Check & Repair" in rendered_output
    assert "IPA Processing - Install" in rendered_output
    assert "IPA Processing - Crack" in rendered_output
    assert "IPA Processing - Move & Rename" in rendered_output
    assert "6/6" in rendered_output
    assert "Current: second.ipa" in rendered_output
    assert "█" * BAR_WIDTH in rendered_output


def test_warning_clears_and_redraws_active_progress_line():
    """Keep warning text separate from an active progress line."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(stream=output_stream)
    progress_display.open()
    progress_display.start_ipa_processing(3)

    handler = logger_module.ConsoleStreamHandler(output_stream)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    warning_record = logging.LogRecord(
        name="test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="device storage is nearly full",
        args=(),
        exc_info=None,
    )

    try:
        handler.emit(warning_record)
        rendered_output = output_stream.getvalue()
    finally:
        progress_display.close()

    assert "WARNING: device storage is nearly full\n" in rendered_output
    assert rendered_output.endswith("IPA Processing [" + "░" * BAR_WIDTH + "] 0/9")


def test_disabled_progress_is_a_complete_no_op():
    """Allow verbose mode to call the same progress methods without output."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(
        enabled=False,
        stream=output_stream,
    )

    progress_display.open()
    progress_display.start_ssh_stage()
    progress_display.complete_ssh_stage()
    progress_display.start_clutch_stage()
    progress_display.complete_clutch_stage()
    progress_display.start_ipa_processing(1)
    with progress_display.track_ipa_step(
        Path("app.ipa"),
        IpaProcessingStep.INSTALL,
    ):
        pass
    progress_display.close()

    assert output_stream.getvalue() == ""


def test_incomplete_clutch_stage_does_not_show_false_completion():
    """Leave a failed Clutch readiness stage at zero of one."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(stream=output_stream)

    progress_display.start_clutch_stage()
    progress_display.close()

    rendered_output = output_stream.getvalue()
    incomplete_line = "Clutch Check & Repair [" + "░" * BAR_WIDTH + "] 0/1"
    completed_line = "Clutch Check & Repair [" + "█" * BAR_WIDTH + "] 1/1"
    assert incomplete_line in rendered_output
    assert completed_line not in rendered_output


def test_one_of_forty_five_steps_advances_after_one_install_attempt():
    """Use three progress units per IPA in a fifteen-file batch."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(stream=output_stream)
    progress_display.start_ipa_processing(15)

    with progress_display.track_ipa_step(
        Path("first.ipa"),
        IpaProcessingStep.INSTALL,
    ):
        pass

    rendered_output = output_stream.getvalue()
    assert "IPA Processing - Install" in rendered_output
    assert "1/45" in rendered_output


def test_failed_crack_skips_move_and_completes_current_ipa():
    """Fill the final unit when Move is skipped after a Crack failure."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(stream=output_stream)
    ipa_path = Path("failed_crack.ipa")
    progress_display.start_ipa_processing(1)

    with progress_display.track_ipa(ipa_path):
        with progress_display.track_ipa_step(
            ipa_path,
            IpaProcessingStep.INSTALL,
        ):
            pass
        with progress_display.track_ipa_step(
            ipa_path,
            IpaProcessingStep.CRACK,
        ):
            pass

    rendered_output = output_stream.getvalue()
    assert "IPA Processing - Skipped" in rendered_output
    assert "3/3" in rendered_output


def test_unprocessed_ipas_are_not_filled_after_batch_stops():
    """Fill only the handled IPA when later files were never entered."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(stream=output_stream)
    first_ipa_path = Path("first.ipa")
    progress_display.start_ipa_processing(3)

    with progress_display.track_ipa(first_ipa_path):
        with progress_display.track_ipa_step(
            first_ipa_path,
            IpaProcessingStep.INSTALL,
        ):
            pass

    rendered_output = output_stream.getvalue()
    assert "IPA Processing - Skipped" in rendered_output
    assert "3/9" in rendered_output
    assert "9/9" not in rendered_output


def test_finished_message_is_green_and_exact():
    """Print the requested completion message even in verbose mode."""
    output_stream = StringIO()
    progress_display = WorkflowProgress(
        enabled=False,
        stream=output_stream,
    )

    progress_display.show_all_tasks_finished()

    rendered_output = output_stream.getvalue()
    assert rendered_output == f"\033[32m{FINISHED_MESSAGE}\033[0m\n"
