"""根据传递的目录URL，爬取目录下的所有文章。
待改进的地方：
1、各域名的爬取并发进行
2、根据域名对应的IP地址进行限流，控制对特定IP的访问频率
"""

#python3内置库
import re
import time
import hashlib
import logging
import datetime
from urllib.parse import urljoin

#第三方库
import requests
import cchardet
from parsel import Selector
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from diskcache import Cache

import lda_model
import doc2vec
from fetch_papers import pull_arxiv_paper
from utils import collection_dict

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
    text = content.decode(cchardet.detect(content[:1000])['encoding'], errors='ignore')
    return Selector(text=text)

def get_article(dir_url, start_page, proposer, record_xpath, title_xpath, summary_xpath):
    client = MongoClient()
    dir_url_set = set()
    
    page = start_page
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
        
        try: 
            doc = byte_to_selector(r.content)
        except Exception as e:
            logging.error('解码失败：%s' %e)
            continue
            
        records = doc.xpath(record_xpath).getall()
        success = 0
        for record in records:
            article_url = urljoin(current_dir_url, record)
            url_hash = hashlib.md5(bytes(article_url, encoding='utf-8')).hexdigest()
            if client.article.crawl.find_one({'_id': url_hash}, projection={}):
                continue
            
            if client.article.not_crawl.find_one({'_id': url_hash}, projection={}):
                 continue
            else:
                client.article.not_crawl.insert_one({'_id': url_hash, 'url': article_url})
            
            try:
                r = my_get(article_url)
            except Exception as e:
                logging.warning('[%s]请求失败:%s' %(article_url, e))
                continue
            try: 
                doc = byte_to_selector(r.content)
            except Exception as e:
                logging.error('[%s]解码失败：%s' %(article_url, e))
                continue

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
                text = '\n'.join(doc.xpath(part_xpath).getall())
                if re.search(r'\w', text):
                    data[part] = text
            
            if data.get('title', False) and data.get('summary', False) and len(data.get('summary', '')) > 50: #入库条件
                now = datetime.datetime.now().isoformat()
                data['updated'] = now
                client.article.crawl.insert_one(data)
                logging.debug('[%s]插入成功' %article_url)
                success += 1
            else:
                logging.warning('[%s]标题为空或正文内容太少' %article_url)
        
        logging.info('目录[%s]，成功插入%s条，共%s条' %(current_dir_url, success, len(records)))
        if success == 0:
            break

def run():
    t_start = time.time()
    one_day = 3600 * 24
    cache = Cache('crawl_target')
    
    while True:
        for key in cache:
            args = cache.get(key, None)
            if args:
                if len(args) == 1:
                    args = cache.get(args[0], None)
                    if not args:
                        logging.error('[%s]参数错误' %key)
                        continue
                get_article(key, *args)
        
        #一天检索一次arxiv论文库，同时更新下LDA模型和文档模型
        if time.time() - t_start > one_day:
            pull_arxiv_paper()
            t_start = time.time()
            for key in collection_dict:
                lda_model.main(key)
                doc2vec.main(key)
        
        logging.info('一轮爬取已结束，休眠1小时')
        time.sleep(3600) #更新频率低的话可以隔几天跑一轮，要视具体情况而定

if __name__ == '__main__':
    #任务调度示例
    cache = Cache('crawl_target')
    #人民网
    args = { #参数顺序start_page, proposer, record_xpath, title_xpath, summary_xpath
        'http://cpc.people.com.cn/GB/87228/index{page}.html': [
            1,
            'admin',
            '//div[contains(@class, "fl")]//li/a/@href',
            '//h1/text()',
            '//div[@class="show_text"]/p/text()',
        ],
        'http://finance.people.com.cn/GB/70846/index{page}.html': [
            1,
            'admin',
            '//div[contains(@class, "fl")]//li/a/@href',
            '//h1/text()',
            '//div[contains(@class, "rm_txt_con")]/p/text()',
        ],
        'http://society.people.com.cn/GB/136657/index{page}.html': [
            1,
            'admin',
            '//div[contains(@class, "fl")]//li/a/@href',
            '//h1/text()',
            '//div[contains(@class, "rm_txt_con")]/p/text()',
        ],
    }
    
    #光明网
    args['https://politics.gmw.cn/node_9844.htm'] = [
            1, #起始页码
            'admin',
            '//ul[contains(@class, "channel-newsGroup")]/li//a/@href',
            '//h1/text()',
            '//div[contains(@class, "u-mainText")]/p/text()',
    ]
    for dir_url in [
        'https://politics.gmw.cn/node_9840.htm',
        'https://politics.gmw.cn/node_9831.htm',
        'https://politics.gmw.cn/node_9828.htm',
        'https://politics.gmw.cn/node_9836.htm',
        'https://politics.gmw.cn/node_26858.htm',
        'https://world.gmw.cn/node_4661.htm',
        'https://world.gmw.cn/node_24177.htm',
        'https://world.gmw.cn/node_4485.htm',
        'https://world.gmw.cn/node_4696.htm',
        'https://world.gmw.cn/node_24179.htm',
        'https://world.gmw.cn/node_4660.htm',
        'https://guancha.gmw.cn/node_86599.htm',
        'https://guancha.gmw.cn/node_7292.htm',
        'https://guancha.gmw.cn/node_87838.htm',
        'https://guancha.gmw.cn/node_26275.htm',
        'https://theory.gmw.cn/node_10133.htm',
        'https://theory.gmw.cn/node_97957.htm',
        'https://theory.gmw.cn/node_47530.htm',
        'https://theory.gmw.cn/node_97958.htm',
        'https://theory.gmw.cn/node_97034.htm',
        'https://theory.gmw.cn/node_41267.htm',
        'https://culture.gmw.cn/node_10570.htm',
        'https://culture.gmw.cn/node_10572.htm',
        'https://culture.gmw.cn/node_10565.htm',
        'https://culture.gmw.cn/node_4369.htm',
        'https://culture.gmw.cn/node_10559.htm',
        'https://culture.gmw.cn/node_10250.htm',
        'https://culture.gmw.cn/node_40271.htm',
        'https://culture.gmw.cn/node_110874.htm',
    ]:
        args[dir_url] = ['https://politics.gmw.cn/node_9844.htm']
    
    args['https://guancha.gmw.cn/node_11273.htm'] = [
        1,
        'admin',
        '//p[contains(@class, "main_title")]/a/@href',
        '//h1/text()',
        '//div[contains(@class, "u-mainText")]/p/text()',
    ]
    
    #中国新闻网
    args['http://www.chinanews.com/scroll-news/news{page}.html'] = [
        1,
        'admin',
        '//div[contains(@class, "dd_bt")]/a/@href',
        '//div[contains(@class, "content")]/h1/text()',
        '//div[contains(@class, "left_zw")]/p/text()',
    ]
    
    for key in args:
        cache[key] = args[key]
    
