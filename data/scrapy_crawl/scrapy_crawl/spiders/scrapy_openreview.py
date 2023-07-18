import scrapy
import json


class ScrapyOpenreviewSpider(scrapy.Spider):
    name = "scrapy_openreview"
    allowed_domains = ["api.openreview.net"]

    def __init__(self, year='2023', source='ICLR', type='oral', 
                 invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission', details='replyCount', venue=None, 
                 offset=0, limit=1000):
        """
        year: 2023
        source: ICLR, ICML, NeurIPS, CVPR
        type: oral, spotlight, and poster
        venue: e.g. ICLR+2023+notable+top+25%25
        invitation: e.g. ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission
        offset: default 0, need to be changed if more than 1000 records
        limit: 1000
        """
        urls = []
        if venue:
            urls.append(f"content.venue={venue}")
        urls.append(f"details={details}")
        urls.append(f"offset={offset}")
        urls.append(f"limit={limit}")
        urls.append(f"invitation={invitation}")
        
        self.start_urls = ["https://api.openreview.net/notes?" + '&'.join(urls)]
        self.year = year
        self.source = source
        self.type = type

    def parse(self, response):
        result = json.loads(response.text)
        print(f"\n\n==== Totally: {result.get('count')} records====")
        # Download: 'title', 'year', 'source', 'authors', 'class', 'keywords', 'abstract', 'pdf_link'
        for data in result.get("notes"):
            title = data.get("content").get('title')
            print(title)
            authors = str(data.get("content").get('authors'))
            keywords = data.get("content").get('keywords')
            abstract = data.get("content").get('abstract')
            pdf_link = data.get("content").get('pdf')
            # lst = [title, year, source, authors, keywords, abstract, pdf_link]
            # yield lst
            dct = {'title': title, 
                   'year': self.year, 
                   'source': self.source, 
                   'authors': authors,
                   'class': self.type,
                   'keywords': keywords, 
                   'abstract': abstract, 
                   'pdf_link': pdf_link}
            yield dct