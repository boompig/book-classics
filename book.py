class Book:
    def __init__(self, title: str, author: str, original_publication_year: int,
            str_distance: int) -> None:
        self.title = title
        self.author = author
        self.original_publication_year = original_publication_year
        self.str_distance = str_distance

    def __str__(self) -> str:
        return "{} by {}, published in {}".format(self.title, self.author, self.original_publication_year)



class GoodreadsBook(Book):
    def __init__(self, title: str, author: str, original_publication_year,
            str_distance: int,
            num_ratings: int, 
            node) -> None: 
        super().__init__(title, author, original_publication_year, str_distance)
        self.num_ratings = num_ratings
        self.node=node
