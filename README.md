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
* Neo4j library neomodel uses OGM (object-graph mapping), so I set up pair of classes: LeaderDB and CompanyDB, for leaders and companies respectively.
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
* Actual data parsing
    * First I tried fetching pages sequentially, speed was about 1 page/sec which is not good
    * So I went ahead and start using `aiohttp` library for sending a lot of requests asynchronously with a speed of 30 pages/second
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
*    I was trying to mix periods of network and CPU activity by fetching 100 pages, then processing them, again fetching and again processing, but unfortunately, site still blacklisted me, so I added a little bit of delay between iterations, and now my speed is around 3-4 pages/second which is better than sequential, but **FAR** worse than blazing 30 pages/second with pure, unconfined async requests
                
---
#### Conclusion
I built me a nice little tool to scrape sites that utilizes the powers of:
*    Node4j Graph DB
*    Asyncio python library
*    BeautifulSoup parser
