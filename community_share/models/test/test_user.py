import unittest

from community_share.models.user import User
from community_share.models.survey import Answer
from community_share.test.in_memory_store import InMemoryStore


store = InMemoryStore()

user = {
    'id': 16,
    'name': 'Active User',
    'email': 'active@example.com',
    'password_hash': User.pwd_context.encrypt('password'),
}


def add_user(user):
    store.session.add(User(**user))
    store.session.commit()


class UserTest(unittest.TestCase):

    def setUp(self):
        store.reset()

    def test_is_administrator_not_writeable_on_update(self):
        add_user(user)
        stored_user = store.session.query(User).get(user['id'])
        stored_user.admin_deserialize_update({'is_administrator': 'True'})
        self.assertFalse(stored_user.is_administrator)

    def test_is_administrator_not_writeable_on_add(self):
        potential_admin_user = dict(user)
        potential_admin_user['is_administrator'] = True
        created_user = User.admin_deserialize_add(potential_admin_user)
        self.assertFalse(created_user.is_administrator)
