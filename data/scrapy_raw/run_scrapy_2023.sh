# create project
# scrapy startproject openreview

# create spider
# cd openreview
# scrapy genspider iclr2023 api.openreview.net

# run spider
# params: year='2023', source='ICLR', type='oral', venue='ICLR+2023+notable+top+25%25', invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission'

# === 2023 === #
# ICLR
scrapy crawl scrapy_openreview -o 2023/iclr2023-oral.json  -a year=2023 -a source=ICLR -a type=oral -a venue='ICLR+2023+notable+top+5%25' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2023/iclr2023-spotlight.json  -a year=2023 -a source=ICLR -a type=spotlight -a venue='ICLR+2023+notable+top+25%25' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2023/iclr2023-poster1.json  -a year=2023 -a source=ICLR -a type=poster -a venue='ICLR+2023+poster' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2023/iclr2023-poster2.json  -a year=2023 -a source=ICLR -a type=poster -a venue='ICLR+2023+poster' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' -a offset=1000 --nolog



