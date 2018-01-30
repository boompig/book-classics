from __future__ import print_function

# from pprint import pprint
import csv
import logging
import os
import xml.etree.ElementTree as ET
from argparse import ArgumentParser

import coloredlogs
import requests
from Levenshtein import distance
from typing import Iterator, List, Optional

from goodreads_secrets import key
from book import GoodreadsBook
from log_utils import setup_logging

coloredlogs.install()


def search_for_book(title: str):
    """:return ET.Element"""
    if not os.path.exists("data"):
        os.mkdir("data")
    if not os.path.exists("data/goodreads-cache"):
        os.mkdir("data/goodreads-cache")
    goodreads_cache_fname = "data/goodreads-cache/{}.xml".format(
        title.lower().replace(" ", "_")
    )
    # check the cache
    if os.path.exists(goodreads_cache_fname):
        logging.debug("Hit the cache")
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
            relevant_books.append(GoodreadsBook(**{
                "title": result_title,
                "author": author,
                "num_ratings": num_ratings,
                "original_publication_year": pub_year,
                "str_distance": str_distance,
                "node": work_elem
            }))
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
    logging.debug("Found %d relevant results" % len(relevant_books))
    return relevant_books


def get_books_from_file(fname: str) -> Iterator[str]:
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
    logging.info("Saved choices in %s" % fname)


def get_output_fname(person: str) -> str:
    dir = "data/resolved-picks"
    if not os.path.exists(dir):
        os.mkdir(dir)
    fname = "{dir}/{person}.csv".format(
        dir=dir,
        person=person.lower().replace(" ", "_")
    )
    return fname


def confirm(msg: str) -> bool:
    user_in = ""
    while user_in not in ["y", "n"]:
        print(msg)
        user_in = input("y/n > ")
    return user_in == "y"


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--person", required=True,
                        help="The person whose book picks these are")
    parser.add_argument("-f", "--book-file", required=True,
                        help="File which contains names of books, one per line")
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args()
    setup_logging(not args.quiet)
    chosen_books = []
    output_fname = get_output_fname(args.person)
    if os.path.exists(output_fname):
        print("Resolved picks file already exists for {}".format(args.person))
        if not confirm("Continue?"):
            raise SystemExit()
    for book in get_books_from_file(args.book_file):
        logging.info("Searching for '%s' on goodreads..." % book)
        root = search_for_book(book)
        relevant_books = suggest_book_from_results(book, root)
        if relevant_books == []:
            print("WARNING: no results for query '%s'" % book)
            print("Possible typo?")
            if not confirm("Skip (no exits the program)"):
                raise SystemExit()
            # basically not skipping will write
        elif len(relevant_books) == 1:
            candidate = relevant_books[0]
        else:
            candidate = get_obviously_correct_book(relevant_books)
            if candidate:
                logging.debug("We have a winner!")
                # pprint(candidate)
            else:
                logging.debug("No obviously correct book")
                candidate = resolve_via_human(book, relevant_books)
                # print(candidate)
            chosen_books.append(candidate)
    # create the candidates pool
    save_chosen_books(args.person, chosen_books)
