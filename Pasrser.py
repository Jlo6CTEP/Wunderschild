import asyncio
import csv
import re
import time

import aiohttp
from aiohttp import ClientSession
from bs4 import BeautifulSoup
from neomodel import db

from DBManager import LeaderDB, CompanyDB, MONTHS

INPUT_CSV = './input/siren_numbers.csv'

COMPANY_URL = 'https://www.verif.com/societe/{}/'

EXTRACT = {'raison sociale': 'name', 'adresse': 'address'}

RPS = 100

replace_spaces = re.compile('\\s\\s+')
replace_tabs = re.compile('\\s')
remove_m_mrs = re.compile('mme(.?)|m(.?)')
extract_date = re.compile(
    '([1-9]|1[0-9]|2[0-9]|3[0-1])( ?)({})( ?)[1-2][0-9][0-9][0-9]'.format('|'.join(MONTHS.keys())))


def clean(data):
    return replace_tabs.sub(' ', replace_spaces.sub(' ', data)).strip().lower()


def clean_name(data):
    return title(remove_m_mrs.sub('', clean(data))).strip()


def title(string):
    return ' '.join([x.capitalize() for x in string.split(' ')])


async def fetch(db_object, session):
    while 1:
        try:
            async with session.get(db_object.link, raise_for_status=True) as response:
                print(response.headers.get("DATE"))
                return await response.read(), db_object
        except (aiohttp.ClientResponseError, aiohttp.ClientConnectorError):
            await asyncio.sleep(1)
        except aiohttp.ClientOSError as e:
            print(e)
            await asyncio.sleep(1)


async def run(object_list):
    tasks = []

    async with ClientSession(auto_decompress=True) as session:
        for obj in object_list:
            if obj.link == '':
                continue
            task = asyncio.ensure_future(fetch(obj, session))
            tasks.append(task)

        return await asyncio.gather(*tasks)


def load_pages(objects):
    loop = asyncio.get_event_loop()
    future = asyncio.ensure_future(run(objects))
    return loop.run_until_complete(future)


def obtain_leaders(company_zip):
    company = company_zip[1]

    leaders = set()

    company_page = company_zip[0]
    soup = BeautifulSoup(company_page.decode('ISO-8859-1'), 'lxml')
    main_content = soup.find(class_='tab-content')

    # if there is no such company
    if main_content is None:
        return set()

    company.info = main_content.find(class_='accroche').get_text().strip()

    main_table = main_content.find(class_='infoGen')
    leaders_table = main_content.find(class_='dirigeants')

    for tr in main_table.findAll(recursive=False):
        t_row = tr.findAll(recursive=False)

        row_key = clean(t_row[0].get_text())
        if row_key not in EXTRACT:
            continue
        setattr(company, EXTRACT[row_key], clean(t_row[1].get_text()))

    if company.is_in_db():
        return set()

    company.save()

    for lead in company.leaders:
        if lead.b_date is None:
            company.leader.connect(LeaderDB.nodes.get(name=lead.name, link=lead.link))
        else:
            company.leader.connect(LeaderDB.nodes.get(name=lead.name, b_date=lead.b_date, link=lead.link))

    if leaders_table is None:
        return set()

    for tr in leaders_table.findAll(recursive=False):
        t_row = tr.findAll(recursive=False)

        row_key = clean(t_row[0].get_text())

        link = '' if t_row[1].a is None else t_row[1].a.get('href')
        link = 'http:' + link if not link.startswith('http') and link != '' else link
        name = t_row[1].get_text() if t_row[1].a is None else t_row[1].a.get_text()

        leader = LeaderDB(name=clean_name(name), link=link)
        leader.companies.update({company})
        leader.roles.append(row_key)

        leaders.update({leader})
    return leaders


def obtain_companies(leader_zip):
    companies = set()

    leader = leader_zip[1]

    leader_page = leader_zip[0]

    soup = BeautifulSoup(leader_page.decode('ISO-8859-1'), 'lxml')
    main_table = soup.find(class_='profile')

    if main_table is None:
        return set()

    date = extract_date.search(main_table.find(class_='text-content').get_text())

    if date is None:
        # this is invalid data-placeholder
        b_date = None
    else:
        b_date = date.group(0)
        b_date = None
    leader.set_b_date(b_date)
    companies_table = main_table.find_all(class_='elt')

    if leader.is_in_db():
        return set()

    leader.save()

    for comp in leader.companies:
        leader.company.connect(CompanyDB.nodes.get(name=comp.name, address=comp.address, info=comp.info))

    for company_name in companies_table:
        company = CompanyDB(name=clean(company_name.find('a').get_text()))
        company_link = company_name.find('a').get('href')
        company.link = 'http:' + company_link if not company_link.startswith('http') else company_link
        company.leaders.update({leader})
        companies.update({company})
    return companies


def parse_data(companies):
    leaders = set()
    count = 0
    count2 = 0

    while len(companies) != 0:
        for x in range(len(companies) // RPS + 1):
            for company in load_pages(list(companies)[x * RPS:(x + 1) * RPS]):
                leaders.update(obtain_leaders(company))
                count2 += 1
                if count2 % 100 == 0:
                    print('Processed {} 100 pages'.format(count2 // 100))
            time.sleep(5)
        companies = set()

        count += 1
        print('Pass {} half-way ended, {} leaders to parse'.format(str(count), str(len(leaders))))

        for x in range(len(leaders) // RPS + 1):
            for leader in load_pages(list(leaders)[x * RPS:(x + 1) * RPS]):
                companies.update(obtain_companies(leader))
                count2 += 1
                if count2 % 100 == 0:
                    print('Processed {} 100 pages'.format(count2 // 100))
            time.sleep(5)
        count2 = 0
        leaders = set()
        print('Pass {} ended, {} companies to parse'.format(str(count), str(len(companies))))


db.cypher_query('MATCH (n) DETACH DELETE n;')
with open(INPUT_CSV, newline='') as csv_file:
    csv_data = csv.reader(csv_file)
    header = next(csv_data)
    csv_sets = {CompanyDB(link=COMPANY_URL.format(str(row[0]))) for row in csv_data}
parse_data(csv_sets)
