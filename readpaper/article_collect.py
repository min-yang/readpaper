"""根据传递的目录URL，爬取目录下的所有文章。
待改进的地方：
1、各域名的爬取并发进行
2、根据域名对应的IP地址进行限流，控制对特定IP的访问频率
"""

#python3内置库
import re
import time
import hashlib
import datetime
from urllib.parse import urljoin

#第三方库
import requests
import cchardet
from parsel import Selector
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from diskcache import Cache

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

def my_get(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    time.sleep(1)
    return r
    
def byte_to_selector(content):
    text = content.decode(cchardet.detect(content[:1000])['encoding'])
    return Selector(text=text)
    
def get_article(dir_url, proposer, record_xpath, title_xpath, summary_xpath):
    client = MongoClient()
    dir_url_set = set()
    
    page=1
    while True:
        current_dir_url = dir_url.format(page=page)
        page += 1
        if current_dir_url in dir_url_set:
            break
        dir_url_set.add(current_dir_url)
        try:
            r = my_get(current_dir_url)
        except:
            break
            
        doc = byte_to_selector(r.content)
        records = doc.xpath(record_xpath).getall()
        hit = False
        success = 0
        for record in records:
            article_url = urljoin(current_dir_url, record)
            url_hash = hashlib.md5(bytes(article_url, encoding='utf-8')).hexdigest()
            if client.article.crawl.find_one({'_id': url_hash}, projection={}):
                continue
                
            hit = True
            try:
                r = my_get(article_url)
            except Exception as e:
                print('WARNING: [%s]请求失败:%s' %(article_url, e))
                continue
            doc = byte_to_selector(r.content)

            data = {
                '_id': url_hash, 
                'links': [{'type': 'text/html', 'href': article_url}], 
                'proposer': proposer, 
                'authors': [],
                'tags': [],
            }
            for part, part_xpath in [
                ('title', title_xpath),
                ('summary', summary_xpath)
            ]:
                text = ' '.join(doc.xpath(part_xpath).getall())
                if re.search(r'\w', text):
                    data[part] = text
            
            if data.get('title', False) and data.get('summary', False): #必须不为空的部分
                now = datetime.datetime.now().isoformat()
                data['updated'] = now
                client.article.crawl.insert_one(data)
                print('INFO: [%s]插入成功' %article_url)
                success += 1
            else:
                print('WARNING: [%s]标题为空或正文为空' %article_url)
        
        print('INFO: 目录[%s]，成功插入%s条，共%s条' %(current_dir_url, success, len(records)))
        if not hit:
            break

def run():
    cache = Cache('crawl_target')
    for key in cache:
        args = cache.get(key, None)
        if args:
            get_article(key, *args)
    
    print('INFO: 一轮爬取已结束，休眠1小时')
    time.sleep(3600) #更新频率低的话可以隔几天跑一轮，要视具体情况而定

if __name__ == '__main__':
    #任务调度示例
    cache = Cache('crawl_target')
    args = { #参数顺序proposer, record_xpath, title_xpath, summary_xpath 
        'http://cpc.people.com.cn/GB/87228/index{page}.html': [
            'admin',
            '//div[contains(@class, "fl")]//li/a/@href',
            '//h1/text()',
            '//div[@class="show_text"]/p/text()',
        ],
        'http://finance.people.com.cn/GB/70846/index{page}.html': [
            'admin',
            '//div[contains(@class, "fl")]//li/a/@href',
            '//h1/text()',
            '//div[contains(@class, "rm_txt_con")]/p/text()',
        ],
        'http://society.people.com.cn/GB/136657/index{page}.html': [
            'admin',
            '//div[contains(@class, "fl")]//li/a/@href',
            '//h1/text()',
            '//div[contains(@class, "rm_txt_con")]/p/text()',
        ]
    }
    
    for key in args:
        cache[key] = args[key]
        
    run()
    
