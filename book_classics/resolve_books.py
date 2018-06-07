"""
Disambiguate the book names
"""

from typing import List
import os
import goodreads
from collections import namedtuple
from log_utils import setup_logging
import logging


def get_filenames() -> List[str]:
    dir = "data/raw-picks"
    fnames = []
    for fname in os.listdir(dir):
        if fname.endswith(".txt"):
            fnames.append(os.path.join(dir, fname))
    return fnames


def get_name_from_filename(fname: str) -> str:
    return os.path.splitext(os.path.basename(fname))[0].replace("_", " ")


GoodreadsArgs = namedtuple("GoodreadsArgs", [
    "quiet",
    "person",
    "book_file",
    "always_use_cache",
])


if __name__ == "__main__":
    setup_logging(verbose=True)
    fnames = get_filenames()
    for fname in fnames:
        person_name = get_name_from_filename(fname)
        logging.debug("Resolving picks for %s", person_name)
        args = GoodreadsArgs(
            quiet=False,
            person=person_name,
            book_file=fname,
            always_use_cache=True,
        )
        try:
            goodreads.main(args)
        except goodreads.NoCacheOverrideException:
            logging.debug("Not overriding choices for %s", person_name)
