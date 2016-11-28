from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from community_share import Base


class InMemoryStore:

    def __init__(self):
        self.engine = create_engine('sqlite:///:memory:')
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def reset(self):
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
