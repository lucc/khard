"""Queries to match against contacts"""

import abc
from functools import reduce
from operator import and_, or_
from typing import Any, Dict, List, Optional, Union

from . import carddav_object


class Query(metaclass=abc.ABCMeta):

    """A query to match against strings, lists of strings and CarddavObjects"""

    @abc.abstractmethod
    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
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

    def __eq__(self, other: object) -> bool:
        """A generic equality for all query types without parameters"""
        return isinstance(other, type(self))

    def __hash__(self) -> int:
        "A generic hashing implementation for all queries without parameters"
        return hash(type(self))


class NullQuery(Query):

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return False

    def __str__(self) -> str:
        return "NONE"


class AnyQuery(Query):

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return True

    def __hash__(self) -> int:
        return hash(NullQuery)

    def __str__(self) -> str:
        return "ALL"


class TermQuery(Query):

    def __init__(self, term: str) -> None:
        self._term = term.lower()

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        if isinstance(thing, str):
            return self._term in thing.lower()
        return self._term in thing.pretty().lower()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TermQuery) and self._term == other._term

    def __hash__(self) -> int:
        return hash((TermQuery, self._term))

    def __str__(self) -> str:
        return self._term


class FieldQuery(TermQuery):

    def __init__(self, field: str, value: str) -> None:
        self._field = field
        super().__init__(value)

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        if isinstance(thing, str):
            return super().match(thing)
        if hasattr(thing, self._field):
            return self._match_union(getattr(thing, self._field))
        return False

    def _match_union(self, value: Union[str, List, Dict[str, Any]]) -> bool:
        if isinstance(value, str):
            return self.match(value)
        if isinstance(value, list):
            return any(self._match_union(item) for item in value)
        if isinstance(value, dict):
            for key in value:
                if self.match(key) or self._match_union(value[key]):
                    return True
            return False
        # this should actually be a type error
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FieldQuery) and self._field == other._field \
            and super().__eq__(other)

    def __hash__(self) -> int:
        return hash((FieldQuery, self._field, self._term))

    def __str__(self) -> str:
        return '{}:{}'.format(self._field, self._term)


class AndQuery(Query):

    def __init__(self, first: Query, second: Query, *queries: Query) -> None:
        self._queries = (first, second, *queries)

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return all(q.match(thing) for q in self._queries)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, AndQuery) \
            and frozenset(self._queries) == frozenset(other._queries)

    def __hash__(self) -> int:
        return hash((AndQuery, frozenset(self._queries)))

    @staticmethod
    def reduce(queries: List[Query], start: Optional[Query] = None) -> Query:
        return reduce(and_, queries, start or AnyQuery())

    def __str__(self) -> str:
        return ' '.join(str(q) for q in self._queries)


class OrQuery(Query):

    def __init__(self, first: Query, second: Query, *queries: Query) -> None:
        self._queries = (first, second, *queries)

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return any(q.match(thing) for q in self._queries)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, OrQuery) \
            and frozenset(self._queries) == frozenset(other._queries)

    def __hash__(self) -> int:
        return hash((OrQuery, frozenset(self._queries)))

    @staticmethod
    def reduce(queries: List[Query], start: Optional[Query] = None) -> Query:
        return reduce(or_, queries, start or NullQuery())

    def __str__(self) -> str:
        return ' | '.join(str(q) for q in self._queries)
