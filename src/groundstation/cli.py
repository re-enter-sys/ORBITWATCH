"""
Command-line interface for OrbitWatch.
"""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__
from .config import ensure_data_directories, get_default_config


LOGGER = logging.getLogger("orbitwatch")


def configure_logging(level: str) -> None:
    """Configure application-wide logging."""
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the OrbitWatch command-line parser."""
    parser = argparse.ArgumentParser(
        prog="orbitwatch",
        description=(
            "OrbitWatch - Linux Satellite Ground Station for "
            "SDR reception, satellite tracking, and telemetry."
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"OrbitWatch {__version__}",
    )

    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        default="INFO",
        help="Set the application logging level.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="commands",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Display ground station status.",
    )
    status_parser.set_defaults(handler=handle_status)

    init_parser = subparsers.add_parser(
        "init",
        help="Initialize required OrbitWatch data directories.",
    )
    init_parser.set_defaults(handler=handle_init)

    config_parser = subparsers.add_parser(
        "config",
        help="Display the active ground station configuration.",
    )
    config_parser.set_defaults(handler=handle_config)

    dashboard_parser = subparsers.add_parser(
        "dashboard",
        help="Launch the OrbitWatch Mission Control dashboard.",
    )
    dashboard_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Dashboard bind address.",
    )
    dashboard_parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Dashboard port.",
    )
    dashboard_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable Flask debug mode.",
    )
    dashboard_parser.set_defaults(handler=handle_dashboard)

    return parser


def handle_status(_args: argparse.Namespace) -> int:
    """Display basic ground station status."""
    config = get_default_config()

    print("OrbitWatch Ground Station")
    print("--------------------------")
    print(f"Version:        {config.version}")
    print("Status:         READY")
    print(f"Data directory: {config.data_dir}")
    print(f"SDR frequency:  {config.sdr.center_frequency_hz:.0f} Hz")
    print(f"Sample rate:    {config.sdr.sample_rate_hz:.0f} Hz")

    return 0


def handle_init(_args: argparse.Namespace) -> int:
    """Initialize OrbitWatch data directories."""
    config = get_default_config()
    ensure_data_directories(config)

    print("OrbitWatch data directories initialized.")
    print(f"Data directory: {config.data_dir}")

    return 0


def handle_config(_args: argparse.Namespace) -> int:
    """Display the active configuration."""
    config = get_default_config()

    print("OrbitWatch Configuration")
    print("------------------------")
    print(f"Name:             {config.name}")
    print(f"Version:          {config.version}")
    print(f"Timezone:         {config.timezone}")
    print(f"Log level:        {config.log_level}")
    print(f"Data directory:   {config.data_dir}")
    print(f"Satellite data:   {config.satellite_data_dir}")
    print(f"Sample data:      {config.sample_data_dir}")
    print(f"Telemetry data:   {config.telemetry_data_dir}")
    print(f"Recordings:       {config.recording_data_dir}")
    print()
    print("SDR")
    print("---")
    print(f"Device index:     {config.sdr.device_index}")
    print(f"Frequency:        {config.sdr.center_frequency_hz:.0f} Hz")
    print(f"Sample rate:      {config.sdr.sample_rate_hz:.0f} Hz")
    print(f"Gain:             {config.sdr.gain}")
    print(f"PPM correction:   {config.sdr.ppm_correction}")

    return 0


def handle_dashboard(args: argparse.Namespace) -> int:
    """Launch OrbitWatch Mission Control."""
    from .dashboard.app import run_dashboard

    print()
    print("OrbitWatch Mission Control")
    print("==========================")
    print(f"Dashboard: http://{args.host}:{args.port}")
    print("Mode:      READ-ONLY")
    print("RF TX:     DISABLED")
    print()
    print("Press Ctrl+C to stop the dashboard.")
    print()

    run_dashboard(
        host=args.host,
        port=args.port,
        debug=args.debug,
    )

    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the OrbitWatch CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    configure_logging(args.log_level)

    if not hasattr(args, "handler"):
        parser.print_help()
        return 0

    try:
        return args.handler(args)
    except KeyboardInterrupt:
        LOGGER.info("OrbitWatch interrupted by user.")
        return 130
    except Exception as exc:
        LOGGER.error("OrbitWatch error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
