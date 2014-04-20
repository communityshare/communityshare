import logging

from flask import session, jsonify, request, Blueprint

from sqlalchemy.exc import IntegrityError, InvalidRequestError

from community_share.store import session
from community_share.utils import StatusCodes, is_integer
from community_share.authorization import get_requesting_user

logger = logging.getLogger(__name__)

API_MANY_FORMAT = '/api/{0}'
API_SINGLE_FORMAT = '/api/{0}/<id>'

def make_not_authorized_response():
    response_data = {'message': 'Authorization failed'}
    response = jsonify(response_data)
    response.status_code = StatusCodes.NOT_AUTHORIZED
    return response

def make_forbidden_response():
    response_data = {'message': 'Forbidden'}
    response = jsonify(response_data)
    response.status_code = StatusCodes.FORBIDDEN
    return response

def make_not_found_response():
    response_data = {'message': 'Not found'}
    response = jsonify(response_data)
    response.status_code = StatusCodes.NOT_FOUND
    return response

def make_bad_request_response(message=None):
    if message is None:
        message = 'Bad request'
    response_data = {'message': message}
    response = jsonify(response_data)
    response.status_code = StatusCodes.BAD_REQUEST
    return response

def make_OK_response(message=None):
    if message is None:
        message = 'OK'
    response_data = {'message': message}
    response = jsonify(response_data)
    response.status_code = StatusCodes.OK
    return response

def make_server_error_response(message=None):
    if message is None:
        message = 'Server error'
    response_data = {'message': message}
    response = jsonify(response_data)
    response.status_code = StatusCodes.SERVER_ERROR
    return response

def make_standard_many_response(items):
    serialized = [item.standard_serialize() for item in items]
    response_data = {'data': serialized}
    response = jsonify(response_data)
    return response

def make_admin_many_response(items):
    serialized = [item.admin_serialize() for item in items]
    response_data = {'data': serialized}
    response = jsonify(response_data)
    return response

def make_standard_single_response(item):
    if item is None:
        response = make_not_found_response()
    else:
        serialized = item.standard_serialize()
        response_data = {'data': serialized}
        response = jsonify(response_data)
    return response

def make_admin_single_response(item):
    if item is None:
        response = make_not_found_response()
    else:
        serialized = item.admin_serialize()
        response_data = {'data': serialized}
        response = jsonify(response_data)
    return response


def make_blueprint(Item, resourceName):

    api = Blueprint(resourceName, __name__)

    def _args_to_filter_params():
        filter_args = []
        filter_kwargs = {}
        for key in request.args.keys():
            bits = key.split('.')
            if hasattr(Item, bits[0]):
                if len(bits) > 2:
                    raise Exception('Unknown filter parameter')
                elif len(bits) == 2:
                    if bits[1] in ('like', 'ilike'):
                        new_arg = getattr(getattr(Item, bits[0]), bits[1])(request.args[key])
                        filter_args.append(new_arg)
                    else:
                        raise Exception('Unknown filter parameter')
        return filter_args, filter_kwargs

    def _get_raw_items():
        filter_args, filter_kwargs = _args_to_filter_params()
        items = session.query(Item).filter(*filter_args, **filter_kwargs)
        return items

    @api.route(API_MANY_FORMAT.format(resourceName), methods=['GET'])
    def get_items():
        requester = get_requesting_user()
        if requester is None:
            response = make_not_authorized_response()
        elif not requester.is_administrator:
            if Item.PERMISSIONS.standard_can_ready_many:
                items = _get_raw_items()
                response = make_standard_many_response(items)
            else:
                response = make_forbidden_response()
        else:
            items = _get_raw_items()
            response = make_admin_many_response(items)
        return response

    @api.route(API_SINGLE_FORMAT.format(resourceName), methods=['GET'])
    def get_item(id):
        requester = get_requesting_user()
        if requester is None:
            response = make_not_authorized_response()
        elif not is_integer(id):
            response = make_bad_request_user()
        else:
            item = session.query(Item).filter_by(id=id).first()
            if item is None:
                response = make_not_found_response()
            else:
                if item.has_admin_rights(requester):
                    response = make_admin_single_response(item)
                else:
                    response = make_standard_single_response(item)
        return response

    @api.route(API_MANY_FORMAT.format(resourceName), methods=['POST'])
    def add_item():
        requester = get_requesting_user()
        if not Item.has_add_rights(requester):
            if requester is None:
                response = make_not_authorized_response()
            else:
                response = make_forbidden_response()
        else:
            data = request.json
            logger.debug('data send is {0}'.format(data))
            item = Item.admin_deserialize_add(data)
            session.add(item)
            try:
                session.commit()
                if item.has_admin_rights(requester):
                    response = make_admin_single_response(item)
                else:
                    response = make_standard_single_response(item)
            except (IntegrityError, InvalidRequestError) as e:
                logger.error(e)
                import pdb
                pdb.set_trace()
                response = make_server_error_response()
        return response
        
    @api.route(API_SINGLE_FORMAT.format(resourceName), methods=['PATCH', 'PUT'])
    def edit_item(id):
        requester = get_requesting_user()
        if requester is None:
            response = make_not_authorized_response()
        elif not is_integer(id):
            response = make_bad_request_response()
        else:
            id = int(id)
            data = request.json
            data_id = data.get('id', None)
            if data_id is not None and int(data_id) != id:
                response = make_bad_request_response()
            else:
                if id is None:
                    item = None
                else:
                    item = session.query(Item).filter_by(id=id).first()
                if item is None:
                    response = make_not_found_response()
                else:
                    if item.has_admin_rights(requester):
                       item.admin_deserialize_update(data)
                       session.add(item)
                       session.commit()
                       response = make_admin_single_response(item)
                    else:
                       response = make_forbidden_response()
        return response
        
    return api
