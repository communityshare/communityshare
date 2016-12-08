import unittest

from sqlalchemy import Column, Integer, Boolean, String

from community_share.routes.base_routes import get_item
from community_share.test.in_memory_store import InMemoryStore
from community_share.models.base import Serializable
from community_share.models.user import User
from community_share.models.survey import Answer
from community_share import Base
from community_share.app_exceptions import Unauthorized, NotFound, Forbidden


store = InMemoryStore()


class Thing(Base, Serializable):
    __tablename__ = 'thing'
    id = Column(Integer, primary_key=True)
    active = Column(Boolean, default=True)
    secret = Column(Boolean, default=False)

    def has_standard_rights(self, requester):
        return not self.secret


thing = {'id': 1}
secret_thing = {'id': 1, 'secret': True}
inactive_thing = {**thing, "active": False}
user = User(id=1, is_administrator=False)


def add_thing(props):
    store.session.add(Thing(**props))
    store.session.commit()


class GetItemTest(unittest.TestCase):

    def setUp(self):
        store.reset()

    def test_clear(self):
        add_thing(thing)
        response = get_item(Thing, 1, store=store, requester=user)
        self.assertEqual(response['data'], thing)

    def test_unauthorized_if_not_authenticated(self):
        add_thing(thing)
        with self.assertRaises(Unauthorized):
            get_item(Thing, 1, store=store, requester=None)

    def test_not_found_if_item_missing(self):
        # This time we didn't add_thing(thing)
        with self.assertRaises(NotFound):
            get_item(Thing, 1, store=store, requester=user)

    def test_not_found_if_item_not_active(self):
        add_thing(inactive_thing)
        with self.assertRaises(NotFound):
            get_item(Thing, 1, store=store, requester=user)

    def test_forbidden_if_user_cant_deserialize(self):
        add_thing(secret_thing)
        with self.assertRaises(Forbidden):
            get_item(Thing, 1, store=store, requester=user)
