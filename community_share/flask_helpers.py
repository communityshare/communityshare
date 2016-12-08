from functools import wraps

from flask import request
from typing import Dict

from community_share.app_exceptions import Unauthorized, Forbidden
from community_share.authorization import get_requesting_user
from community_share.models.user import User
from community_share.models.base import Serializable


def api_path(path, query_args={}):
    query = []
    for name, values in query_args.items():
        if not isinstance(values, list):
            values = [values]

        query += ['{}={}'.format(name, value) for value in values]

    return '{base_url}rest/{path}{query}'.format(
        base_url=request.url_root,
        path=path,
        query='?{}'.format('&'.join(query)) if query else ''
    )


def needs_auth(auth_level='user'):
    def needs_auth_decorator(f):
        @wraps(f)
        def auth_check(*args, **kwargs):

            # Don't use
            #
            #   user = kwargs.pop('requester', get_requesting_user())
            #
            # here because the eager execution of get_requesting_user
            # will force us to be in flask app context during any test
            # that uses a @needs_auth() method, and that makes unit
            # tests harder.
            if 'requester' in kwargs:
                user = kwargs.pop('requester')
            else:
                user = get_requesting_user()

            if user is None:
                raise Unauthorized()

            if 'admin' == auth_level and not user.is_administrator:
                raise Unauthorized()

            return f(*args, requester=user, **kwargs)

        return auth_check

    return needs_auth_decorator


def needs_admin_auth():
    return needs_auth('admin')


def serialize(user, raw_item, fields=None):
    if raw_item is None:
        return None

    item = raw_item.serialize(user)

    if item is None:
        return None

    if fields is None:
        return item

    return {key: item[key] for key in item if key in fields + ['id']}


def serialize_many(user, raw_items, fields=None):
    items = [serialize(user, item, fields) for item in raw_items]

    return [item for item in items if item is not None]


def make_OK_response(message='OK'):
    return {'message': message}


def make_single_response(requester: User, item: Serializable) -> Dict[str, Dict]:
    serialized = serialize(requester, item)
    if serialized is None:
        raise Forbidden()
    return {'data': serialized}
