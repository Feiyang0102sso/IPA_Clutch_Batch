"""Render and coordinate all batch workflow progress stages."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from enum import Enum
from pathlib import Path
import sys
from typing import Protocol, TextIO

from ipa_clutch_batch.logger import set_console_output_hooks


BAR_WIDTH = 30
CLEAR_LINE = "\r\033[2K"
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"
FINISHED_MESSAGE = "All Tasks Finished Closing SSH Service"


class IpaProcessingStep(Enum):
    """Name each visible step in one IPA lifecycle."""

    INSTALL = "Install"
    CRACK = "Crack"
    MOVE_AND_RENAME = "Move & Rename"


class BatchProgressReporter(Protocol):
    """Receive progress events from the sequential IPA pipeline."""

    def start_ipa_processing(self, total_count: int):
        """Start the IPA stage."""

    def track_ipa(self, ipa_path: Path) -> AbstractContextManager[None]:
        """Track one IPA and fill any skipped steps when it exits."""

    def track_ipa_step(
        self,
        ipa_path: Path,
        step: IpaProcessingStep,
    ) -> AbstractContextManager[None]:
        """Track one attempted IPA processing step."""


class NullBatchProgressReporter:
    """Ignore IPA progress events when no display was supplied."""

    def start_ipa_processing(self, total_count: int):
        """Ignore the IPA total."""

    @contextmanager
    def track_ipa(self, ipa_path: Path) -> Iterator[None]:
        """Ignore one complete IPA lifecycle."""
        yield

    @contextmanager
    def track_ipa_step(
        self,
        ipa_path: Path,
        step: IpaProcessingStep,
    ) -> Iterator[None]:
        """Ignore one attempted IPA processing step."""
        yield


NO_BATCH_PROGRESS = NullBatchProgressReporter()


class WorkflowProgress:
    """Own terminal rendering and progress-aware logging for all stages."""

    def __init__(
        self,
        enabled: bool = True,
        stream: TextIO | None = None,
    ):
        self._enabled = enabled
        self._stream = stream if stream is not None else sys.stdout
        self._active_line: str | None = None
        self._ipa_total_steps = 0
        self._ipa_completed_steps = 0
        self._current_ipa_name = ""
        self._current_ipa_step: IpaProcessingStep | None = None
        self._current_ipa_completed_steps = 0

    def open(self):
        """Enable progress-aware console logging for this workflow."""
        if not self._enabled:
            return
        set_console_output_hooks(
            self.clear_for_log,
            self.redraw_after_log,
        )

    def start_ssh_stage(self):
        """Show the pending SSH connection stage."""
        self._set_active_progress("SSH Connection", 0, 1)

    def complete_ssh_stage(self):
        """Complete the SSH stage and keep its final result visible."""
        self._complete_single_step_stage("SSH Connection")

    def start_clutch_stage(self):
        """Show the pending Clutch check and repair stage."""
        self._set_active_progress("Clutch Check & Repair", 0, 1)

    def complete_clutch_stage(self):
        """Complete the Clutch stage after its state is ready."""
        self._complete_single_step_stage("Clutch Check & Repair")

    def start_ipa_processing(self, total_count: int):
        """Start the IPA stage with the total number of input files."""
        if not self._enabled:
            return
        self._ipa_total_steps = total_count * len(IpaProcessingStep)
        self._ipa_completed_steps = 0
        self._current_ipa_name = ""
        self._current_ipa_step = None
        self._current_ipa_completed_steps = 0
        self._render_ipa_progress()

    @contextmanager
    def track_ipa(self, ipa_path: Path) -> Iterator[None]:
        """Fill skipped units so every handled IPA consumes three steps."""
        if self._enabled:
            self._current_ipa_name = ipa_path.name
            self._current_ipa_completed_steps = 0

        try:
            yield
        finally:
            if self._enabled:
                self._complete_skipped_ipa_steps()

    @contextmanager
    def track_ipa_step(
        self,
        ipa_path: Path,
        step: IpaProcessingStep,
    ) -> Iterator[None]:
        """Show and advance one attempted IPA processing step."""
        if self._enabled:
            self._current_ipa_name = ipa_path.name
            self._current_ipa_step = step
            self._render_ipa_progress()

        try:
            yield
        finally:
            if self._enabled:
                self._ipa_completed_steps += 1
                self._current_ipa_completed_steps += 1
                self._render_ipa_progress()

    def show_all_tasks_finished(self):
        """Show the requested green message before SSH is closed."""
        self._finish_active_line()
        self._stream.write(f"{GREEN}{FINISHED_MESSAGE}{RESET}\n")
        self._stream.flush()

    def show_final_summary(
        self,
        input_count: int,
        success_count: int,
        fail_count: int,
        failed_ipa_names: tuple[str, ...],
    ):
        """Show final counts and failed input IPA filenames."""
        self._finish_active_line()
        summary_line = (
            f"input:{input_count} "
            f"{GREEN}success:{success_count}{RESET} "
            f"{RED}fail:{fail_count}{RESET}\n"
        )
        self._stream.write(summary_line)

        for ipa_name in failed_ipa_names:
            self._stream.write(f"{RED}fail: {ipa_name}{RESET}\n")

        self._stream.flush()

    def clear_for_log(self):
        """Temporarily clear the progress line before a log is emitted."""
        if self._active_line is None:
            return
        self._stream.write(CLEAR_LINE)
        self._stream.flush()

    def redraw_after_log(self):
        """Restore the active progress line after a log is emitted."""
        if self._active_line is None:
            return
        self._stream.write(self._active_line)
        self._stream.flush()

    def close(self):
        """Finish output and detach the console logging hooks."""
        if not self._enabled:
            return
        self._finish_active_line()
        set_console_output_hooks(None, None)

    def _complete_single_step_stage(self, label: str):
        self._set_active_progress(label, 1, 1)
        self._finish_active_line()

    def _complete_skipped_ipa_steps(self):
        step_count = len(IpaProcessingStep)
        skipped_step_count = step_count - self._current_ipa_completed_steps
        if skipped_step_count == 0:
            return

        self._ipa_completed_steps += skipped_step_count
        self._current_ipa_completed_steps = step_count
        self._current_ipa_step = None
        self._render_ipa_progress("Skipped")

    def _render_ipa_progress(self, step_label: str = ""):
        label = "IPA Processing"
        if step_label:
            label += f" - {step_label}"
        elif self._current_ipa_step is not None:
            label += f" - {self._current_ipa_step.value}"

        detail = ""
        if self._current_ipa_name:
            detail = f"Current: {self._current_ipa_name}"
        self._set_active_progress(
            label,
            self._ipa_completed_steps,
            self._ipa_total_steps,
            detail,
        )

    def _set_active_progress(
        self,
        label: str,
        completed: int,
        total: int,
        detail: str = "",
    ):
        if not self._enabled:
            return

        filled_width = 0
        if total > 0:
            filled_width = BAR_WIDTH * completed // total

        empty_width = BAR_WIDTH - filled_width
        bar = "█" * filled_width + "░" * empty_width
        progress_line = f"{label} [{bar}] {completed}/{total}"
        if detail:
            progress_line += f"  {detail}"

        self._active_line = progress_line
        self._stream.write(f"{CLEAR_LINE}{progress_line}")
        self._stream.flush()

    def _finish_active_line(self):
        if self._active_line is None:
            return
        self._stream.write(f"{CLEAR_LINE}{self._active_line}\n")
        self._stream.flush()
        self._active_line = None
