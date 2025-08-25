import argparse
import logging
import pathlib

from datetime import datetime, UTC

from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("src/templates"),
    autoescape=select_autoescape(['html', 'xml'])
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    print("Starting generation")
    parser = argparse.ArgumentParser()
    src_path = pathlib.Path(__name__)
    time_stamp = datetime.now(UTC)
    logger.info(f"Staring Blue Core Graph Toolkit static site {time_stamp}")
    index_template = env.get_template("index.html")
    with (src_path.parent / "index.html").open("w+") as fo:
        fo.write(index_template.render(timestamp=time_stamp))
    total_time = (datetime.now(UTC) - time_stamp).seconds
    logger.info(f"Total time {total_time}")

