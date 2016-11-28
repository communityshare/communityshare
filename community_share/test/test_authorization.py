import unittest

from community_share.authorization import user_from_api_key, user_from_login
from community_share.models.secret import Secret, create_secret
from community_share.models.user import User
from community_share.models.survey import Answer
from community_share.test.in_memory_store import InMemoryStore


store = InMemoryStore()

active_user = {
    'id': 16,
    'name': 'Active User',
    'email': 'active@example.com',
    'password_hash': User.pwd_context.encrypt('password'),
}

inactive_user = {
    'id': 23,
    'name': 'Inactive User',
    'email': 'inactive@example.com',
    'password_hash': User.pwd_context.encrypt('inactive'),
    'active': False,
}

missing_user_id = 42


def add_user(user):
    store.session.add(User(**user))
    store.session.commit()


class AuthorizationTest(unittest.TestCase):
    """Authentication Tests

    Some of these tests appear to have redundancies in what
    they assert, such as when asserting that a user exists
    right after adding the user. These extra checks are here
    to keep the tests from giving false positives. For example,
    since the failure modes of the authentication functions
    all return None, we need to distinguish between cases where
    we have received None because a user didn't exist and where
    we have received None because a password was incorrect.

    This should be a comprehensive suite of tests for
    authenticating users within the app, but does not include
    the integration testing with Flask and HTTP requests

    """

    def setUp(self):
        store.reset()

    def test_rejects_missing_api_key_secret(self):
        add_user(active_user)

        self.assert_user_exists(active_user)
        self.assertIsNone(store.session.query(Secret).get('non-existent key'))
        self.assertIsNone(user_from_api_key('non-existent key', store=store))

    def test_rejects_non_api_key_secret(self):
        add_user(active_user)
        invalid_key = create_secret({'action': 'test', 'userId': active_user['id']}, 24, store=store).key

        self.assert_user_exists(active_user)
        self.assertIsNone(user_from_api_key(invalid_key, store=store))

    def test_rejects_valid_api_key_and_missing_user(self):
        non_user_key = create_secret({'action': 'api_key', 'userId': missing_user_id}, 24, store=store).key

        self.assert_user_missing({'id': missing_user_id})
        self.assertIsNone(store.session.query(User).get(missing_user_id))
        self.assertIsNone(user_from_api_key(non_user_key, store=store))

    def test_rejects_valid_api_key_and_inactive_user(self):
        add_user(inactive_user)
        inactive_user_key = create_secret({'action': 'api_key', 'userId': inactive_user['id']}, 24, store=store).key

        self.assert_user_inactive(inactive_user)
        self.assertIsNone(user_from_api_key(inactive_user_key, store=store))

    def test_accepts_valid_api_key_and_user(self):
        add_user(active_user)

        test_api_key = create_secret({'action': 'api_key', 'userId': active_user['id']}, 24, store=store).key

        self.assertIsInstance(user_from_api_key(test_api_key, store=store), User)

    def test_rejects_login_missing_user(self):
        self.assertIsNone(store.session.query(User).filter(User.email == 'email').first())
        self.assertIsNone(user_from_login('email', 'password', store=store))

    def test_rejects_login_inactive_user(self):
        add_user(inactive_user)

        self.assert_user_inactive(inactive_user)
        self.assertIsNone(user_from_login(inactive_user['email'], 'inactive', store=store))

    def test_rejects_invalid_password(self):
        add_user(active_user)

        self.assert_user_exists(active_user)
        self.assertIsNone(user_from_login(active_user['email'], 'wrong password', store=store))

    def test_accepts_valid_login(self):
        add_user(active_user)

        self.assertIsInstance(user_from_login(active_user['email'], 'password', store=store), User)

    def assert_user_exists(self, user):
        self.assertIsInstance(store.session.query(User).get(user['id']), User)

    def assert_user_inactive(self, user):
        stored_user = store.session.query(User).get(user['id'])

        self.assertIsInstance(stored_user, User)
        self.assertEqual(stored_user.active, False)

    def assert_user_missing(self, user):
        self.assertIsNone(store.session.query(User).get(user['id']))
