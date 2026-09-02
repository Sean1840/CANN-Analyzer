import logging


class DataPreparationParser:
    FILE_NAME = "data_preparation_parser.py"

    def process(self, result_dir):
        logging.warning("No data preparation data, data list is empty!")
        logging.info(
            "%s process data finished, execute time is %.3f s",
            self.__class__.__name__,
            0.005,
        )
        logging.error("Analysis data in \"%s\" failed. Maybe the data is incomplete." % result_dir)
