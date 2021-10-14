"""收集网上书籍，用于构建语料库"""

import os
import re
import time
import random
from urllib.parse import urljoin

import opencc
import requests
from parsel import Selector

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

class Gutenberg:
    def __init__(self):
        self.book_dir = 'books/gutenberg'
        os.makedirs(self.book_dir, exist_ok=True)
        self.converter = opencc.OpenCC('t2s.json')
        
    def collect(self):
        """收集project gutenberg上面的中文书籍"""
        print('gutenberg收集启动') 
        dir_url = 'https://www.gutenberg.org/browse/languages/zh'
        r = requests.get(dir_url, headers=HEADERS)
        doc = Selector(r.content.decode('utf-8'))
        urls = doc.xpath('//div[contains(@class, "pgdbbylanguage")]//ul/li/a/@href').getall()
        
        for url in urls:
            id = url[8:]
            book_path = os.path.join(self.book_dir, id + '.txt')
            if os.path.exists(book_path):
                continue
                
            print('开始下载编号%s' %id)
            t0 = time.time()
            url = urljoin(dir_url, url)
            r = requests.get(url, headers=HEADERS)
            doc = Selector(r.content.decode('utf-8'))
            txt_url = doc.xpath('//td/a[contains(text(), "Plain Text UTF-8")]/@href').get()
            
            txt_url = urljoin(r.url, txt_url)
            r = requests.get(txt_url, headers=HEADERS)
            r.raise_for_status()
            open(book_path, 'wb').write(r.content)

            print('下载结束，耗时：%d秒' %(time.time() - t0))
        
    def preprocess(self):
        files = os.listdir(self.book_dir)
        random.shuffle(files)
        for file in files:
            doc = open(os.path.join(self.book_dir, file)).read()
            n_han = len(re.findall(r'[\u4e00-\u9fa5]', doc))
            if n_han > 50000:
                doc = ''.join(re.findall(r'([\u4e00-\u9fa5].*?)[a-zA-Z0-9]', doc, flags=re.DOTALL))
                doc = self.converter.convert(doc)
                doc = re.sub(r'\n{2,}', '<|eos|>', doc)
                doc = re.sub(r'\s+', '', doc)
                doc = doc.replace('<|eos|>', '\n')
                print(repr(doc))
                print(file)
                input('continue?')
            
if __name__ == '__main__':
    Gutenberg().preprocess()

