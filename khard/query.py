"""Queries to match against contacts"""

import abc
from datetime import datetime
from functools import reduce
from operator import and_, or_
import re
from typing import cast, Any, Dict, List, Optional, Union

from . import carddav_object

# constants
FIELD_PHONE_NUMBERS = "phone_numbers"


class Query(metaclass=abc.ABCMeta):

    """A query to match against strings, lists of strings and CarddavObjects"""

    @abc.abstractmethod
    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        """Match the self query against the given thing"""

    @abc.abstractmethod
    def get_term(self) -> Optional[str]:
        """Extract the search terms from a query."""

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

    """The null-query, it matches nothing."""

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return False

    def get_term(self) -> None:
        return None

    def __str__(self) -> str:
        return "NONE"


class AnyQuery(Query):

    """The match-anything-query, it always matches."""

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return True

    def get_term(self) -> str:
        return ""

    def __hash__(self) -> int:
        return hash(NullQuery)

    def __str__(self) -> str:
        return "ALL"


class TermQuery(Query):

    """A query to match an object against a fixed string."""

    def __init__(self, term: str) -> None:
        self._term = term.lower()

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        if isinstance(thing, str):
            return self._term in thing.lower()
        return self._term in thing.pretty().lower()

    def get_term(self) -> str:
        return self._term

    def __eq__(self, other: object) -> bool:
        return isinstance(other, TermQuery) and self._term == other._term

    def __hash__(self) -> int:
        return hash((TermQuery, self._term))

    def __str__(self) -> str:
        return self._term


class FieldQuery(TermQuery):

    """A query to match against a certain field in a carddav object."""

    def __init__(self, field: str, value: str) -> None:
        self._field = field
        super().__init__(value)

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        if isinstance(thing, str):
            return super().match(thing)
        if hasattr(thing, self._field):
            return self._match_union(getattr(thing, self._field))
        return False

    def _match_union(self, value: Union[str, datetime, List, Dict[str, Any]]
                     ) -> bool:
        if isinstance(value, str):
            return self.match(value)
        if isinstance(value, list):
            return any(self._match_union(item) for item in value)
        if isinstance(value, dict):
            for key in value:
                if self.match(key) or self._match_union(value[key]):
                    return True
            return False
        if isinstance(value, datetime):
            # currently we only support ISO dates
            return value == datetime.strptime(self._term, "%Y-%m-%d")
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

    """A query to combine multiple queries with "and"."""

    def __init__(self, first: Query, second: Query, *queries: Query) -> None:
        self._queries = (first, second, *queries)

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return all(q.match(thing) for q in self._queries)

    def get_term(self) -> Optional[str]:
        terms = [x.get_term() for x in self._queries]
        if None in terms:
            return None
        return "".join(cast(List[str], terms))

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

    """A query to combine multiple queries with "or"."""

    def __init__(self, first: Query, second: Query, *queries: Query) -> None:
        self._queries = (first, second, *queries)

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        return any(q.match(thing) for q in self._queries)

    def get_term(self) -> Optional[str]:
        terms = [x.get_term() for x in self._queries]
        if all(t is None for t in terms):
            return None
        return "".join(filter(None, terms))

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


class NameQuery(TermQuery):

    """special query to match any kind of name field of a vCard"""

    def __init__(self, term: str) -> None:
        super().__init__(term)
        self._props_query = OrQuery(FieldQuery("formatted_name", term),
                                    FieldQuery("nicknames", term))

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        m = super().match
        if isinstance(thing, str):
            return m(thing)
        return (m(thing.get_first_name_last_name()) or
                m(thing.get_last_name_first_name()) or
                self._props_query.match(thing))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, NameQuery) and self._term == other._term

    def __hash__(self) -> int:
        return hash((NameQuery, self._term))

    def __str__(self) -> str:
        return 'name:{}'.format(self._term)


class PhoneNumberQuery(FieldQuery):

    """A special query to match against phone numbers."""

    @staticmethod
    def _strip_phone_number(number: str) -> str:
        return re.sub("[^0-9+]", "", number)

    def __init__(self, value: str) -> None:
        super().__init__(FIELD_PHONE_NUMBERS, value)
        self._term_only_digits = self._strip_phone_number(value)

    def match(self, thing: Union[str, "carddav_object.CarddavObject"]) -> bool:
        if isinstance(thing, str):
            return self._match_union(thing)
        else:
            return super().match(thing)

    def _match_union(self, value: Union[str, datetime, List, Dict[str, Any]]
                     ) -> bool:
        if isinstance(value, str):
            if self._term in value.lower() \
                    or self._match_phone_number(self._strip_phone_number(value)):
                return True
        if isinstance(value, dict):
            for key in value:
                if self._term in str(key).lower():
                    return True
                if isinstance(value[key], str):
                    if self._match_phone_number(
                            self._strip_phone_number(value[key])):
                        return True
                if isinstance(value[key], list):
                    for number in value[key]:
                        if self._match_phone_number(
                                self._strip_phone_number(number)):
                            return True
            return False
        # this should actually be a type error
        return False

    def _match_phone_number(self, number: str) -> bool:
        if self._term_only_digits.startswith("+") and number.startswith("+"):
            # _term_only_digits: +49123456789
            # number: +49123456789
            return self._term_only_digits in number
        elif self._term_only_digits.startswith("+") and number.startswith("0"):
            # assume, that _term_only_digits contains a complete phone number
            # _term_only_digits: +49123456789
            # number: 0123456789
            return number[1:] in self._term_only_digits
        elif self._term_only_digits.startswith("0") and number.startswith("+"):
            # can't assume, that _term_only_digits contains a complete phone number
            # _term_only_digits: 0123456789
            # number: +49123456789
            if len(self._term_only_digits) >= 5:
                # don't strip the leading "0" if the search term is too short
                # otherwise you may get false positives
                # _term could contain the latter part of a phone number instead
                return self._term_only_digits[1:] in number
        # end of special cases
        if self._term_only_digits:
            return self._term_only_digits in number
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, PhoneNumberQuery) and self._term == other._term

    def __hash__(self) -> int:
        return hash((PhoneNumberQuery, self._term))

    def __str__(self) -> str:
        return 'phone numbers:{}'.format(self._term)


def parse(string: str) -> Union[TermQuery, FieldQuery]:
    """Parse a string into a query object

    The input string interpreted as a :py:class:`FieldQuery` if it starts with
    a valid property name of the
    :py:class:`~khard.carddav_object.CarddavObject` class, followed by a colon
    and an arbitrary search term.  Otherwise it is interpreted as a
    :py:class:`TermQuery`.

    :param string: a string to parse into a query
    :returns: a FieldQuery if the string contains a valid field specifier, a
        TermQuery otherwise
    """
    if ":" in string:
        field, term = string.split(":", maxsplit=1)
        if field == "name":
            return NameQuery(term)
        if field == FIELD_PHONE_NUMBERS:
            return PhoneNumberQuery(term)
        if field in carddav_object.CarddavObject.get_properties():
            return FieldQuery(field, term)
    return TermQuery(string)
