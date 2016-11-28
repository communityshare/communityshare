import logging

from flask import Response, request, make_response

from community_share.app_exceptions import FileTypeNotImplemented, FileTypeNotPermitted
from community_share import mail_actions, store
from community_share.app_exceptions import BadRequest, NotFound, Unauthorized, InternalServerError
from community_share.flask_helpers import needs_admin_auth, needs_auth, serialize, serialize_many, make_single_response, make_OK_response
from community_share.models.user import User, UserReview
from community_share.models.institution import Institution
from community_share.authorization import get_requesting_user
from community_share.picture_utils import allowable_types as picture_types, get_image_type
from community_share.models.base import ValidationException
from community_share.models.institution import Institution
from community_share.models.user import User, UserReview
from community_share.picture_utils import image_to_user_filename, is_allowable_image, store_image
from community_share.routes import base_routes

logger = logging.getLogger(__name__)


def register_user_routes(app):

    user_blueprint = base_routes.make_blueprint(User, 'user')
    app.register_blueprint(user_blueprint)

    user_review_blueprint = base_routes.make_blueprint(UserReview, 'user_review')
    app.register_blueprint(user_review_blueprint)

    institution_blueprint = base_routes.make_blueprint(Institution, 'institution')
    app.register_blueprint(institution_blueprint)

    @app.route('/api/usersignup', methods=['POST'])
    def usersignup():
        data = request.json
        user = data.get('user', None)
        email = user.get('email', '')
        password = data.get('password', None)
        # Check that the email isn't in use.
        existing_user = store.session.query(User)
        existing_user = existing_user.filter(User.email == email, User.active == True)
        existing_user = existing_user.first()
        if existing_user is not None:
            raise BadRequest('That email address is already associated with an account.')
        elif password is None:
            raise BadRequest('No password was found. Please include a "password" property in the payload.')
        else:
            try:
                user = User.admin_deserialize_add(user)
                error_messages = user.set_password(password)
                if error_messages:
                    raise BadRequest(', '.join(error_messages))
                else:
                    store.session.add(user)
                    store.session.commit()
                    error_message = mail_actions.request_signup_email_confirmation(user)
                    secret = user.make_api_key()
                    serialized = user.serialize(user)
                    warning_message = 'Failed to send email confirmation: {0}'.format(error_message)
                    response_data = {
                        'data': serialized,
                        'apiKey': secret.key,
                        'warningMessage': warning_message,
                    }
                response = response_data
            except ValidationException as e:
                raise BadRequest(str(e))
        return response

    @app.route('/api/requestresetpassword/<string:email>', methods=['GET'])
    def request_reset_password(email):
        user = store.session.query(User).filter_by(email=email, active=True).first()
        if user is None:
            raise NotFound()
        else:
            error_message = mail_actions.request_password_reset(user)
            if error_message:
                raise InternalServerError(error_message)

        return make_OK_response()

    @app.route('/api/requestapikey', methods=['GET'])
    @needs_auth()
    def request_api_key(requester: User) -> Response:
        return {
            'apiKey': requester.make_api_key().key,
            'user': serialize(requester, requester),
        }

    @app.route('/api/resetpassword', methods=['POST'])
    def reset_password():
        data = request.json
        key = data.get('key', '')
        password = data.get('password', '')
        if key == '':
            raise BadRequest(
                'No key found. Please include a "key" property '
                'with the password reset token in the payload.',
            )
        elif password == '' or len(password) < 8:
            raise BadRequest(
                'New password was missing, blank, or too short. Please '
                'include a "password" property in the payload, and '
                'ensure that the password is at least 8 characters long.',
            )
        else:
            user, error_messages = mail_actions.process_password_reset(key, password)
            if error_messages:
                raise BadRequest(', '.join(error_messages))
            elif user is None:
                raise BadRequest()

        return make_single_response(user, user)

    @app.route('/api/requestconfirmemail', methods=['GET'])
    def request_confirm_email():
        requester = get_requesting_user()
        if requester is None:
            raise Unauthorized()
        else:
            error_message = mail_actions.request_signup_email_confirmation(requester)
            if error_message:
                raise InternalServerError(error_message)

        return make_OK_response()

    @app.route('/api/confirmemail', methods=['POST'])
    def confirm_email():
        data = request.json
        key = data.get('key', '')
        if key == '':
            raise BadRequest(
                'Key not found. Please include a "key" property in  the payload '
                'that contains the confirmation token that was provided via email.',
            )
        else:
            user, error_messages = mail_actions.process_confirm_email(key)
            if error_messages:
                raise BadRequest(', '.join(error_messages))
            elif user is None:
                raise BadRequest()
            else:
                secret = user.make_api_key()
                serialized = user.serialize(user)
                response_data = {
                    'data': serialized,
                    'apiKey': secret.key,
                }
                response = response_data
        return response

    @app.route('/api/usersearch', methods=['GET'])
    def search():
        requester = get_requesting_user()
        search_text = request.args.get('search_text', None)
        date_created_greaterthan = request.args.get('date_created.greaterthan', None)
        date_created_lessthan = request.args.get('date_created.lessthan', None)
        users = User.search(search_text, date_created_greaterthan, date_created_lessthan)
        return {'data': serialize_many(requester, users)}

    @app.route('/api/user/<int:user_id>/picture', methods=['PUT', 'POST', 'PATCH'])
    @needs_auth()
    def post_picture(user_id: int, requester: User) -> Response:
        if user_id != requester.id and not requester.is_administrator:
            raise Unauthorized()

        image_file = request.files['file']
        if not image_file:
            raise FileTypeNotImplemented(
                'Missing image data. Request needs to provide binary\n'
                'image data as the request parameter named "file".'
            )

        image_data = image_file.read()
        if not is_allowable_image(image_data):
            image_type = get_image_type(image_data)

            if image_type is None:
                reason = 'Could not infer type of image.'
            else:
                reason = 'Inferred image type {} is not allowed.'
                reason = reason.format(image_type)

            raise FileTypeNotPermitted(
                '{reason}\n\n'
                'Allowable types are {types}.'
                .format(
                    reason=reason,
                    types=', '.join(picture_types),
                )
            )

        filename = image_to_user_filename(image_data, user_id)

        store_image(image_file, filename)

        requester.picture_filename = filename
        store.session.add(requester)
        store.session.commit()

        logger.info('Saving image {!r}'.format(filename))

        return make_OK_response()

    @app.route('/api/activate_email', methods=['POST'])
    def activate_email():
        User.activate_email()

    @app.route('/api/dump_csv', methods=['GET'])
    @needs_admin_auth()
    def dump_csv(requester: User) -> Response:
        csv_obj = User.dump_csv()
        response = make_response(csv_obj.getvalue())
        response.headers["Content-Type"] = "text/csv"
        response.headers["Content-Disposition"] = "attachment; filename=communityshare.csv"
        return response
