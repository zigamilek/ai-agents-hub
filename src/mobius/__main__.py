from __future__ import annotations

import argparse

import uvicorn

from mobius import __version__
from mobius.config import load_config
from mobius.onboarding import run_onboarding


def main() -> None:
    parser = argparse.ArgumentParser(prog="mobius")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run API server")
    serve_parser.add_argument("--config", dest="config_path", default=None)
    serve_parser.add_argument("--host", default=None)
    serve_parser.add_argument("--port", type=int, default=None)

    onboard_parser = subparsers.add_parser(
        "onboard", help="Interactive setup for env/config"
    )
    onboard_parser.add_argument("--config", dest="config_path", default=None)
    onboard_parser.add_argument("--env-file", dest="env_file", default=None)

    args = parser.parse_args()
    command = args.command or "serve"

    if command == "onboard":
        run_onboarding(
            config_path=getattr(args, "config_path", None),
            env_file=getattr(args, "env_file", None),
        )
        return

    # When no subcommand is passed, argparse does not populate serve-only fields
    # like host/port. Fall back to config values in that case.
    config = load_config(getattr(args, "config_path", None))
    host = getattr(args, "host", None) or config.server.host
    port = getattr(args, "port", None) or config.server.port
    uvicorn.run(
        "mobius.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
