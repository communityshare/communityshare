from typing import Dict

from flask import request, Blueprint
from sqlalchemy.exc import IntegrityError, InvalidRequestError

from community_share import with_store, Base, Store
from community_share.app_exceptions import BadRequest, Unauthorized, Forbidden, NotFound
from community_share.authorization import get_requesting_user
from community_share.flask_helpers import serialize, serialize_many, make_single_response, needs_auth
from community_share.utils import is_integer
from community_share.models.base import ValidationException
from community_share.models.user import User


@needs_auth()
@with_store
def get_item(
    Item: Base,
    id: int,
    requester: User=None,
    store: Store=None,
) -> Dict[str, Dict]:

    item = store.session.query(Item).filter_by(id=id, active=True).first()

    if item is None:
        raise NotFound()

    return make_single_response(requester, item)


def make_blueprint(Item: Base, resource_name: str) -> Blueprint:

    api = Blueprint(resource_name, __name__)

    @api.route(
        '/api/{0}'.format(resource_name),
        endpoint='get_many_{}'.format(resource_name),
        methods=['GET'],
    )
    def get_items():
        requester = get_requesting_user()
        if requester is None and not Item.PERMISSIONS.get('all_can_read_many', False):
            raise Unauthorized()
        else:
            if requester is None or not requester.is_administrator:
                if (Item.PERMISSIONS.get('standard_can_read_many', False) or
                    Item.PERMISSIONS.get('all_can_read_many', False)):
                    try:
                        query = Item.args_to_query(request.args, requester)
                        if query is None:
                            raise Forbidden()
                        else:
                            items = query.all()
                            response = {'data': serialize_many(requester, items)}
                    except ValueError as e:
                        raise BadRequest(', '.join(e.args))
                else:
                    raise Forbidden()
            else:
                try:
                    query = Item.args_to_query(request.args, requester)
                    items = query.all()
                    response = {'data': serialize_many(requester, items)}
                except ValueError as e:
                    raise BadRequest(', '.join(e.args))
        return response

    @api.route(
        '/api/{0}/<int:id>'.format(resource_name),
        endpoint='get_{}'.format(resource_name),
        methods=['GET'],
    )
    def get_blueprint_item(id: int) -> Dict[str, Dict]:
        return get_item(Item, id)

    @api.route(
        '/api/{0}'.format(resource_name),
        endpoint='add_{}'.format(resource_name),
        methods=['POST'],
    )
    @with_store
    def add_item(store=None):
        requester = get_requesting_user()
        data = request.json
        if not Item.has_add_rights(data, requester):
            if requester is None:
                raise Unauthorized()
            else:
                raise Forbidden()
        else:
            try:
                item = Item.admin_deserialize_add(data)
                store.session.add(item)
                store.session.commit()
                refreshed_item = store.session.query(Item).filter_by(id=item.id).first()
                refreshed_item.on_add(requester)
                # commit again in case on_add changed it.
                store.session.commit()
                # and refresh again to update relationships
                refreshed_item = store.session.query(Item).filter_by(id=item.id).first()

                if refreshed_item is None:
                    raise BadRequest()

                response = make_single_response(requester, refreshed_item)
                response['user'] = serialize(requester, requester)

            except ValidationException as e:
                raise BadRequest(str(e))
            except (IntegrityError, InvalidRequestError) as e:
                if len(e.args) > 0:
                    message = e.args[0]
                else:
                    message = ''
                raise BadRequest(message)
        return response

    @api.route(
        '/api/{0}/<id>'.format(resource_name),
        endpoint='edit_{}'.format(resource_name),
        methods=['PATCH', 'PUT'],
    )
    @with_store
    def edit_item(id, store=None):
        requester = get_requesting_user()
        if requester is None:
            raise Unauthorized()
        elif not is_integer(id):
            raise BadRequest()
        else:
            id = int(id)
            data = request.json
            data_id = data.get('id', None)
            if data_id is not None and int(data_id) != id:
                raise BadRequest()
            else:
                if id is None:
                    item = None
                else:
                    item = store.session.query(Item).filter_by(id=id).first()
                if item is None:
                    raise NotFound()
                else:
                    if item.has_admin_rights(requester):
                        try:
                            item.admin_deserialize_update(data)
                            store.session.add(item)
                            item.on_edit(requester, unchanged=not store.session.dirty)
                            store.session.commit()
                            response = make_single_response(requester, item)
                        except ValidationException as e:
                            raise BadRequest(str(e))
                    else:
                        raise Forbidden()
        return response

    @api.route(
        '/api/{0}/<id>'.format(resource_name),
        endpoint='delete_{}'.format(resource_name),
        methods=['DELETE'],
    )
    @with_store
    def delete_item(id, store=None):
        requester = get_requesting_user()
        if requester is None:
            raise Unauthorized()
        elif not is_integer(id):
            raise BadRequest()
        else:
            id = int(id)
            item = store.session.query(Item).filter_by(id=id).first()
            if item is None:
                raise NotFound()
            else:
                if item.has_delete_rights(requester):
                    item.delete(requester)
                    store.session.commit()
                    response = make_single_response(requester, item)
                else:
                    raise Forbidden()
        return response

    return api
