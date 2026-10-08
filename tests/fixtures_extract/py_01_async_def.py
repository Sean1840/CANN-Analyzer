import logging


async def collect_async(path, out):
    # @expect-func: collect_async
    logging.info("collecting profiling data from %s", path)
    return out
