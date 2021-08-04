from pymongo import MongoClient

mongo_client = MongoClient()

collection_dict = {
    'arxiv': mongo_client.paper.cs_paper_abs,
    'meiti': mongo_client.article.crawl,
}

collection_language = {
    'arxiv': 'EN',
    'meiti': 'CN',
}
