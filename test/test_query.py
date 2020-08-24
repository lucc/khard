import unittest

from khard.query import AndQuery, AnyQuery, FieldQuery, NameQuery, NullQuery, \
    OrQuery, TermQuery, parse

from .helpers import TestCarddavObject, load_contact


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

    def test_spaces_in_search_subject_are_not_stripped(self):
        q = TermQuery('oob')
        self.assertFalse(q.match('foo bar baz'))

    def test_spaces_in_query_are_not_stripped(self):
        q = TermQuery('foo bar')
        self.assertFalse(q.match('foobar'))


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

    def test_order_does_not_matter(self):
        q1 = TermQuery("a")
        q2 = TermQuery("b")
        q = AndQuery(q1, q2)
        self.assertTrue(q.match("ab"))
        self.assertTrue(q.match("ba"))

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

    def test_order_does_not_matter(self):
        q1 = TermQuery("a")
        q2 = TermQuery("b")
        q = OrQuery(q1, q2)
        self.assertTrue(q.match("ab"))
        self.assertTrue(q.match("ba"))


class TestEquality(unittest.TestCase):

    def test_any_queries_are_equal(self):
        self.assertEqual(AnyQuery(), AnyQuery())

    def test_null_queries_are_equal(self):
        self.assertEqual(NullQuery(), NullQuery())

    def test_or_queries_match_after_sorting(self):
        null = NullQuery()
        any = AnyQuery()
        term = TermQuery("foo")
        field = FieldQuery("x", "y")
        first = OrQuery(null, any, term, field)
        second = OrQuery(any, null, field, term)
        self.assertEqual(first, second)

    def test_and_queries_match_after_sorting(self):
        null = NullQuery()
        any = AnyQuery()
        term = TermQuery("foo")
        field = FieldQuery("x", "y")
        first = AndQuery(null, any, term, field)
        second = AndQuery(any, null, field, term)
        self.assertEqual(first, second)


class TestFieldQuery(unittest.TestCase):

    @unittest.expectedFailure
    def test_empty_field_values_match_if_the_field_is_present(self):
        # This test currently fails because the CarddavObject class has all
        # attributes set because they are properties.  So the test in the query
        # class if an attribute is present never fails.
        uid = 'Some Test Uid'
        vcard1 = TestCarddavObject(uid=uid)
        vcard2 = TestCarddavObject()
        query = FieldQuery('uid', '')
        self.assertTrue(query.match(vcard1))
        self.assertFalse(query.match(vcard2))

    def test_empty_field_values_fails_if_the_field_is_absent(self):
        vcard = TestCarddavObject()
        query = FieldQuery('emails', '')
        self.assertFalse(query.match(vcard))

    def test_values_can_match_exact(self):
        uid = 'Some Test Uid'
        vcard = TestCarddavObject(uid=uid)
        query = FieldQuery('uid', uid)
        self.assertTrue(query.match(vcard))

    def test_values_can_match_substrings(self):
        uid = 'Some Test Uid'
        vcard = TestCarddavObject(uid=uid)
        query = FieldQuery('uid', 'e Test U')
        self.assertTrue(query.match(vcard))

    def test_valuess_can_match_case_insensitive(self):
        uid = 'Some Test Uid'
        vcard = TestCarddavObject(uid=uid)
        query1 = FieldQuery('uid', uid.upper())
        query2 = FieldQuery('uid', uid.lower())
        self.assertTrue(query1.match(vcard))
        self.assertTrue(query2.match(vcard))

    def test_match_formatted_name(self):
        vcard = TestCarddavObject(fn='foo bar')
        query = FieldQuery('formatted_name', 'foo')
        self.assertTrue(query.match(vcard))

    def test_match_email(self):
        vcard = load_contact("contact1.vcf")
        query = FieldQuery('emails', 'user@example.com')
        self.assertTrue(query.match(vcard))

    def test_match_birthday(self):
        vcard = load_contact("contact1.vcf")
        query = FieldQuery('birthday', '2018-01-20')
        self.assertTrue(query.match(vcard))

    def test_fail_match_in_other_field(self):
        vcard = load_contact("contact1.vcf")
        query = FieldQuery('formatted_name', 'user@example.com')
        self.assertFalse(query.match(vcard))

    def test_match_email_type(self):
        vcard = load_contact("contact1.vcf")
        query = FieldQuery('emails', 'home')
        self.assertTrue(query.match(vcard))


class TestNameQuery(unittest.TestCase):

    def test_matches_formatted_name_field(self):
        vcard = load_contact("minimal.vcf")
        query = NameQuery("minimal")
        self.assertTrue(query.match(vcard))

    def test_matches_name_field(self):
        vcard = load_contact("nickname.vcf")
        query = NameQuery("smith")
        self.assertTrue(query.match(vcard))

    def test_matches_nickname_field(self):
        vcard = load_contact("nickname.vcf")
        query = NameQuery("mike")
        self.assertTrue(query.match(vcard))

    def test_does_not_match_uid_field(self):
        vcard = load_contact("contact1.vcf")
        query = NameQuery("testuid1")
        self.assertFalse(query.match(vcard))


class TestParser(unittest.TestCase):

    def test_parsing_simple_terms(self):
        string = "foo bar"
        expected = TermQuery(string)
        actual = parse(string)
        self.assertEqual(actual, expected)

    def test_parsing_simple_field_queries(self):
        actual = parse("formatted_name:foo bar")
        expected = FieldQuery("formatted_name", "foo bar")
        self.assertEqual(actual, expected)

    def test_bad_field_name_returns_term_query(self):
        string = "foo:bar"
        actual = parse(string)
        expected = TermQuery(string)
        self.assertEqual(actual, expected)

    def test_field_value_can_be_empty(self):
        actual = parse("formatted_name:")
        expected = FieldQuery("formatted_name", "")
        self.assertEqual(actual, expected)

    def test_field_value_can_contain_colons(self):
        actual = parse("formatted_name:foo:bar")
        expected = FieldQuery("formatted_name", "foo:bar")
        self.assertEqual(actual, expected)

    def test_special_field_name_creates_name_queries(self):
        actual = parse("name:foo")
        expected = NameQuery("foo")
        self.assertEqual(actual, expected)
