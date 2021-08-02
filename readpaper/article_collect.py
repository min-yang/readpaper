"""根据传递的目录URL，爬取目录下的所有文章。
待改进的地方：
1、各域名的爬取并发进行
2、根据域名对应的IP地址进行限流，控制对特定IP的访问频率
"""

#python3内置库
import time
import hashlib
from urllib.parse import urljoin

#第三方库
import requests
import cchardet
from parsel import Selector
from pymongo import MongoClient

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
    
def get_article(dir_url, proposer, record_xpath, title_xpath=None, article_xpath=None):
    client = MongoClient()
    r = my_get(dir_url)
    doc = byte_to_selector(r.content)
    records = doc.xpath(record_xpath).getall()
    for record in records:
        article_url = urljoin(dir_url, record)
        r = my_get(article_url)
        doc = byte_to_selector(r.content)
        
        url_hash = hashlib.md5(bytes(article_url, encoding='utf-8')).hexdigest()
        data = {'_id': url_hash, 'url': article_url, 'proposer': proposer, 'title': '', 'article': ''}
        for part, part_xpath in [
            ('title', title_xpath),
            ('article', article_xpath)
        ]:
            if part_xpath:
                text = ' '.join(doc.xpath(part_xpath).getall())
                data[part] = text
        
        if data['title'] and data['article']: #必须不为空的部分
            try:
                client.article.crawl.insert_one(data)
            except DuplicateKeyError:
                pass
        
if __name__ == '__main__':
    #函数参数例子
    get_article('http://cpc.people.com.cn/GB/87228/index.html',
        proposer='admin',
        record_xpath='//div[@class="fl"]//li/a/@href',
        title_xpath='//h1/text()',
        article_xpath='//div[@class="show_text"]/p/text()',
    )
    
