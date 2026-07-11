"""SSH access to a rooted Toon.

The Toon runs an ancient Dropbear (kernel 2.6.36, 2015 firmware) that only
offers legacy crypto, so we explicitly connect with password auth and let
paramiko negotiate the old algorithms. Default login is root / toon.

    from toon.ssh import ToonSSH
    with ToonSSH("192.168.1.178") as t:
        print(t.run("cat /qmf/qmf_release"))
"""

from __future__ import annotations

import os

import paramiko


class ToonSSH:
    def __init__(
        self,
        host: str = os.environ.get("TOON_HOST", "192.168.1.178"),
        *,
        username: str = "root",
        password: str = os.environ.get("TOON_SSH_PASS", "toon"),
        timeout: float = 15.0,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self._transport: paramiko.Transport | None = None

    def connect(self) -> "ToonSSH":
        transport = paramiko.Transport((self.host, 22))
        # Re-enable the legacy SHA-1 host key the Toon's old Dropbear offers;
        # modern paramiko drops ssh-rsa from its defaults.
        opts = transport.get_security_options()
        opts.key_types = tuple(dict.fromkeys(("ssh-rsa",) + tuple(opts.key_types)))
        transport.banner_timeout = self.timeout
        transport.connect(username=self.username, password=self.password)
        self._transport = transport
        return self

    def run(self, command: str, *, timeout: float = 30.0) -> str:
        """Run a command and return stdout+stderr combined."""
        assert self._transport is not None, "call connect() first"
        chan = self._transport.open_session(timeout=timeout)
        chan.settimeout(timeout)
        chan.exec_command(command)
        out = chan.makefile("rb").read()
        err = chan.makefile_stderr("rb").read()
        chan.recv_exit_status()
        return (out + err).decode("utf-8", "replace").rstrip("\n")

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def __enter__(self) -> "ToonSSH":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()
