"""Queries to match against contacts"""

import abc
from typing import List, Union


class Query(metaclass=abc.ABCMeta):

    """A query to match against strings, lists of strings and CarddavObjects"""

    @abc.abstractmethod
    def match(self, thing: Union[str, List[str]]) -> bool:
        """Match the self query against the given thing"""


class AnyQuery(Query):

    def match(self, thing: Union[str, List[str]]) -> bool:
        return True


class TermQuery(Query):

    def __init__(self, term: str) -> None:
        self._term = term.lower()

    def match(self, thing: Union[str, List[str]]) -> bool:
        if isinstance(thing, str):
            return self._term in thing.lower()
        return any(self.match(t) for t in thing)


class AndQuery(Query):

    def __init__(self, first: Query, second: Query, *queries: Query) -> None:
        self._queries = (first, second, *queries)

    def match(self, thing: Union[str, List[str]]) -> bool:
        return all(q.match(thing) for q in self._queries)


class OrQuery(Query):

    def __init__(self, first: Query, second: Query, *queries: Query) -> None:
        self._queries = (first, second, *queries)

    def match(self, thing: Union[str, List[str]]) -> bool:
        return any(q.match(thing) for q in self._queries)
