import logging
import random
import time
import hashlib
import os
import datetime
from urllib.parse import urljoin, urlparse
from multiprocessing import Process, Queue

import requests
import pymongo
import timeout_decorator
from pymongo import MongoClient
from diskcache import Cache
from newspaper import Article
from w3lib.url import canonicalize_url

logging.basicConfig(format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s', level=logging.INFO)

NEXT_URLS = Queue()
LINKS = Queue()
START_URL = 'https://www.zhihu.com/explore'
DB_NAME = 'article'
COL_NAME = 'crawl2'
MONGO_HOST = '10.10.9.185'
MONGO_USERNAME = 'admin'
MONGO_PASSWORD = 'admin'

def get_mongo_obj():
    mongo_client = MongoClient(MONGO_HOST, username=MONGO_USERNAME, password=MONGO_PASSWORD)
    db = eval('mongo_client.%s' %DB_NAME)
    collection = eval('mongo_client.%s.%s' %(DB_NAME, COL_NAME))
    return mongo_client, db, collection

class CrawlArticle:
    def __init__(self):
        self.headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.DENY_EXTENSIONS = [
            # archives
            '7z', '7zip', 'bz2', 'rar', 'tar', 'tar.gz', 'xz', 'zip',
            # audio
            'mp3', 'wma', 'ogg', 'wav', 'ra', 'aac', 'mid', 'au', 'aiff',
            # video
            '3gp', 'asf', 'asx', 'avi', 'mov', 'mp4', 'mpg', 'qt', 'rm', 'swf', 'wmv',
            'm4a', 'm4v', 'flv', 'webm',
            # office suites
            'xls', 'xlsx', 'ppt', 'pptx', 'pps', 'doc', 'docx', 'odt', 'ods', 'odg',
            'odp',
            # other
            'css', 'svl', 'pdf', 'exe', 'bin', 'rss', 'dmg', 'iso', 'apk', 'ipa',
            #image
            'jpg', 'png',
        ]
        self.queue_max_size = 3000000

    def mongo_init(self):
        view_name = COL_NAME + '_view'
        self.mongo_client, self.db, self.collection = get_mongo_obj()
        if view_name not in self.db.list_collection_names():
            self.db.command({
                'create': view_name,
                'viewOn': COL_NAME,
                'pipeline': [
                    {'$match': {'n_char': {'$gt': 500}}}
                ]
            })

    def link_allowed(self, link):
        hostname = None
        try:
            parsed_url = urlparse(link)
            hostname = parsed_url.hostname
            if os.path.splitext(parsed_url.path)[1].lower()[1:] in self.DENY_EXTENSIONS \
               or not hostname.endswith('zhihu.com'):
                return False, hostname
            return True, hostname
        except Exception as e:
            logging.error('[%s]URL处理出错: %s' %(link, e))
            return False, hostname
        
    @timeout_decorator.timeout(10)
    def download_and_parse(self, url):
        article = Article(url=url, language='zh', fetch_images=False)
        article.download()
        article.parse()
        return article
        
    def parse(self, url):
        logging.info('爬取[%s]' %url)
        
        article = self.download_and_parse(url)
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        try:
            self.collection.insert_one({
                '_id': url_hash,
                'links': [{'type': 'text/html', 'href': url}],
                'authors': [{'name': ele} for ele in article.authors],
                'tags': [],
                'title': article.title, 
                'summary': article.text,
                'n_char': len(article.text),
                'updated': article.publish_date if article.publish_date else datetime.datetime.now(),
            })
        except pymongo.errors.DuplicateKeyError:
            pass
        
        if NEXT_URLS.qsize() > self.queue_max_size:
            logging.info('待爬队列大小超过%s，停止插入' %self.queue_max_size)
        else:
            links = set()
            for link in article.doc.xpath('//@href'):
                link = urljoin(url, link)
                link = canonicalize_url(link, keep_fragments=False)
                links.add(link)
            
            for link in links:
                allowed, hostname = self.link_allowed(link)
                if allowed:
                    LINKS.put(link)
        
    def run(self):
        self.mongo_init()
        while True:
            url = NEXT_URLS.get()
                
            t0 = time.time()
            try:
                self.parse(url)
            except Exception as e:
                logging.error('[%s]解析错误: %s' %(url, e))
            logging.info('单条耗时: %.4f秒' %(time.time() - t0))

def links_to_queue():
    mongo_client, db, collection = get_mongo_obj()
    t0 = time.time()
    dupefilter = set()
    
    while True:
        if time.time() - t0 > 10:
            logging.info('去重队列数量：%s' %len(dupefilter))
            t0 = time.time()
            
        link = LINKS.get()
        if link not in dupefilter:
            dupefilter.add(link)
            url_hash = hashlib.md5(link.encode('utf-8')).hexdigest()
            if not collection.find_one({'_id': url_hash}):
                NEXT_URLS.put(link)

def get_start_url(collection):
    count = collection.count_documents({})
    if count == 0:
        return START_URL
    else:
        return collection.find_one(skip=random.randint(0, count-1))['links'][0]['href']

def manager():
    mongo_client, db, collection = get_mongo_obj()
    while True:
        time.sleep(10)
        n_urls = NEXT_URLS.qsize()
        logging.info('待爬队列数量: %s' %n_urls)
        if n_urls == 0:
            NEXT_URLS.put(get_start_url(collection))

if __name__ == '__main__':
    NEXT_URLS.put(START_URL)
    ps = []
    for i in range(1):
        p = Process(target=CrawlArticle().run)
        p.start()
        ps.append(p)
    
    link_p = Process(target=links_to_queue)
    link_p.start()
    ps.append(link_p)
    
    manager_p = Process(target=manager)
    manager_p.start()
    ps.append(manager_p)
    
    for p in ps:
        p.join()
        
