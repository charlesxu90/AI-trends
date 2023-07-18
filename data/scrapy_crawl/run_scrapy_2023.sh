# create project
# scrapy startproject scrapy_crawl

# create spider
# cd scrapy_raw
# scrapy genspider scrapy_openreview api.openreview.net

# run spider
# params: year='2023', source='ICLR', type='oral', venue='ICLR+2023+notable+top+25%25', invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission'

# === 2023 === #
# ICLR
# scrapy crawl scrapy_openreview -o 2023/iclr2023-oral.json  -a year=2023 -a source=ICLR -a type=oral -a venue='ICLR+2023+notable+top+5%25' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2023/iclr2023-spotlight.json  -a year=2023 -a source=ICLR -a type=spotlight -a venue='ICLR+2023+notable+top+25%25' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2023/iclr2023-poster1.json  -a year=2023 -a source=ICLR -a type=poster -a venue='ICLR+2023+poster' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2023/iclr2023-poster2.json  -a year=2023 -a source=ICLR -a type=poster -a venue='ICLR+2023+poster' -a invitation='ICLR.cc%2F2023%2FConference%2F-%2FBlind_Submission' -a offset=1000 --nolog


# scrapy genspider scrapy_openreview2 api2.openreview.net
# ICML
# Interactive Learning with Implicit Human Feedback Workshop at ICML 2023 (ILHF)
scrapy crawl scrapy_openreview2 -o 2023/icml2023-ILHF-poster.json  -a year=2023 -a source=ICML -a type=poster -a venue='ILHF%20Workshop%20ICML%202023' -a details='replyCount%2Cinvitation%2Coriginal' --nolog

# ICML 2023
# scrapy crawl scrapy_openreview2 -o 2023/icml2023-oral.json  -a year=2023 -a source=ICML -a type=spotlight -a venue='DARL+2022+Spotlight' -a invitation='ICML.cc%2F2022%2FWorkshop%2FDARL%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview2 -o 2023/icml2023-poster.json  -a year=2023 -a source=ICML -a type=poster -a venue='DARL+2022' -a invitation='ICML.cc%2F2022%2FWorkshop%2FDARL%2F-%2FBlind_Submission' --nolog

