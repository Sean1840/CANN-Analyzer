import logging


class DataPreparationParser:
    def __init__(self, result_dir):
        # @expect-func: __init__
        logging.info("parser created for %s", result_dir)
        self.result_dir = result_dir

    def _parse_one(self, name):
        try:
            # @expect-func: _parse_one
            logging.debug("parsing %s", name)
        except OSError as exc:
            # @expect-func: _parse_one
            logging.error("parse failed: %s", exc)
            return None
        return name

    if True:
        # @expect-func: (none)
        logging.warning("class body call has no enclosing function")
