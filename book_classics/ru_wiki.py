"""
This is an interface to query Russian-language wikipedia

I have found the following:

- wikipedia's python bindings don't support non-English pages
- while search works for Russian-language wikipedia, there is no support for using the API to actually get the page content
"""

import logging
import os
import pickle
import urllib
import uuid
from argparse import ArgumentParser
from pprint import pprint

import Levenshtein
import requests
import wptools
from bs4 import BeautifulSoup
from typing import Optional

from book import Book
from log_utils import setup_logging

# this is the query URL
base_url = "https://ru.wikipedia.org/w/api.php"
# base_url = "https://en.wikipedia.org/w/api.php"
# this is the page info URL
base_url_info_api = "https://ru.wikipedia.org/api/rest_v1"
# base_url_info = "https://en.wikipedia.org/api/rest_v1"
base_url_html = "https://ru.wikipedia.org/wiki"


def foo():
    pass
    # r = requests.get(base_url_info + "/page/html/{}".format(
        # urllib.parse.quote_plus(page_title.replace(" ", "_"))
    # ))

def search_wikipedia_curl(search: str):
    # perform a search to find the article
    r = requests.get(base_url, params={
        "format": "json",
        "action": "query",
        "titles": search
    })
    data = r.json()
    return data


def get_page_title(data: dict) -> str:
    page_title = None
    for page_id, page in data["query"]["pages"].items():
        page_title = page["title"]
        break
    assert page_title is not None
    return page_title


def search_for_html_page(page_title: str) -> str:
    r = requests.get("{}/{}".format(
        base_url_html,
        urllib.parse.quote_plus(page_title.replace(" ", "_"))
    ))
    return r.text


def save_html(html: str, fname: Optional[str] = None) -> str:
    if fname is None:
        fname = "data/wikipedia-cache/{}.html".format(str(uuid.uuid4()))
    if not os.path.exists("data/wikipedia-cache"):
        os.mkdir("data/wikipedia-cache")
    with open(fname, "w") as fp:
        fp.write(html)
    return fname


def read_html(fname: str) -> str:
    with open(fname, "r") as fp:
        return fp.read()


def get_col_text(col) -> str:
    col_text = (col.text.translate({
            ord("\t"): None,
            ord("\n"): None,
            ord("'"): None
        })
        .replace("\\n", "")
        # .replace("'", "")
        # .replace("\t", "")
        # .replace("\n", "")
        .strip())
    return col_text


def get_infobox_from_html(html: str) -> dict:
    assert isinstance(html, str)
    soup = BeautifulSoup(html, "lxml")
    assert soup is not None
    table = soup.find_all("table", {"class": "infobox"})[0]
    d = {}
    for i, row in enumerate(table.find_all("tr")):
        header = row.find("th")
        if header:
            header_text = header.text.strip().rstrip(":")
            col = row.find("td")
            d[header_text] = get_col_text(col)
        elif i == 0:
            col = row.find("td")
            d["title"] = get_col_text(col)
        else:
            continue
    return d


def book_from_infobox(infobox: dict, search_str: str) -> Book:
    str_distance = Levenshtein.distance(infobox["title"], search_str)
    return Book(
        title=infobox["title"],
        author=infobox["Автор"],
        original_publication_year=infobox["Выпуск"],
        str_distance=str_distance
    )


def search_wikipedia_helper(search: str):
    """Seach using the wikipedia python bindings"""
    parsed_page = wptools.page(search).get_query()
    pprint(parsed_page)
    # infobox = parsed_page.infobox
    # pprint(infobox)


class WikiCache:
    FNAME = "data/wiki-cache.dat"

    def __init__(self):
        self.cache = {}

    @staticmethod
    def load() -> "WikiCache":
        with open(WikiCache.FNAME, "rb") as fp:
            return pickle.load(fp)

    def save(self) -> None:
        with open(WikiCache.FNAME, "wb") as fp:
            pickle.dump(self, fp)

    def __contains__(self, search_str: str) -> bool:
        return search_str in self.cache

    def set_page_title(self, search_str: str, page_title: str) -> None:
        if search_str not in self.cache:
            self.cache[search_str] = {}
        self.cache[search_str]["page_title"] = page_title

    def set_html_filename(self, search_str: str, fname: str) -> None:
        if search_str not in self.cache:
            self.cache[search_str] = {}
        self.cache[search_str]["html_file"] = fname

    def get_html_filename(self, search_str: str) -> str:
        return self.cache[search_str]["html_file"]



if __name__ == "__main__":
    setup_logging()
    parser = ArgumentParser()
    parser.add_argument("search_str")
    args = parser.parse_args()
    try:
        wiki_cache = WikiCache.load()
    except IOError:
        wiki_cache = WikiCache()
    search_str = args.search_str
    if search_str in wiki_cache:
        logging.debug("Loading page from cache...")
        fname = wiki_cache.get_html_filename(search_str)
        logging.debug("Reading HTML from file '%s'..." % fname)
        html = read_html(fname)
    else:
        data = search_wikipedia_curl(search_str)
        page_title = get_page_title(data)
        wiki_cache.set_page_title(search_str, page_title)
        html = search_for_html_page(page_title)
        fname = save_html(html)
        wiki_cache.set_html_filename(search_str, fname)
        wiki_cache.save()
    assert isinstance(html, str)
    infobox = get_infobox_from_html(html)
    book = book_from_infobox(infobox, search_str)
    print(book)

