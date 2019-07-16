import re
from datetime import date

import neomodel
from neomodel import StructuredNode, StringProperty, config, DateProperty, Relationship

MONTHS = {x[0]: x[1] for x in zip(['janvier', 'février', 'mars', 'avril', 'mai',
          'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'], range(1, 13))}


config.DATABASE_URL = 'bolt://neo4j:neo@localhost:7687'
config.AUTO_INSTALL_LABELS = True


class CompanyDB(StructuredNode):
    link = StringProperty()
    name = StringProperty(required=True)
    address = StringProperty()
    info = StringProperty()
    leaders = None

    leader = Relationship('LeaderDB', 'OWNED')

    def __init__(self, *args, **kwargs):
        self.leaders = set()
        super().__init__(*args, **kwargs)

    def is_in_db(self):
        try:
            CompanyDB.nodes.get(name=self.name)
            return True
        except neomodel.DoesNotExist:
            return False

    def __hash__(self):
        return hash(str(self.link) + str(self.name) + str(self.address) + str(self.info))

    def __eq__(self, other):
        return hash(self) == hash(other)


class LeaderDB(StructuredNode):
    link = StringProperty()
    name = StringProperty(required=True)
    b_date = DateProperty()
    companies = None
    roles = None

    company = Relationship('CompanyDB', 'OWNER')

    def __init__(self, *args, **kwargs):
        self.companies = set()
        self.roles = []
        super().__init__(*args, **kwargs)

    def is_in_db(self):
        try:
            LeaderDB.nodes.get(name=self.name, b_date=self.b_date)
            return True
        except neomodel.DoesNotExist:
            return False
        except neomodel.DeflateError:
            try:
                LeaderDB.nodes.get(name=self.name)
                return True
            except neomodel.DoesNotExist:
                return False

    def __hash__(self):
        return hash(str(self.name) + str(self.b_date))

    def __eq__(self, other):
        return hash(self) == hash(other)

    def set_b_date(self, b_date):
        if b_date is None:
            return
        b_date = b_date.replace(' ', '')
        month = re.search('([^\\W\\d_])+', b_date).group(0)
        numeric_data = b_date.replace(month, ' ').split(' ')
        self.b_date = date(int(numeric_data[1]), MONTHS[month], int(numeric_data[0]))
