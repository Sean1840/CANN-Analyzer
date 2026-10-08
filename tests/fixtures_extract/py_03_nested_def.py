import logging


def outer(flag):
    def inner(value):
        # @expect-func: inner
        logging.warning("inner saw %s", value)
        return value

    # @expect-func: outer
    logging.info("outer flag=%s", flag)
    return inner(flag)
