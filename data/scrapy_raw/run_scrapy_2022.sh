# create project
# scrapy startproject openreview

# create spider
# cd openreview
# scrapy genspider iclr2022 api.openreview.net

# run spider
# params: year='2022', source='ICLR', type='oral', venue='ICLR+2022+notable+top+25%25', invitation='ICLR.cc%2F2022%2FConference%2F-%2FBlind_Submission'

# === 2022 === #
### ICLR ###
# scrapy crawl scrapy_openreview -o 2022/iclr2022-oral.json  -a year=2022 -a source=ICLR -a type=oral -a venue='ICLR+2022+Oral' -a invitation='ICLR.cc%2F2022%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/iclr2022-spotlight.json  -a year=2022 -a source=ICLR -a type=spotlight -a venue='ICLR+2022+Spotlight' -a invitation='ICLR.cc%2F2022%2FConference%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/iclr2022-poster1.json  -a year=2022 -a source=ICLR -a type=poster -a venue='ICLR+2022+Poster' -a invitation='ICLR.cc%2F2022%2FConference%2F-%2FBlind_Submission' --nolog

### ICML ### 
# Workshop on Spurious Correlations, Invariance and Stability (SCIS)
# scrapy crawl scrapy_openreview -o 2022/icml2022-SCIS-oral.json  -a year=2022 -a source=ICML -a type=oral -a venue='SCIS+2022+Oral' -a invitation='ICML.cc%2F2022%2FWorkshop%2FSCIS%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/icml2022-SCIS-poster.json  -a year=2022 -a source=ICML -a type=poster -a venue='SCIS+2022+Poster' -a invitation='ICML.cc%2F2022%2FWorkshop%2FSCIS%2F-%2FBlind_Submission' --nolog

# Workshop on Decision Awareness in Reinforcement Learning (DARL)
# scrapy crawl scrapy_openreview -o 2022/icml2022-DARL-oral.json  -a year=2022 -a source=ICML -a type=spotlight -a venue='DARL+2022+Spotlight' -a invitation='ICML.cc%2F2022%2FWorkshop%2FDARL%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/icml2022-DARL-poster.json  -a year=2022 -a source=ICML -a type=poster -a venue='DARL+2022' -a invitation='ICML.cc%2F2022%2FWorkshop%2FDARL%2F-%2FBlind_Submission' --nolog

# Workshop on Shift Happens
# scrapy crawl scrapy_openreview -o 2022/icml2022-Shift_Happens-oral.json  -a year=2022 -a source=ICML -a type=oral -a venue='Shift+Happens+2022+ContributedTalk' -a invitation='ICML.cc%2F2022%2FWorkshop%2FShift_Happens%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/icml2022-Shift_Happens-poster.json  -a year=2022 -a source=ICML -a type=poster -a venue='Shift+Happens+2022+Poster' -a invitation='ICML.cc%2F2022%2FWorkshop%2FShift_Happens%2F-%2FBlind_Submission' --nolog

# Workshop on Knowledge Retrieval and Language Models (KRLM)
# scrapy crawl scrapy_openreview -o 2022/icml2022-KRLM.json  -a year=2022 -a source=ICML -a type=poster -a venue='ICML+2022+Workshop+KRLM+' -a invitation='ICML.cc%2F2022%2FWorkshop%2FKRLM%2F-%2FBlind_Submission' --nolog

# Workshop on AI for Agent-Based Modelling (AI4ABM)
# scrapy crawl scrapy_openreview -o 2022/icml2022-AI4ABM-oral.json  -a year=2022 -a source=ICML -a type=oral -a venue='AI4ABM+2022+Oral' -a invitation='ICML.cc%2F2022%2FWorkshop%2FAI4ABM%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/icml2022-AI4ABM-spotlight.json  -a year=2022 -a source=ICML -a type=spotlight -a venue='AI4ABM+2022+Spotlight' -a invitation='ICML.cc%2F2022%2FWorkshop%2FAI4ABM%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/icml2022-AI4ABM-poster.json  -a year=2022 -a source=ICML -a type=poster -a venue='AI4ABM+2022+Poster' -a invitation='ICML.cc%2F2022%2FWorkshop%2FAI4ABM%2F-%2FBlind_Submission' --nolog

# Workshop on AI for Science (AI4Science)
# scrapy crawl scrapy_openreview -o 2022/icml2022-AI4Science-oral.json  -a year=2022 -a source=ICML -a type=oral -a venue='ICML-AI4Science+Oral' -a invitation='ICML.cc%2F2022%2FWorkshop%2FAI4Science%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/icml2022-AI4Science-poster.json  -a year=2022 -a source=ICML -a type=poster -a venue='ICML-AI4Science+Poster' -a invitation='ICML.cc%2F2022%2FWorkshop%2FAI4Science%2F-%2FBlind_Submission' --nolog

# Workshop on Pre-training: Perspectives, Pitfalls, and Paths Forward
# scrapy crawl scrapy_openreview -o 2022/icml2022-Pre-training-oral.json  -a year=2022 -a source=ICML -a type=oral -a venue='ICML+2022+Pre-training+Workshop+ContributedTalk' -a invitation='ICML.cc%2F2022%2FWorkshop%2FPre-Training%2F-%2FBlind_Submission' --nolog
# scrapy crawl scrapy_openreview -o 2022/icml2022-Pre-training-poster.json  -a year=2022 -a source=ICML -a type=poster -a venue='ICML+2022+Pre-training+Workshop' -a invitation='ICML.cc%2F2022%2FWorkshop%2FPre-Training%2F-%2FBlind_Submission' --nolog


### NIPS ### 
# scrapy crawl scrapy_openreview -o 2022/nips2022-accept1.json  -a year=2022 -a source=NIPS -a type=poster -a venue='NeurIPS+2022+Accept' -a invitation='NeurIPS.cc%2F2022%2FConference%2F-%2FBlind_Submission' --nolog -a offset=0 
# scrapy crawl scrapy_openreview -o 2022/nips2022-accept2.json  -a year=2022 -a source=NIPS -a type=poster -a venue='NeurIPS+2022+Accept' -a invitation='NeurIPS.cc%2F2022%2FConference%2F-%2FBlind_Submission' --nolog -a offset=1000 
# scrapy crawl scrapy_openreview -o 2022/nips2022-accept3.json  -a year=2022 -a source=NIPS -a type=poster -a venue='NeurIPS+2022+Accept' -a invitation='NeurIPS.cc%2F2022%2FConference%2F-%2FBlind_Submission' --nolog -a offset=2000 