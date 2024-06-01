import scrapy
import json


class ScrapyOpenreview2Spider(scrapy.Spider):
    name = "scrapy_openreview2"
    allowed_domains = ["api2.openreview.net"]

    def __init__(self, year='2023', source='ICLR', type='oral', 
                #  invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission', 
                 details='replyCount', 
                 venue=None, 
                 domain=None,
                 offset=0, limit=1000):
        """
        year: 2023
        source: ICLR, ICML, NeurIPS, CVPR
        type: oral, spotlight, and poster
        venue: e.g. ICLR+2023+notable+top+25%25
        # invitation: e.g. ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission
        offset: default 0, need to be changed if more than 1000 records
        limit: 1000
        """
        urls = []
        if venue:
            urls.append(f"content.venue={venue}")
        urls.append(f"details={details}")
        urls.append(f"offset={offset}")
        urls.append(f"limit={limit}")
        if domain is not None:
            urls.append(f"domain={domain}")
        # urls.append(f"invitation={invitation}")
        
        self.start_urls = ["https://api2.openreview.net/notes?" + '&'.join(urls)]
        self.year = year
        self.source = source
        self.type = type

    def parse(self, response):
        result = json.loads(response.text)
        print(f"\n\n==== Totally: {result.get('count')} records====")
        # Download: 'title', 'year', 'source', 'authors', 'class', 'keywords', 'abstract', 'pdf_link'
        for data in result.get("notes"):
            title = data.get("content").get('title').get('value')
            print(title)
            authors = str(data.get("content").get('authors').get('value')).replace('\"', '').replace("[", "").replace("]", "")
            try:
                keywords = data.get("content").get('keywords').get('value').replace('\"', '').replace("[", "").replace("]", "")
            except:
                keywords = ""
            abstract = data.get("content").get('abstract').get('value')
            try:
                pdf_link = data.get("content").get('pdf').get('value')
            except:
                pdf_link = ""

            dct = {'title': title, 
                   'year': self.year, 
                   'source': self.source, 
                   'authors': authors,
                   'class': self.type,
                   'keywords': keywords, 
                   'abstract': abstract, 
                   'pdf_link': pdf_link}
            yield dct