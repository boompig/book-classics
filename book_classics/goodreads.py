from __future__ import print_function

import csv
import logging
import os
import pickle
import xml.etree.ElementTree as ET
from argparse import ArgumentParser
# from pprint import pprint

import requests
from Levenshtein import distance
from typing import Iterator, List, Optional

from book import GoodreadsBook
from goodreads_secrets import key
from log_utils import setup_logging


GOODREADS_CACHE_DIR = "data/goodreads-cache"
RESOLVED_PICKS_DIR = "data/resolved-picks"


def search_for_book(title: str) -> ET.Element:
    """:return ET.Element"""
    if not os.path.exists(GOODREADS_CACHE_DIR):
        os.makedirs(GOODREADS_CACHE_DIR)
    goodreads_cache_fname = os.path.join(
        GOODREADS_CACHE_DIR,
        "{}.xml".format(title.lower().replace(" ", "_"))
    )
    # check the cache
    if os.path.exists(goodreads_cache_fname):
        logging.debug("Hit the Goodreads API XML cache")
        with open(goodreads_cache_fname) as fp:
            contents = fp.read()
            return ET.fromstring(contents)
    else:
        logging.debug("Cache miss, hitting the goodreads API")
        r = requests.get("https://www.goodreads.com/search/index.xml", data={
            "key": key,
            "search": "title",
            "page": "1",
            "q": title
        })
        assert r.status_code == 200
        response = r.text
        root = ET.fromstring(response)
        # write the data
        tree = ET.ElementTree(root)
        tree.write(goodreads_cache_fname)
        return root


def suggest_book_from_results(searched_title: str, root) -> List[GoodreadsBook]:
    """
    :param recommendation:          ET.Element
    """
    relevant_books = []
    for work_elem in root.find("search").find("results").findall("work"):
        # parse the element to find info
        result_title = work_elem.find("best_book").find("title").text
        author = work_elem.find("best_book").find("author").find("name").text
        num_ratings = int(work_elem.find("ratings_count").text)
        try:
            pub_year = int(work_elem.find("original_publication_year").text)
        except TypeError:
            # this happens because source element might be null
            pub_year = None
        str_distance = distance(searched_title.lower(), result_title.lower())
        # heuristic
        if str_distance < 50 and num_ratings > 100:
            # print(ET.dump(work_elem))
            relevant_books.append(GoodreadsBook(
                title= result_title,
                author= author,
                num_ratings= num_ratings,
                original_publication_year= pub_year,
                str_distance= str_distance,
                node= work_elem,
            ))
        else:
            # logging.debug("Skipping title")
            continue

    logging.debug("Before filtering step, found {} relevant results".format(
        len(relevant_books)))
    # filter out those that don't have that many ratings compared to leading candidates
    max_num_ratings = 0
    for b in relevant_books:
        if b.num_ratings > max_num_ratings:
            max_num_ratings = b.num_ratings
    relevant_books = [b for b in relevant_books
                      if b.num_ratings >= (max_num_ratings / 100)]
    logging.debug("Found %d relevant results", len(relevant_books))
    return relevant_books


def get_books_from_file(fname: str) -> Iterator[str]:
    logging.debug("Loading books from file %s", fname)
    with open(fname) as fp:
        for line in fp:
            line = line.strip()
            if line == "":
                continue
            yield line


def get_obviously_correct_book(relevant_books: List[GoodreadsBook]) -> Optional[GoodreadsBook]:
    """
    A book is obviously correct iff
    - has >= 100x more reviews than any other book; AND
    - string similarity < 10
    """
    max_num_ratings = 0
    target = None
    for b in relevant_books:
        if b.num_ratings > max_num_ratings:
            max_num_ratings = b.num_ratings
            target = b
    for b in relevant_books:
        if b == target:
            continue
        if b.num_ratings * 100 > target.num_ratings:
            return None
    # here we have a runaway winner
    # so just need to check that it has a good string similarity
    if target.str_distance < 10:
        return target
    else:
        return None


def resolve_via_human(query: str, relevant_books: List[GoodreadsBook]) -> GoodreadsBook:
    print("Found {} good results for '{}'".format(
        len(relevant_books),
        query
    ))
    for i, book in enumerate(relevant_books):
        print("{}. {title} (by {author})".format(
            i + 1, title=book.title, author=book.author
        ))
    answer = ""
    while answer == "" or not answer.isdigit() or answer == "0":
        answer = input("Which is the right one? ")
    return relevant_books[int(answer) - 1]


def save_chosen_books(person: str, chosen_books: List[GoodreadsBook]) -> None:
    fname = get_output_fname(person)
    with open(fname, "w") as fp:
        writer = csv.writer(fp, quotechar='"', delimiter=',')
        writer.writerow(["title", "author", "year"])
        for book in chosen_books:
            writer.writerow([
                book.title,
                book.author,
                book.original_publication_year
            ])
    logging.info("Saved choices in %s", fname)


def get_output_fname(person: str) -> str:
    if not os.path.exists(RESOLVED_PICKS_DIR):
        os.makedirs(RESOLVED_PICKS_DIR)
    fname = "{dir}/{person}.csv".format(
        dir=RESOLVED_PICKS_DIR,
        person=person.lower().replace(" ", "_")
    )
    return fname


def confirm(msg: str) -> bool:
    user_in = ""
    while user_in not in ["y", "n"]:
        print(msg)
        user_in = input("y/n > ")
    return user_in == "y"


class GoodreadsResolutionCache:
    FNAME = "data/goodreads-resolution-cache.dat"

    def __init__(self, cache: dict = {}, is_dirty: bool = True) -> None:
        """
        :param cache:       Can start with a pre-populated cache
        :param is_dirty:    Set to true by default.
                            If false, will not write to disk unless changes are made.
        """
        self.cache = cache
        self.is_dirty = is_dirty

    @staticmethod
    def load() -> "GoodreadsResolutionCache":
        with open(GoodreadsResolutionCache.FNAME, "rb") as fp:
            cache = pickle.load(fp)
            return GoodreadsResolutionCache(cache, is_dirty=False)

    def save(self) -> None:
        if self.is_dirty:
            logging.debug("Saved Goodreads resolution cache to disk")
            with open(GoodreadsResolutionCache.FNAME, "wb") as fp:
                pickle.dump(self.cache, fp)
            self.is_dirty = False

    def __contains__(self, search_str: str) -> bool:
        return search_str in self.cache

    def save_title_resolution(self, search_str: str, goodreads_id: int, book: GoodreadsBook) -> None:
        if search_str not in self.cache:
            self.cache[search_str] = {}
        self.cache[search_str]["goodreads_id"] = goodreads_id
        self.cache[search_str]["book"] = book
        self.is_dirty = True

    def get_book(self, search_str: str) -> GoodreadsBook:
        return self.cache[search_str]["book"]


def main(args):
    setup_logging(not args.quiet)
    chosen_books = []
    output_fname = get_output_fname(args.person)
    try:
        goodreads_resolution_cache = GoodreadsResolutionCache.load()
    except IOError:
        goodreads_resolution_cache = GoodreadsResolutionCache()
        goodreads_resolution_cache.save()
    if os.path.exists(output_fname):
        print("Resolved picks file already exists for {}.".format(args.person))
        if not confirm("Overwrite?"):
            raise SystemExit()
    for book in get_books_from_file(args.book_file):
        # the 'book' is actually a query
        if book in goodreads_resolution_cache:
            logging.info("Found '%s' in Goodreads resolution cache", book)
            candidate = goodreads_resolution_cache.get_book(book)
            chosen_books.append(candidate)
        else:
            logging.info("Searching for '%s' on goodreads for person %s...", book, args.person)
            root = search_for_book(book)
            relevant_books = suggest_book_from_results(book, root)
            if relevant_books == []:
                print("WARNING: no results for query '%s'", book)
                print("Possible typo?")
                if confirm("Skip (no exits the program)"):
                    continue
                else:
                    raise SystemExit()
                # basically not skipping will write
            elif len(relevant_books) == 1:
                candidate = relevant_books[0]
            else:
                candidate = get_obviously_correct_book(relevant_books)
                if candidate:
                    logging.debug("We have a winner!")
                else:
                    logging.debug("No obviously correct book")
                    candidate = resolve_via_human(book, relevant_books)
            goodreads_resolution_cache.save_title_resolution(book, candidate.get_goodreads_id(), candidate)
            goodreads_resolution_cache.save()
            chosen_books.append(candidate)

    # create the candidates pool
    save_chosen_books(args.person, chosen_books)


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--person", required=True,
                        help="The person whose book picks these are")
    parser.add_argument("-f", "--book-file", required=True,
                        help="File which contains names of books, one per line")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()
    main(args)
