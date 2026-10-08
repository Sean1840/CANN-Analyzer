import logging

LOG_LEVEL = "INFO"


def configure():
    logging.basicConfig(level=LOG_LEVEL)


# @expect-func: (none)
logging.warning("module imported without explicit configuration")
