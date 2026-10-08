from __future__ import annotations

import sys

from groundstation.cli import main as cli_main


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "demo":
        from groundstation.runtime import set_idle, set_replay
        from groundstation.simulation.mission import main as demo_main

        set_replay()

        try:
            return demo_main(sys.argv[2:])
        finally:
            # A completed or interrupted replay must never leave
            # the dashboard permanently showing REPLAY.
            set_idle()

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
