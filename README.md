# About

## Getting Started

First, create raw files for all the people in `data/raw-picks/$name.txt` with one line per book.
To disambiguate books you can add an author last name or similar to the end of the title.
The scripts will search goodreads with that search string to disambiguate.

Run `python book_classics/resolve_books.py` and resolve all outstanding book choices.
The resolved choices will be written to `data/resolved-picks/$name.txt`

## Analysis

To get the 'basic_bitch_score' associated with all people, run `python book_classics/basic_bitch_score.py`.
For a full description of what it does, read the docstring at the top of that file.