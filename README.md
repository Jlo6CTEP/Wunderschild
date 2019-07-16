Wunderschild Python dev
===

The task was to implement web-scrapper of site https://www.verif.com

The full task is available [here](https://drive.google.com/open?id=1rn0cJONUDkWGlkUbJLBSUIJrq19Pgvch), and initial data can be found in [this document](https://drive.google.com/open?id=1bsskPwp0A5ImnS_l77w85DQ_SslQ2uxeQyhuocv4pWE)

## Installation

#### Neo4j database
* Since I'm going to work with entities and relations, Graph DBMS will be the best choice.
* Installation:
    * Via [choco](https://chocolatey.org/): `choco install neo4j-community`
    * Via the official [site](https://neo4j.com/)
    * Password - neo
---
#### Cloning my repository
Now it is time to clone my project repo
* `git clone https://github.com/Jlo6CTEP/Wunderschild`
---
#### Python packages
The project utilizes python 3.7 version
* All the dependencies can be installed via `pip install -r requirements.txt`

#### Startup
When all the preparations are done, the project can be runned via `python .\test_task\Parser.py`

Code
---

#### Interaction with DB
* Neo4j library neomodel uses OGM (object-graph mapping)
* I set up a pair of classes for Company and Leader types of entities
    This one for Company
    ```python
    class CompanyDB(StructuredNode):
        link = StringProperty()
        name = StringProperty(required=True)
        address = StringProperty()
        info = StringProperty()
        leaders = None
    ```
    This one for Leader
    ```python
    class LeaderDB(StructuredNode):
        link = StringProperty()
        name = StringProperty(required=True)
        b_date = DateProperty()
        companies = None
    ```
* I set up couple of magic methods (`__eq__` and `__hash__`) to take advantage of Python's sets and make getting rid of duplicating companies/leaders in sets fast and efficient
* And date conversion for my LeaderDB class:
    ```python
        def set_b_date(self, b_date):
        if b_date is None:
            return
        b_date = b_date.replace(' ', '')
        month = re.search('([^\\W\\d_])+', b_date).group(0)
        numeric_data = b_date.replace(month, ' ').split(' ')
        self.b_date = date(int(numeric_data[1]), MONTHS[month], int(numeric_data[0]))
    ```
    Where `MONTHS` is dict to perform textual-numeric month conversion.
    
* That's about it for DBMS, now to actual algorithm and parsing
---
#### Algorithm
* The idea is the following
    *    there are two functions:
            *    `obtain_companies()`, which takes a LeaderDB object as an argument, and returns a list of companies of this leader
                    Each company in this list have given LeaderDB object in its `leaders` attribute
                    This way i can track relationships between companies and leaders
            *    `obtain_leaders()`, which takes CompanyDB as an argument and returns list of leaders of this company
                    Each leader in this list (similarly to `obtain_companies()`) have given CompanyDB object in its `companies` attribute
                    
    * Now as you can see, if I will apply these functions in an **alternating fashion** to return of a previous function like this:
        *    obtain_leaders(obtain_companies(obtain_leaders(initial_companies)))
 
        it will be **The Breadth-first Graph Traversal**:
        Starting from some initial Company, I will find all its Leaders, then all Companies of these Leaders, and so forth.
    * While  executing this function it will push nodes to DB and set up some connections between nodes to have nice graph representation (and also free RAM on my machine)

---
#### Parsing
* The first step will be to parse these SIRENs numbers from the file and convert them into links.
    * For verif.com, structure of the link is www.verif.com/societe/SIREN_number_here/
    * So I just create bunch of CompanyDB instances with this links and pass them to `parse_data()`
    ```python
    with open(INPUT_CSV, newline='') as csv_file:
        csv_data = csv.reader(csv_file)
        header = next(csv_data)
        csv_sets = {CompanyDB(link=COMPANY_URL.format(str(row[0]))) for row in csv_data}
    parse_data(csv_sets)
    ```

* Actual data parsing
    * First I tried fetching pages sequentially, speed was about 1 page/sec which is not good
    * So I went ahead and start using `aiohttp` library for sending a lot of requests asynchronously like this:

    ```python
    # send 1 request asynchronously
    # couple of exception handlers to resend requests with 403 return code
    # they appears because server think that I'm a DoSer
    async def fetch(url, company, session):
        while 1:
            try:
                async with session.get(db_object.link, raise_for_status=True) as response:
                    print(response.headers.get("DATE"))
                    return await response.read(), db_object
            except (aiohttp.ClientResponseError, aiohttp.ClientConnectorError):
                await asyncio.sleep(1)
            except aiohttp.ClientOSError as e:
                await asyncio.sleep(1)
    ```
    
    ```python
    # send a list of requests
    # objects with empty links are ignored
    # because if they are on the site somewhere, they will be added at last
    # And if not - then they probably shouldn't be here
    async def run(object_list):
        tasks = []

        async with ClientSession(auto_decompress=True) as session:
            for obj in object_list:
                if obj.link == '':
                    continue
                task = asyncio.ensure_future(fetch(obj, session))
                tasks.append(task)
            return await asyncio.gather(*tasks)
    ```
    
    ```python
    def load_pages(objects):
        loop = asyncio.get_event_loop()
        future = asyncio.ensure_future(run(objects))
        return loop.run_until_complete(future)
    ```
    * This is pretty standart "textbook" example from the documentation, and it has a speed of 30 pages/second
    * Return of `load_pages()` is a list of 2-element tuples: 
        * response body
        * company object


* Now its time to look at the code
    * I will show only `obtain_companies()` because `obtain_leaders()` works similarly with the only difference that it parses company-specific data instead of leader-specific
    *  I also set up a couple of helper functions, to clean HTML tags easily:
        * `clean()` removes duplicating tabs, new-lines, and other invisible symbols and replaces them with spaces
        * `clean_name()` does the same, plus removes M or Mmm prefix
        * `title()` capitalizes every word in the sentence
    *  First check if such leader was found - if not, return empty set (which means that this leader has no companies)
        ```python
        leader_page = leader_zip[0]

        soup = BeautifulSoup(leader_page.decode('ISO-8859-1'), 'lxml')
        main_table = soup.find(class_='profile')

        if main_table is None:
            return set()
        ```
    * Then, extract information about this leader using `BeautifulSoup` library.
        ```python
        date = extract_date.search(main_table.find(class_='text-content').get_text())

        if date is None:
            b_date = None
        else:
            b_date = date.group(0)
        leader.set_b_date(b_date)
        companies_table = main_table.find_all(class_='elt')

        if leader.is_in_db():
            return set()

        ```
    * after this step the leader should be saved to a database, and all his companies from `companies` attribute connected to this leader
        ```python
        leader.save()

        for comp in leader.companies:
            leader.company.connect(CompanyDB.nodes.get(name=comp.name, address=comp.address, info=comp.info))
        ```
    *    Now, when the leader is in db and is connected to its companies (this information comes from `obtain_leader()` function, it is time to obtain companies of this leader and return them!
            ```python
            for company_name in companies_table:
                company = CompanyDB(name=clean(company_name.find('a').get_text()))
                company_link = company_name.find('a').get('href')
                company.link = 'http:' + company_link if not company_link.startswith('http') else company_link
                company.leaders.update({leader})
                companies.update({company})
            return companies
            ```
---
#### Sites hate scrappers

*    Unfortunately, verif.com hates me as a scrapper really bad, and tries to make my life miserable:
        *    If I send a lot of requests in a short period of time, i.e. 1000 of them, it will start throwing 403 forbidden errors
        *    If I try to bypass this by retry with backoff time, it will start delaying my requests
        *    And finally, just block all my subnet for a couple of minutes.
*    There are two options on how to mitigate this problem, I can either:
        *    Slow down and be a "nice guy"
        *    Scrape me a few proxies, fake headers, use them and continue firing on all cylinders
*    Under these circumstances, proxies seem to be an overkill, so I decided to stick to being a "nice guy"
*    I'm trying to mix periods of network and CPU activity by fetching 100 pages, then processing them, again fetching and again processing, but unfortunately, site still blacklists me, so I added a little bit of delay between iterations, and now my speed is around 3-4 pages/second which is better than sequential, but **FAR** worse than blazing 30 pages/second with pure, unconfined async requests
                
---
#### Conclusion
I built me a nice little tool to scrape sites that utilizes the powers of:
*    Node4j Graph DB
*    Asyncio python library
*    BeautifulSoup parser
