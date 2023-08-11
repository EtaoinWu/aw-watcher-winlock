from aw_core.log import setup_logging

from aw_watcher_winlock.lock import LockWatcher
from aw_watcher_winlock.config import parse_args


def main() -> None:
    args = parse_args()

    # Set up logging
    setup_logging(
        "aw-watcher-winlock",
        testing=args.testing,
        verbose=args.verbose,
        log_stderr=True,
        log_file=True,
    )

    # Start watcher
    watcher = LockWatcher(args, testing=args.testing)
    watcher.run()


if __name__ == "__main__":
    main()