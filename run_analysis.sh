## Activate environment
conda activate AI-trend-env

## Test the latest API using Postman
# 1. analysis the website to obtain the API of from OpenReview or Website (through inspecting the network), 
#   e.g. https://api2.openreview.net/notes?content.venue=ICLR%202024%20oral&details=replyCount%2Cpresentation&domain=ICLR.cc%2F2024%2FConference&limit=25&offset=0
# 2. test the API using Postman

## Retrieve the latest data from the API using Scrapy
# Follow this bash script: data/scrapy_crawl/run_scrapy_2024.sh
# Need to update the spider following the latest API
# Pay attention to the first file, as it usually contains the multiple copy of data

## Merge json files through processing
# Using the process_scrapy.ipynb

## Analyze the topics in the data
# Using the 1.assign_topics.ipynb
# 1. Filter the keywords, and manually check the topics
# 2. assign topics to the papers
# 3. Analyze the trend of the topics, including the top 5 topics, top 5 emerging topics, and top 5 fading topics

## Analyze the popular topics in the data
# Using the 2.popular_topics.ipynb
# 1. Get the paper citation of papers in the popular topics, including top 5 topics and emergent topics


