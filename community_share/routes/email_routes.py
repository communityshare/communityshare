import logging

from flask import request

from community_share.flask_helpers import make_OK_response
from community_share.models.conversation import Message
from community_share.mail import Email, get_mailer
from community_share.mail_actions import append_conversation_link
from community_share import config, store

logger = logging.getLogger(__name__)


def register_email_routes(app):
    @app.route('/api/email', methods=['POST'])
    def receive_email():

        logger.debug('Received an email.')

        if config.MAILER_TYPE == 'MAILGUN':
            verify = True
        else:
            verify = False
        email = Email.from_mailgun_data(request.values, verify=verify)
        logger.info('Received an email with content "{}"'.format(email.content))

        message = None
        message_id = Message.process_from_address(email.to_address)
        if message_id is not None:
            message = store.session.query(Message).filter_by(id=message_id).first()
        if message is None:
            logger.warning('Received an email but did not find corresponding message.')
        else:
            logger.debug('Creating a new email to send')
            # Create a new message
            new_message = Message(
                conversation_id=message.conversation_id,
                sender_user_id=message.receiver_user().id,
                content=email.new_content,
            )
            store.session.add(new_message)
            store.session.commit()
            # Create an email to send to the recipient
            forward_to_address = message.sender_user.email
            forward_from_address = new_message.generate_from_address()
            forward_content = append_conversation_link(email.content, message.conversation)
            forward_new_content = append_conversation_link(email.new_content, message.conversation)
            forward_email = Email(
                from_address=forward_from_address,
                to_address=forward_to_address,
                subject=email.subject,
                content=forward_content,
                new_content=forward_new_content,
            )
            error_message = get_mailer().send(forward_email)
        return make_OK_response()
