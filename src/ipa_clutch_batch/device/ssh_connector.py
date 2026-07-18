"""
Create and manage an SSH connection to an iOS device through USB.
"""
from dataclasses import dataclass
from pathlib import Path
import socket
import subprocess
import time

import paramiko

from ipa_clutch_batch.common.command_runner import log_ssh_output
from ipa_clutch_batch.config import (
    SSH_CONNECT_TIMEOUT_SECONDS,
    SSH_DEVICE_PORT,
    SSH_HOST,
    SSH_LOCAL_PORT,
    SSH_PASSWORD,
    SSH_USERNAME,
    get_iproxy_path,
)
from ipa_clutch_batch.logger import logger


@dataclass(frozen=True)
class SshCommandResult:
    """Output returned by a remote SSH command."""

    command: str
    exit_code: int
    stdout: str
    stderr: str


class UsbSshConnection:
    """Own one iproxy process and one SSH client connection."""

    def __init__(
        self,
        udid: str,
        iproxy_path: Path | None = None,
        local_port: int = SSH_LOCAL_PORT,
    ):
        self.udid = udid
        self.iproxy_path = iproxy_path
        self.local_port = local_port
        self._iproxy_process: subprocess.Popen[str] | None = None
        self._ssh_client: paramiko.SSHClient | None = None

    def connect(self) -> bool:
        """Start the USB tunnel and authenticate the SSH session."""
        if self._ssh_client is not None:
            logger.error("SSH connection is already open.")
            return False

        proxy_path = self.iproxy_path
        if proxy_path is None:
            proxy_path = get_iproxy_path()

        if not proxy_path.is_file():
            logger.error(f"USB proxy tool not found: {proxy_path}")
            return False

        if _is_local_port_open(self.local_port):
            logger.error(
                f"Local SSH port is already in use: {SSH_HOST}:{self.local_port}"
            )
            return False

        if not self._start_iproxy(proxy_path):
            return False

        if not self._wait_for_tunnel():
            self.close()
            return False

        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        logger.info(
            f"Connecting SSH through USB at {SSH_HOST}:{self.local_port}..."
        )
        try:
            ssh_client.connect(
                hostname=SSH_HOST,
                port=self.local_port,
                username=SSH_USERNAME,
                password=SSH_PASSWORD,
                timeout=SSH_CONNECT_TIMEOUT_SECONDS,
                banner_timeout=SSH_CONNECT_TIMEOUT_SECONDS,
                auth_timeout=SSH_CONNECT_TIMEOUT_SECONDS,
                look_for_keys=False,
                allow_agent=False,
            )
        except (OSError, paramiko.SSHException) as error:
            logger.error(f"SSH connection failed: {error}")
            ssh_client.close()
            self.close()
            return False

        transport = ssh_client.get_transport()
        if transport is None or not transport.is_active():
            logger.error("SSH transport is not active after login.")
            ssh_client.close()
            self.close()
            return False

        transport.set_keepalive(15)
        self._ssh_client = ssh_client
        logger.info("SSH connection established through USB.")
        return True

    def execute_command(
        self,
        command: str,
        use_pty: bool = False,
    ) -> SshCommandResult | None:
        """Execute one command over SSH, optionally with a pseudo-terminal."""
        if self._ssh_client is None or not self.is_active():
            logger.error("Cannot execute command because SSH is not connected.")
            return None

        logger.info(f"Executing SSH command: {command}")
        try:
            stdin, stdout, stderr = self._ssh_client.exec_command(
                command,
                get_pty=use_pty,
            )
        except (OSError, paramiko.SSHException) as error:
            logger.error(f"SSH command failed to start: {error}")
            return None

        stdin.close()
        stdout_text, stderr_text, exit_code = log_ssh_output(stdout, stderr)

        return SshCommandResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
        )

    def is_active(self) -> bool:
        """Return whether both the proxy and SSH session are active."""
        if self._iproxy_process is None or self._iproxy_process.poll() is not None:
            return False
        if self._ssh_client is None:
            return False

        transport = self._ssh_client.get_transport()
        if transport is None:
            return False
        return transport.is_active()

    def open_sftp(self) -> paramiko.SFTPClient | None:
        """Open an SFTP client over the active SSH connection."""
        if self._ssh_client is None or not self.is_active():
            logger.error("Cannot open SFTP because SSH is not connected.")
            return None

        try:
            sftp_client = self._ssh_client.open_sftp()
        except (OSError, paramiko.SSHException) as error:
            logger.error(f"Cannot open SFTP connection: {error}")
            return None

        logger.info("SFTP connection opened.")
        return sftp_client

    def close(self):
        """Close SSH first and then stop the owned iproxy process."""
        if self._ssh_client is not None:
            self._ssh_client.close()
            self._ssh_client = None
            logger.info("SSH connection closed.")

        if self._iproxy_process is None:
            return

        if self._iproxy_process.poll() is None:
            self._iproxy_process.terminate()
            try:
                self._iproxy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._iproxy_process.kill()
                self._iproxy_process.wait()

        self._iproxy_process = None
        logger.info("USB SSH tunnel closed.")

    def _start_iproxy(self, proxy_path: Path) -> bool:
        """Start one iproxy process for the selected device."""
        port_mapping = f"{self.local_port}:{SSH_DEVICE_PORT}"
        command = [
            str(proxy_path),
            "--udid",
            self.udid,
            "--source",
            SSH_HOST,
            port_mapping,
        ]
        logger.info(
            f"Starting USB SSH tunnel: {SSH_HOST}:{self.local_port} "
            f"-> device:{SSH_DEVICE_PORT}"
        )

        try:
            self._iproxy_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            logger.error(f"Cannot start iproxy: {error}")
            return False
        return True

    def _wait_for_tunnel(self) -> bool:
        """Wait until iproxy accepts local connections or exits."""
        deadline = time.monotonic() + SSH_CONNECT_TIMEOUT_SECONDS

        while time.monotonic() < deadline:
            if self._iproxy_process is None:
                return False

            if self._iproxy_process.poll() is not None:
                proxy_output = self._iproxy_process.stdout
                if proxy_output is not None:
                    output_text = proxy_output.read().strip()
                    if output_text:
                        logger.error(f"iproxy output: {output_text}")
                logger.error("iproxy exited before the SSH tunnel became ready.")
                return False

            if _is_local_port_open(self.local_port):
                logger.info("USB SSH tunnel is ready.")
                return True

            time.sleep(0.1)

        logger.error("Timed out while waiting for the USB SSH tunnel.")
        return False


def _is_local_port_open(local_port: int) -> bool:
    """Return whether a local TCP port currently accepts connections."""
    try:
        with socket.create_connection(
            (SSH_HOST, local_port),
            timeout=0.2,
        ):
            return True
    except OSError:
        return False
