import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


class Parser:
    @classmethod
    @lru_cache(maxsize=None)
    def build(cls, name):
        # @expect-func: build
        logger.error("build failed for %s", name)
        return cls()
