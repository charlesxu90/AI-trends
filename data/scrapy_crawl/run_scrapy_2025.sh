# create project
# scrapy startproject scrapy_crawl

# create spider
# cd scrapy_raw
# scrapy genspider scrapy_openreview api.openreview.net

# run spider
# params: year='2025', source='ICLR', type='oral', venue='ICLR%202025%20oral', details='replyCount%2Cpresentation', domain='ICLR.cc%2F2025%2FConference'

# === 2025 === #
# ICLR
# scrapy crawl scrapy_openreview2 -o 2025/iclr2025-oral.json  -a year=2025 -a source=ICLR -a type=oral -a venue='ICLR%202025%20Oral' -a details='replyCount%2Cpresentation' -a domain='ICLR.cc%2F2025%2FConference' --nolog
# scrapy crawl scrapy_openreview2 -o 2025/iclr2025-spotlight.json  -a year=2025 -a source=ICLR -a type=spotlight -a venue='ICLR%202025%20Spotlight' -a details='replyCount%2Cpresentation' -a domain='ICLR.cc%2F2025%2FConference' --nolog
scrapy crawl scrapy_openreview2 -o 2025/iclr2025-poster1.json  -a year=2025 -a source=ICLR -a type=poster -a venue='ICLR%202025%20Poster' -a details='replyCount%2Cpresentation' -a domain='ICLR.cc%2F2025%2FConference' --nolog -a offset=0  -a limit=1000 
scrapy crawl scrapy_openreview2 -o 2025/iclr2025-poster2.json  -a year=2025 -a source=ICLR -a type=poster -a venue='ICLR%202025%20Poster' -a details='replyCount%2Cpresentation' -a domain='ICLR.cc%2F2025%2FConference' --nolog -a offset=1000  -a limit=1000 
scrapy crawl scrapy_openreview2 -o 2025/iclr2025-poster3.json  -a year=2025 -a source=ICLR -a type=poster -a venue='ICLR%202025%20Poster' -a details='replyCount%2Cpresentation' -a domain='ICLR.cc%2F2025%2FConference' --nolog -a offset=2000  -a limit=1000 
scrapy crawl scrapy_openreview2 -o 2025/iclr2025-poster4.json  -a year=2025 -a source=ICLR -a type=poster -a venue='ICLR%202025%20Poster' -a details='replyCount%2Cpresentation' -a domain='ICLR.cc%2F2025%2FConference' --nolog -a offset=3000  -a limit=1000 

# scrapy genspider scrapy_openreview2 api2.openreview.net
# ICML
# scrapy crawl scrapy_openreview2 -o 2025/icml2025-oral.json  -a year=2025 -a source=ICML -a type=oral -a venue='ICML%202025%20Oral' -a details='ICML%202025%20Oral' -a domain='ICML.cc%2F2025%2FConference' --nolog
# scrapy crawl scrapy_openreview2 -o 2025/icml2025-spotlight.json  -a year=2025 -a source=ICML -a type=spotlight -a venue='ICML%202025%20Spotlight' -a domain='ICML.cc%2F2025%2FConference' --nolog
# scrapy crawl scrapy_openreview2 -o 2025/icml2025-poster1.json  -a year=2025 -a source=ICML -a type=poster -a venue='ICML%202025%20Poster' -a domain='ICML.cc%2F2025%2FConference'  --nolog -a limit=1000 
# scrapy crawl scrapy_openreview2 -o 2025/icml2025-poster2.json  -a year=2025 -a source=ICML -a type=poster -a venue='ICML%202025%20Poster' -a domain='ICML.cc%2F2025%2FConference' --nolog -a offset=1000 -a limit=1000 
# scrapy crawl scrapy_openreview2 -o 2025/icml2025-poster3.json  -a year=2025 -a source=ICML -a type=poster -a venue='ICML%202025%20Poster' -a domain='ICML.cc%2F2025%2FConference' --nolog -a offset=2000 -a limit=1000 

## NIPS
# scrapy crawl scrapy_openreview2 -o 2025/nips2025-oral.json  -a year=2025 -a source=NIPS -a type=oral -a venue='NeurIPS%202025%20oral' -a details='replyCount%2Cpresentation' --nolog -a offset=0
# scrapy crawl scrapy_openreview2 -o 2025/nips2025-spotlight.json  -a year=2025 -a source=NIPS -a type=spotlight -a venue='NeurIPS%202025%20spotlight' -a details='replyCount%2Cpresentation' --nolog -a offset=0
# scrapy crawl scrapy_openreview2 -o 2025/nips2025-poster1.json  -a year=2025 -a source=NIPS -a type=poster -a venue='NeurIPS%202025%20poster' -a details='replyCount%2Cpresentation' --nolog -a offset=0 -a limit=1000 
# scrapy crawl scrapy_openreview2 -o 2025/nips2025-poster2.json  -a year=2025 -a source=NIPS -a type=poster -a venue='NeurIPS%202025%20poster' -a details='replyCount%2Cpresentation' --nolog -a offset=1000
# scrapy crawl scrapy_openreview2 -o 2025/nips2025-poster3.json  -a year=2025 -a source=NIPS -a type=poster -a venue='NeurIPS%202025%20poster' -a details='replyCount%2Cpresentation' --nolog -a offset=2000
# scrapy crawl scrapy_openreview2 -o 2025/nips2025-poster4.json  -a year=2025 -a source=NIPS -a type=poster -a venue='NeurIPS%202025%20poster' -a details='replyCount%2Cpresentation' --nolog -a offset=3000