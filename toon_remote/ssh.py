"""SSH access to a rooted Toon.

The Toon runs an ancient Dropbear (kernel 2.6.36, 2015 firmware) that only
offers legacy crypto, so we explicitly connect with password auth and let
paramiko negotiate the old algorithms. Default login is root / toon.

    from toon.ssh import ToonSSH
    with ToonSSH() as t:              # host/password come from config
        print(t.run("cat /qmf/qmf_release"))
"""

from __future__ import annotations

import paramiko

from . import config


class ToonSSH:
    def __init__(
        self,
        host: str | None = None,
        *,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 15.0,
        compress: bool = False,
    ) -> None:
        self.host = config.require_host(host)
        self.username = config.get_username(username)
        self.password = config.get_password(password)
        self.timeout = timeout
        self.compress = compress
        self._transport: paramiko.Transport | None = None

    def connect(self) -> "ToonSSH":
        transport = paramiko.Transport((self.host, 22))
        # Re-enable the legacy SHA-1 host key the Toon's old Dropbear offers;
        # modern paramiko drops ssh-rsa from its defaults.
        opts = transport.get_security_options()
        opts.key_types = tuple(dict.fromkeys(("ssh-rsa",) + tuple(opts.key_types)))
        transport.banner_timeout = self.timeout
        if self.compress:
            transport.use_compression(True)  # zlib crushes the mostly-black fb
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

    def read_binary(self, command: str, *, timeout: float = 60.0) -> bytes:
        """Run a command and return its stdout as raw bytes (for binary data)."""
        assert self._transport is not None, "call connect() first"
        chan = self._transport.open_session(timeout=timeout)
        chan.settimeout(timeout)
        chan.exec_command(command)
        chunks = []
        while True:
            data = chan.recv(65536)
            if not data:
                break
            chunks.append(data)
        chan.recv_exit_status()
        return b"".join(chunks)

    def write_stdin(self, command: str, data: bytes, *, timeout: float = 15.0) -> None:
        """Run a command and feed `data` to its stdin (e.g. cat > /dev/...)."""
        assert self._transport is not None, "call connect() first"
        chan = self._transport.open_session(timeout=timeout)
        chan.settimeout(timeout)
        chan.exec_command(command)
        chan.sendall(data)
        chan.shutdown_write()
        chan.recv_exit_status()

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    def __enter__(self) -> "ToonSSH":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()
