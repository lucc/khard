import unittest

from khard.query import AndQuery, AnyQuery, FieldQuery, NullQuery, OrQuery, TermQuery


class TestTermQuery(unittest.TestCase):

    def test_match_if_query_is_anywhere_in_string(self):
        q = TermQuery('bar')
        self.assertTrue(q.match('foo bar baz'))

    def test_query_terms_are_case_insensitive(self):
        q = TermQuery('BAR')
        self.assertTrue(q.match('foo bar baz'))

    def test_match_arguments_are_case_insensitive(self):
        q = TermQuery('bar')
        self.assertTrue(q.match('FOO BAR BAZ'))

    def test_match_lists_by_mathing_recursive(self):
        q = TermQuery('bar')
        self.assertTrue(q.match(['foo', 'bar baz']))


class TestAndQuery(unittest.TestCase):

    def test_matches_if_all_subterms_match(self):
        q1 = TermQuery("a")
        q2 = TermQuery("b")
        q = AndQuery(q1, q2)
        self.assertTrue(q.match("ab"))

    def test_failes_if_at_least_one_subterm_fails(self):
        q1 = TermQuery("a")
        q2 = TermQuery("b")
        q = AndQuery(q1, q2)
        self.assertFalse(q.match("ac"))


class TestOrQuery(unittest.TestCase):

    def test_matches_if_at_least_one_subterm_matchs(self):
        q1 = TermQuery("a")
        q2 = TermQuery("b")
        q = OrQuery(q1, q2)
        self.assertTrue(q.match("ac"))

    def test_failes_if_all_subterms_fail(self):
        q1 = TermQuery("a")
        q2 = TermQuery("b")
        q = OrQuery(q1, q2)
        self.assertFalse(q.match("cd"))
