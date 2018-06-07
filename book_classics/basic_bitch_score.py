"""
How 'original' your choices are with respect to other choices in the database.
"""

from typing import List, Dict
from csv import DictReader
import os
from log_utils import setup_logging
import logging
import Levenshtein


def basic_bitch_scores(cohort: List[str], book: Dict[str, List[str]]):
    raise NotImplementedError()


def get_resolved_book_fname_for_person(person):
    return "data/resolved-picks/{}.csv".format(person.replace(" ", "_"))


def read_resolved_books_for_person(person: str):
    fname = get_resolved_book_fname_for_person(person)
    with open(fname) as fp:
        reader = DictReader(fp)
        lines = [line for line in reader]
    return lines


def get_all_people() -> List[str]:
    for fname in os.listdir("data/resolved-picks"):
        name = os.path.splitext(fname)[0].replace("_", " ").title()
        yield name


def get_book_id(book: dict) -> str:
    return "title={title},author={author},year={year}".format(
        title=book["title"], author=book["author"], year=book["year"])


def get_basic_bitch_score_for_person(person: str, people_to_books_map: Dict[str, List[str]],
                                     books_to_people_map: Dict[str, List[str]]) -> float:
    someone_else_selected_count = 0
    your_count = 0
    for book_id in people_to_books_map[person]:
        if len(books_to_people_map[book_id]) > 1:
            someone_else_selected_count += 1
        else:
            logging.debug("Found unique book for %s: %s", person, book_id)
        your_count += 1
    assert your_count > 0
    return (someone_else_selected_count * 1.0) / your_count


def get_basic_bitch_scores(all_people: List[str]) -> Dict[str, float]:
    # map from books to people that chose that book
    all_books = {}
    # map from 'book_id' to full information about that book
    book_map = {}
    # map from person's name to list of books they selected (book IDs)
    person_to_books = {}
    for person in all_people:
        books = read_resolved_books_for_person(person)
        person_to_books[person] = []
        for book in books:
            book_id = get_book_id(book)
            all_books.setdefault(book_id, [])
            all_books[book_id].append(person)
            book_map[book_id] = book
            person_to_books[person].append(book_id)
    # goal: map of person to basic bitch score
    # basic bitch score = (# books you selected that someone else also selected) / (# books you selected)
    scores = {}
    for person in all_people:
        score = get_basic_bitch_score_for_person(
            person,
            person_to_books,
            all_books
        )
        scores[person] = score
    return scores


def check_books_unique(all_books: List[dict]) -> bool:
    """Make sure that the books selected are actually unique and we don't have the same book under multiple names"""
    unique_flag = True
    all_titles = [book["title"] for book in all_books]
    for i, book1 in enumerate(all_titles):
        for j, book2 in enumerate(all_titles[i + 1:]):
            # get the distance between these books
            d = Levenshtein.distance(book1, book2)
            if d <= 5 and d < 0.5 * min(len(book1), len(book2)):
                # now check the author to see if they are similar or typo
                b1 = all_books[i]
                b2 = all_books[i + j + 1]
                author_d = Levenshtein.distance(b1["author"], b2["author"])
                if author_d <= 5:
                    print("Books '{}' and '{}' have Levenshtein distance {}".format(book1, book2, d))
                    unique_flag = False
                else:
                    logging.info("Books '{}' and '{}' have Levenshtein distance {}...".format(book1, book2, d))
                    logging.info("But they have different authors '{}' and '{}' with distance {}".format(
                        b1["author"], b2["author"], author_d))
    return unique_flag


def get_all_book_titles(all_people: List[str]) -> List[dict]:
    all_books = []
    s = set([])
    for person in all_people:
        books = read_resolved_books_for_person(person)
        book_ids = [get_book_id(book) for book in books]
        for book_id, book in zip(book_ids, books):
            if book_id not in s:
                all_books.append(book)
                s.add(book_id)
    return all_books


if __name__ == "__main__":
    setup_logging(verbose=False)
    # when None it means everyone
    cohort = None
    all_people = [person for person in get_all_people()]
    all_books = get_all_book_titles(all_people)
    are_unique = check_books_unique(all_books)
    if not are_unique:
        logging.error("Books not unique, stopping computation")
        raise SystemExit()
    scores = get_basic_bitch_scores(all_people)
    for person in sorted(scores, key=scores.get, reverse=True):
        score = scores[person]
        print("%s -> %.3f" % (person, score))
