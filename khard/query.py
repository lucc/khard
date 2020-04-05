"""Queries to match against contacts"""

import abc
from typing import List, Union


class Query(metaclass=abc.ABCMeta):

    """A query to match against strings, lists of strings and CarddavObjects"""

    @abc.abstractmethod
    def match(self, thing: Union[str, List[str]]) -> bool:
        """Match the self query against the given thing"""

    def __and__(self, other: "Query") -> "Query":
        """Combine two queries with AND"""
        if isinstance(self, NullQuery) or isinstance(other, NullQuery):
            return NullQuery()
        if isinstance(self, AnyQuery):
            return other
        if isinstance(other, AnyQuery):
            return self
        if isinstance(self, AndQuery) and isinstance(other, AndQuery):
            return AndQuery(*self._queries, *other._queries)
        if isinstance(self, AndQuery):
            return AndQuery(*self._queries, other)
        if isinstance(other, AndQuery):
            return AndQuery(self, *other._queries)
        return AndQuery(self, other)

    def __or__(self, other: "Query") -> "Query":
        """Combine two queries with OR"""
        if isinstance(self, AnyQuery) or isinstance(other, AnyQuery):
            return AnyQuery()
        if isinstance(self, NullQuery):
            return other
        if isinstance(other, NullQuery):
            return self
        if isinstance(self, OrQuery) and isinstance(other, OrQuery):
            return OrQuery(*self._queries, *other._queries)
        if isinstance(self, OrQuery):
            return OrQuery(*self._queries, other)
        if isinstance(other, OrQuery):
            return OrQuery(self, *other._queries)
        return OrQuery(self, other)


class NullQuery(Query):

    def match(self, thing: Union[str, List[str]]) -> bool:
        return False


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
