import logging


def process(items):
    # @expect-func: process
    logging.error(
        "process failed for %d items, first=%s",
        len(items),
        items[0] if items else None,
    )


def next_step():
    # @expect-func: next_step
    logging.info("next step")
