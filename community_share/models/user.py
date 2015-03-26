from nltk.stem.lancaster import LancasterStemmer
from nltk.corpus import stopwords
import nltk
from datetime import datetime
import logging
import csv
import io

import sqlalchemy
from sqlalchemy import Column, Integer, String, DateTime, \
    Boolean, and_, or_, update, Table, UniqueConstraint
from sqlalchemy import ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship, backref

import passlib
from passlib import context

from community_share import store, Base, config
from community_share.models.base import Serializable
from community_share.models.secret import Secret
from community_share.models.search import Search
from community_share.models.institution import InstitutionAssociation, Institution


logger = logging.getLogger(__name__)

stemmer = LancasterStemmer()
stopwords = set(stopwords.words('english'))
def munch_text(text):
    words = [w for w in nltk.word_tokenize(text) if w not in stopwords]
    stems = [stemmer.stem(word) for word in words]
    return stems

user_label_table = Table('user_label', Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id')),
    Column('typed_label_id', Integer, ForeignKey('typed_label.id'))
)

class User(Base, Serializable):
    __tablename__ = 'user'

    MANDATORY_FIELDS = ['name', 'email']
    WRITEABLE_FIELDS = [
        'name', 'is_administrator', 'institution_associations',
        'zipcode', 'website', 'twitter_handle', 'linkedin_link',
        'year_of_birth', 'gender', 'ethnicity', 'bio', 'phonenumber',
        'educator_profile_search', 'community_partner_profile_search',
        'wants_update_emails', 'labels',
    ]
    STANDARD_READABLE_FIELDS = [
        'id', 'name', 'is_administrator', 'last_active', 'is_educator',
        'is_community_partner', 'institution_associations',
        'zipcode', 'website', 'twitter_handle', 'linkedin_link',
        'year_of_birth', 'gender', 'ethnicity', 'bio', 'picture_url',
        'email_confirmed', 'active', 'educator_profile_search',
        'community_partner_profile_search', 'labels']

    ADMIN_READABLE_FIELDS = [
        'id', 'name', 'email' , 'date_created', 'last_active',
        'is_administrator', 'is_educator', 'is_community_partner',
        'institution_associations',
        'zipcode', 'phonenumber', 'website', 'twitter_handle', 'linkedin_link',
        'year_of_birth', 'gender', 'ethnicity', 'bio', 'picture_url',
        'email_confirmed', 'active', 'educator_profile_search',
        'community_partner_profile_search', 'wants_update_emails',
        'labels',
    ]

    PERMISSIONS = {
        'all_can_read_many': False,
        'standard_can_read_many': False,
        'admin_can_delete': True
    }

    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False)
    email = Column(String(50), nullable=False)
    email_confirmed = Column(Boolean, nullable=False, default=False)
    active = Column(Boolean, default=True)
    password_hash = Column(String(120), nullable=True)
    date_created = Column(DateTime, nullable=False, default=datetime.utcnow)
    date_inactivated = Column(DateTime, nullable=True)
    is_administrator = Column(Boolean, nullable=False, default=False)
    is_educator = Column(Boolean, nullable=False, default=False)
    is_community_partner = Column(Boolean, nullable=False, default=False)
    last_active = Column(DateTime)
    educator_profile_search_id = Column(Integer)
    community_partner_profile_search_id = Column(Integer)
    wants_update_emails = Column(Boolean, nullable=False, default=False)

    picture_filename = Column(String(100))
    bio = Column(String(1000))
    search_text = Column(String(2000))
    zipcode = Column(String(50))
    phonenumber = Column(String(50))
    website = Column(String(100))
    twitter_handle = Column(String(100))
    linkedin_link = Column(String(100))
    year_of_birth = Column(Integer)
    gender = Column(String(100))
    ethnicity = Column(String(100))

    labels = relationship('TypedLabel', secondary=user_label_table)

    searches = relationship(
        "Search",
        primaryjoin="Search.searcher_user_id == User.id",
        backref="searcher_user")
    institution_associations = relationship("InstitutionAssociation")
    educator_profile_search = relationship(
        "Search",
        primaryjoin="Search.id == User.educator_profile_search_id",
        foreign_keys="User.educator_profile_search_id")
    community_partner_profile_search = relationship(
        "Search",
        primaryjoin="Search.id == User.community_partner_profile_search_id",
        foreign_keys="User.community_partner_profile_search_id")

    pwd_context = passlib.context.CryptContext(
        schemes=['sha512_crypt'],
        default='sha512_crypt',
        all__vary_rounds = 0.1,
        sha512_crypt__vary_rounds = 8000,
    )

    def searches_as(self, role):
        searches = store.session.query(Search).filter_by(
            searcher_user_id=self.id, searcher_role=role).all()
        return searches

    @property
    def confirmed_email(self):
        output = None
        if self.email_confirmed:
            output = self.email
        return output

    def is_password_correct(self, password):
        if not self.password_hash:
            is_correct = False
        else:
            is_correct = self.pwd_context.verify(password, self.password_hash)
        return is_correct

    @classmethod
    def is_password_valid(cls, password):
        error_messages = []
        if len(password) < 8:
            error_messages.append(
                'Password must have a length of at least 8 characters')
        return error_messages

    def set_password(self, password):
        output = None
        error_messages = self.is_password_valid(password)
        if not error_messages:
            password_hash = User.pwd_context.encrypt(password)
            self.password_hash = password_hash
        return error_messages

    def __repr__(self):
        output = "<User(email={email})>".format(email=self.email)
        return output

    @classmethod
    def has_add_rights(cls, data, user):
        return False

    def has_admin_rights(self, user):
        has_admin_rights = False
        if user is not None:
            if user.is_administrator:
                has_admin_rights = True
            elif user.id == self.id:
                has_admin_rights = True
        return has_admin_rights

    def serialize(self, requester, exclude=[]):
        return self._base_serialize(requester, exclude)

    def serialize_institution_associations(self, requester):
        associations = [i.serialize(requester)
                        for i in self.institution_associations]
        return associations

    def serialize_educator_profile_search(self, requester):
        search = self.educator_profile_search
        if (search and search.active):
            serialized = search.serialize(requester, exclude='searcher_user')
        else:
            serialized = None
        return serialized

    def serialize_community_partner_profile_search(self, requester):
        search = self.community_partner_profile_search
        if (search and search.active):
            serialized = search.serialize(requester, exclude='searcher_user')
        else:
            serialized = None
        return serialized

    def serialize_picture_url(self, requester):
        url = ''
        if (config.UPLOAD_LOCATION is not None) and self.picture_filename:
            url = config.UPLOAD_LOCATION + self.picture_filename
        return url

    def serialize_labels(self, requester):
        return [(l.name, l.typ) for l in self.labels]

    custom_serializers = {
        'labels': serialize_labels,
        'institution_associations': serialize_institution_associations,
        'picture_url': serialize_picture_url,
        'educator_profile_search': serialize_educator_profile_search,
        'community_partner_profile_search': serialize_community_partner_profile_search,
    }

    def deserialize_bio(self, bio):
        BIO_LIMIT = 1000
        if bio != None:
            if len(bio) > BIO_LIMIT:
                bio = bio[:BIO_LIMIT]
        self.bio = bio

    def deserialize_institution_associations(self, data_list):
        if data_list is None:
            data_list = []
        data_list = [d for d in data_list if d != {}]
        self.institution_associations = [
            InstitutionAssociation.admin_deserialize(data) for data in data_list]
        for ia in self.institution_associations:
            ia.user = self

    def deserialize_educator_profile_search(self, data):
        search = self.educator_profile_search
        if data is not None:
            if search and search.active:
                profile_search_id = search.id
            else:
                profile_search_id = None
            data['id'] = profile_search_id
            self.educator_profile_search = Search.admin_deserialize(data)

    def deserialize_community_partner_profile_search(self, data):
        search = self.community_partner_profile_search
        if data is not None:
            if search and search.active:
                profile_search_id = search.id
            else:
                profile_search_id = None
            data['id'] = profile_search_id
            self.community_partner_profile_search = Search.admin_deserialize(data)

    def deserialize_labels(self, labeltuples):
        if labelnames is None:
            labelnames = []
        self.labels = TypedLabel.tuple_list_to_object_list(labeltuples)

    custom_deserializers = {
        'labels': deserialize_labels,
        'institution_associations': deserialize_institution_associations,
        'educator_profile_search': deserialize_educator_profile_search,
        'community_partner_profile_search': deserialize_community_partner_profile_search,
        'bio': deserialize_bio,
        }

    def make_api_key(self):
        secret_data = {
            'userId': self.id,
            'action': 'api_key',
        }
        secret = Secret.create_secret(info=secret_data, hours_duration=24)
        return secret

    @classmethod
    def from_api_key(self, key):
        secret = Secret.lookup_secret(key)
        logger.debug('key is {0}'.format(key))
        logger.debug('secret is {0}'.format(secret))
        user_id = None
        if secret is not None:
            info = secret.get_info()
            if info.get('action', None) == 'api_key':
                user_id = info.get('userId', None)
        if user_id is not None:
            user = store.session.query(User).filter_by(id=user_id).first()
            logger.debug('user from api_key is {0}'.format(user))
        else:
            user = None
        return user

    def on_delete(self, requester):
        # Importing here to prevent circular reference
        from community_share import mail_actions
        from community_share.models.share import Event, Share
        mail_actions.send_account_deletion_message(self)
        # Delete all upcoming events.
        upcoming_events = store.session.query(Event).filter(
            and_(Event.active==True,
                 or_(Share.educator_user_id==self.id,
                     Share.community_partner_user_id==self.id)))
        shares = set([])
        for event in upcoming_events:
            event.delete(requester)
            shares.add(event.share)
        for share in shares:
            other_user = None
            if share.educator_user_id == self.id:
                other_user = share.community_partner
            elif share.community_partner_user_id == self.id:
                other_user = share.educator
            mail_actions.send_partner_deletion_message(
                other_user, self, share.conversation)

    @classmethod
    def search(cls, search_text, date_created_greaterthan, date_created_lessthan):
        '''
        searchText can match name, email, institution name
        '''
        query = store.session.query(User).outerjoin(InstitutionAssociation).outerjoin(Institution)
        if search_text:
            name_condition = User.name.ilike('%'+search_text+'%')
            email_condition = User.email.ilike('%'+search_text+'%')
            institution_condition = Institution.name.ilike('%'+search_text+'%')
            biography_condition = User.bio.ilike('%'+search_text+'%')
            query = query.filter(or_(name_condition, email_condition, \
                institution_condition, biography_condition))
        if date_created_greaterthan:
            query = query.filter(User.date_created > date_created_greaterthan)
        if date_created_lessthan:
            query = query.filter(User.date_created < date_created_lessthan)
        query = query.filter(User.active==True)
        users = query.all()
        return users

    @classmethod
    def activate_email(cls, user=None):
        if not user:
            store.session \
                .query(User) \
                .filter(User.active==True) \
                .filter(User.email_confirmed==False) \
                .update({'email_confirmed': True})
            store.session.commit()

    @classmethod
    def dump_csv(cls):
        query = store.session.query(User).all()
        dest = io.StringIO()
        writer = csv.writer(dest)
        header = ['username', 'email']
        writer.writerow(header)
        for user in query:
            row = [user.name, user.email]
            writer.writerow(row)
        return dest

    @classmethod
    def text_search(cls, text, limit=20):
        stems = munch_text(text)
        query_text =  ' | '.join(stems)
        print(query_text)
        sql = '''
select *, ts_rank_cd(st, q) as rank from "user", to_tsvector('english', search_text) st, to_tsquery('english', :query_text) q where st @@ q and active = 't' order by rank desc limit :limit;
'''
        users = store.session.query(cls).from_statement(
            sqlalchemy.text(sql)).params(query_text=query_text, limit=limit).all()
        return users
        

    def update_search_text(self):
        raw_string = self.bio
        if raw_string is None:
            raw_string = ''
        if self.is_community_partner:
            expertise_labels = [l.name for l in self.labels if l.typ == 'expertise']
            raw_string += ' ' + ' '.join(expertise_labels)
        raw_string += self.name
        for ia in self.institution_associations:
            raw_string += ' ' + ia.role + ' ' + ia.institution.name + ' ' + ia.institution.institution_type
        stems = munch_text(raw_string)
        self.search_text = ' '.join(stems)

class TypedLabel(Base, Serializable):
    __tablename__ = 'typed_label'
    __table_args__ = (UniqueConstraint('name', 'typ'),)
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    typ = Column(String(20), nullable=False)
    active = Column(Boolean, default=True)

    @classmethod
    def tuple_list_to_object_list(cls, tuples):
        names = [t[0] for t in tuples]
        typs = {}
        for t in tuples:
            if t[0] not in typs:
                typs[t[0]] = set([])
            typs[t[0]].add(t[1])
                
        labels = store.session.query(TypedLabel).filter(Label.name.in_(names)).all()
        matching_labels = []
        for label in labels:
            if label.typ in typs[label.name]:
                matching_labels.append(label)
                
        missing_tuples = set(tuples)
        for label in exiting_labels:
            missing_tuples.remove((label.name, label.typ))
        for name, typ in missing_tuples:
            new_label = TypedLabel(name=name, typ=typ)
            matching_labels.append(new_label)
        return matching_labels

# class UserReview(Base, Serializable):
#     __tablename__ = 'userreview'

#     MANDATORY_FIELDS = [
#         'user_id', 'rating', 'creator_user_id', 'event_id']
#     WRITEABLE_FIELDS = [
#         'review']
#     STANDARD_READABLE_FIELDS = [
#         'id', 'user_id', 'rating', 'review'
#     ]
#     ADMIN_READABLE_FIELDS = [
#         'id', 'user_id', 'rating', 'review'
#     ]

#     PERMISSIONS = {
#         'all_can_read_many': False,
#         'standard_can_read_many': False,
#         'admin_can_delete': False
#     }

#     id = Column(Integer, primary_key=True)
#     user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
#     event_id = Column(Integer, ForeignKey('event.id'))
#     rating = Column(Integer, nullable=False)
#     active = Column(Boolean, nullable=False, default=True)
#     date_created = Column(DateTime, nullable=False, default=datetime.utcnow)
#     creator_user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
#     review = Column(String(5000))

#     __table_args__ = (
#         CheckConstraint('rating>=0', 'Rating is negative'),
#         CheckConstraint('rating<=5', 'Rating is greater than 5'),
#     )

#     event = relationship('Event')
#     user = relationship('User', primaryjoin='UserReview.user_id == User.id')
#     creator_user = relationship('User', primaryjoin='UserReview.creator_user_id == User.id')


#     @classmethod
#     def has_add_rights(cls, data, requester):
#         from community_share.models.share import Event
#         has_rights = False
#         data['creator_user_id'] = requester.id
#         event_id = int(data.get('event_id', -1))
#         user_id = int(data.get('user_id', -1))
#         event = store.session.query(Event).filter(Event.id==event_id).first()
#         now = datetime.utcnow()
#         if event.active and event.datetime_start < now:
#             event_users = set([event.share.educator_user_id,
#                                event.share.community_partner_user_id])
#             request_users = set([requester.id, user_id])
#             if event_users == request_users:
#                 already_exists = store.session.query(UserReview).filter(and_(
#                     UserReview.user_id==user_id,
#                     UserReview.creator_user_id==requester.id,
#                     UserReview.event_id==event_id)).count()
#                 total = store.session.query(UserReview).count()
#                 logger.debug('Review already existing = {} total={}'.format(already_exists, total))
#                 if not already_exists:
#                     has_rights = True
#         return has_rights
