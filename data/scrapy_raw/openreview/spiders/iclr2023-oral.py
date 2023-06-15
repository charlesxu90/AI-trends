import scrapy
import json


class Iclr2023Spider(scrapy.Spider):
    name = "iclr2023-oral"
    allowed_domains = ["api.openreview.net"]

    def __init__(self, year='2023', source='ICLR', type='oral', venue='ICLR+2023+notable+top+5%25', invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission', offset=0, limit=1000):
        """
        year: 2023
        source: ICLR, ICML, NeurIPS, CVPR
        type: oral, spotlight, and poster
        venue: e.g. ICLR+2023+notable+top+25%25
        invitation: e.g. ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission
        limit: 1000
        """
        self.start_urls = [f"https://api.openreview.net/notes?content.venue={venue}&details=replyCount&offset={offset}&limit={limit}&invitation={invitation}"]
        self.year = year
        self.source = source
        self.type = type

    def parse(self, response):
        result = json.loads(response.text)
        print(f"==== Totally: {result.get('count')} records====")
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