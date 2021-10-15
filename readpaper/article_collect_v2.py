import logging
import random
import time
import hashlib
import os
import datetime
from urllib.parse import urljoin, urlparse

import requests
import pymongo
import timeout_decorator
from pymongo import MongoClient
from diskcache import Cache
from newspaper import Article
from w3lib.url import canonicalize_url

logging.basicConfig(format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s', level=logging.INFO)

class CrawlArticle:
    def __init__(self):
        self.headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        }
        self.start_url = 'https://www.zhihu.com/'
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
        self.mongo_init()

    def mongo_init(self):
        col_name = 'crawl2'
        view_name = col_name + '_view'
        self.mongo_client = MongoClient('10.10.9.185', username='admin', password='admin')
        self.collection = eval('self.mongo_client.article.' + col_name)
        
        if view_name not in self.mongo_client.article.collection_names():
            self.mongo_client.article.command({
                'create': view_name,
                'viewOn': col_name,
                'pipeline': [
                    {'$match': {'n_char': {'$gt': 500}}}
                ]
            })

    def get_start_url(self):
        count = self.collection.count_documents({})
        if count == 0:
            return self.start_url
        else:
            return self.collection.find_one(skip=random.randint(0, count-1))['links'][0]['href']
        
    def link_allowed(self, link):
        try:
            parsed_url = urlparse(link)
            if os.path.splitext(parsed_url.path)[1].lower()[1:] in self.DENY_EXTENSIONS:
                return False
            return True
        except Exception as e:
            logging.error('[%s]URL处理出错: %s' %(link, e))
            return False
        
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
        
        if len(self.next_urls) > self.queue_max_size:
            logging.info('待爬队列大小超过%s，停止插入' %self.queue_max_size)
        else:
            links = set()
            for link in article.doc.xpath('//@href'):
                link = urljoin(url, link)
                link = canonicalize_url(link, keep_fragments=False)
                links.add(link)
            
            for link in links:
                url_hash = hashlib.md5(link.encode('utf-8')).hexdigest()
                if not self.collection.find_one({'_id': url_hash}, projection=['_id']) and self.link_allowed(link):
                    self.next_urls.add(link)
        
    def run(self):
        self.next_urls = set()
        self.next_urls.add(self.start_url)
        while True:
            try:
                url = self.next_urls.pop()
            except KeyError:
                logging.info('待爬队列为空，从库中随机选取起始地址')
                url = self.get_start_url()
            
            t0 = time.time()
            try:
                self.parse(url)
            except Exception as e:
                logging.error('[%s]解析错误: %s' %(url, e))
            logging.info('单条耗时: %.4f秒, 待爬队列数量: %s' %(time.time() - t0, len(self.next_urls)))

if __name__ == '__main__':
    CrawlArticle().run()
    
