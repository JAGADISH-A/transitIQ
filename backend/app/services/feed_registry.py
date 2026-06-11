"""Registry for discovering available GTFS feed directories."""

import logging
from pathlib import Path
from typing import List


class FeedRegistry:
    """Maintain and discover GTFS feed folders under the backend data directory."""

    def __init__(self, data_root: str = "../data") -> None:
        """Initialize the feed registry.

        Args:
            data_root: Path to the data directory containing feed folders.
        """
        self.logger = logging.getLogger(__name__)
        self.data_root = Path(data_root).expanduser().resolve()

    def discover_feeds(self) -> List[str]:
        """Return the names of all GTFS feed directories under the data root.

        Returns:
            A list of feed directory names sorted alphabetically.
        """
        try:
            if not self.data_root.exists() or not self.data_root.is_dir():
                self.logger.warning("Data directory not found: %s", self.data_root)
                return []

            feeds = [path.name for path in self.data_root.iterdir() if path.is_dir()]
            feeds = sorted(feeds)
            self.logger.info("Discovered %d GTFS feed(s) in %s", len(feeds), self.data_root)
            return feeds
        except Exception as exc:  # pragma: no cover - defensive error handling
            message = f"Failed to discover GTFS feeds: {exc}"
            self.logger.exception(message)
            return []

    def get_feed_path(self, feed_name: str) -> Path:
        """Return the absolute path to a named GTFS feed directory.

        Args:
            feed_name: The feed folder name to resolve.

        Returns:
            The absolute path to the feed directory.
        """
        return (self.data_root / feed_name).resolve()

    def feed_exists(self, feed_name: str) -> bool:
        """Return whether a feed directory exists.

        Args:
            feed_name: The feed folder name to check.

        Returns:
            True if the feed exists, otherwise False.
        """
        return self.get_feed_path(feed_name).exists() and self.get_feed_path(feed_name).is_dir()
