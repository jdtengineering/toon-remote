"""PyInstaller entry point for the toon-remote GUI binary."""

from toon_remote.app import main

if __name__ == "__main__":
    raise SystemExit(main())
