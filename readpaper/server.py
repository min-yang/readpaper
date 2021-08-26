import os
import re
import json
import time
import random
import sqlite3
import asyncio
import logging
import datetime
import uuid
from io import BytesIO
from multiprocessing import Process, Manager, Queue
from functools import lru_cache

import bcrypt
import tornado.ioloop
import tornado.web
import tornado.options
import pymongo
from pymongo import MongoClient

import article_collect
from rec_sys import get_recommend_result
from utils import collection_dict, collection_language
from aiModule import *

UPDATE_DELAY = 60 * 5
ADMIN_USERS = ['yangmin', 'yangmin2', 'yangmin3']
TASK_QUEUE = Queue()
RESULT_DICT = Manager().dict()

def check_contain_chinese(text):
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

class BaseHandler(tornado.web.RequestHandler):
    def write_error(self, status_code, **kwargs):
        self.render('error.html', info='%s:%s' %(status_code, self._reason))
    
    def open_mongo(self, collection):
        return eval('self.application.mongo_client.' + collection)
        
    def custom_find(self, collection, *args, **kwargs):
        my_params = {'projection': ['_id', 'title', 'summary', 'updated', 'avg_score']}
        my_params.update(kwargs)
        return collection.find(*args, **my_params)
        
    def post_process(self, doc): #如果不需要保留原文本（什么地方换行）的话，标准化可以在入库的时候进行
        if check_contain_chinese(doc['summary']):
            max_len = 400
            if len(doc['summary']) > max_len:
                end_text = '......'
            else:
                end_text = ''
            doc['summary'] = doc['summary'][:max_len] + end_text
            doc['summary'] = re.sub(r'\s+', ' ', doc['summary'])
        return doc
        
    def find_sort_by_updated(self, collection, filter, page):
        papers = []
        num_skip = (page - 1) * 10
        if num_skip < 0:
            raise tornado.web.HTTPError(400)
            
        for doc in self.custom_find(
            collection,
            filter, 
            skip=num_skip, 
            limit=11, 
            sort=[('updated', pymongo.DESCENDING)]
        ):
            papers.append(self.post_process(doc))
            
        if not papers:
            raise tornado.web.HTTPError(404)
        
        return papers
        
    def prepare(self):
        # get_current_user cannot be a coroutine, so set
        # self.current_user in prepare instead.
        current_user = self.get_secure_cookie("username")
        if current_user:
            self.current_user = current_user.decode()
            self.is_admin = self.current_user in ADMIN_USERS
            
    def query(self, stmt, *args):
        with self.application.user_db as conn:
            return conn.execute(stmt, *args).fetchall()
        
    def queryone(self, stmt, *args):
        results = self.query(stmt, *args)
        if len(results) == 0:
            raise ValueError('目标不存在')
        elif len(results) > 1:
            raise ValueError('Expected 1 result, got %d' %len(results))
        return results[0]

class HomeHandler(BaseHandler):
    async def get(self):
        self.render('base.html')
            
class PaperIndexHandler(BaseHandler):
    def get(self, collection_key):
        collection = self.open_mongo(collection_dict[collection_key])
        page = int(self.get_query_argument('page', 1))
        papers = self.find_sort_by_updated(collection, {}, page)
        n_papers = collection.count_documents({})
        self.render('paper_list.html', collection=collection_key, papers=papers, page=page, total_num=n_papers)

class TopicHandler(BaseHandler):
    def get(self, collection_key, topic_index):
        collection = self.open_mongo(collection_dict[collection_key])
        filter = {'topic_index': int(topic_index)}
        page = int(self.get_query_argument('page', 1))
        papers = self.find_sort_by_updated(collection, filter, page)
        n_papers = collection.count_documents(filter)
        self.render('paper_list.html', collection=collection_key, papers=papers, page=page, total_num=n_papers)
        
class PaperHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, collection_key, paper_id):
        collection = self.open_mongo(collection_dict[collection_key])
        paper = collection.find_one({'_id': paper_id})
        if not paper:
            raise tornado.web.HTTPError(404)
            
        sim_title = []
        sim_ids = paper.get('similar_paper', [])
        for sim_id in sim_ids:
            sim_doc = collection.find_one({'_id': sim_id})
            if sim_doc:
                title = sim_doc['title']
                sim_title.append((sim_id, title))
        
        my_score = self.query('select rating from user_rate_%s where user=? and item=?' %collection_key, (
            self.current_user, 
            paper_id,
        ))
        my_score = [ele['rating'] for ele in my_score]
        my_score = my_score[0] if my_score else 0
        
        self.render('paper_text.html', collection=collection_key, paper=paper, sim_title=sim_title, my_score=my_score)

class LoginHandler(BaseHandler):
    def get(self):
        self.render('login.html', error=None)
        
    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
        
        try:
            user = self.queryone('select * from users where name=?', (username,))
        except Exception as e:
            self.render('login.html', error=str(e))
            return
        
        password_equal = bcrypt.checkpw(tornado.escape.utf8(password), tornado.escape.utf8(user['hashed_password']))
        if password_equal:
            self.set_secure_cookie('username', str(user['name']))
            self.redirect(self.get_argument('next', '/'))
        else:
            self.render('login.html', error='密码错误')

class UserCreateHandler(BaseHandler):
    def get(self):
        self.render('user_create.html', error=None)

    def post(self):
        username = self.get_argument('username')
        password = self.get_argument('password')
        phone = self.get_argument('phone')
        if not username or not password or not phone:
            self.render('user_create.html', error='用户名、密码或手机号为空')
            return
        
        if not re.search(r'^1[3-9][0-9]{9}$', phone):
            self.render('user_create.html', error='无效的手机号码')
            return
        
        hashed_password = bcrypt.hashpw(tornado.escape.utf8(password), bcrypt.gensalt())
        try:
            self.query(
                'insert into users values (?, ?, ?)', 
                (
                    username, 
                    tornado.escape.to_unicode(hashed_password),
                    phone,
                )
            )
        except Exception as e:
            self.render('user_create.html', error=str(e))
            
        self.set_secure_cookie('username', username)
        self.redirect(self.get_argument('next', '/'))
       
class LogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie('username')
        self.redirect(self.get_argument('next', '/'))
        
class SearchHandler(BaseHandler):
    def get(self, collection_key):
        collection = self.open_mongo(collection_dict[collection_key])
        keyword = self.get_argument('keyword')
        no_word_list = re.findall(r'\W+$', keyword)
        if no_word_list:
            keyword = keyword[:-(len(no_word_list[-1]))]
        
        if check_contain_chinese(keyword):
            p = re.compile(re.escape(keyword).replace('\\ ', '\s*'))
        else:
            p = re.compile('\\b%s\\b' %(
                re.escape(re.sub(r'\s+', ' ', keyword)).replace('\\ ', '\s*')
            ), flags=re.I)
            
        filter = {'$or': [{'title': p}, {'summary': p}]}
        page = int(self.get_query_argument('page', 1))
        papers = self.find_sort_by_updated(collection, filter, page)
        n_papers = collection.count_documents(filter)
        self.render('paper_list.html', collection=collection_key, papers=papers, page=page, total_num=n_papers)
        
class RatingHandler(BaseHandler):
    @tornado.web.authenticated
    async def post(self, collection_key):
        data = json.loads(self.request.body)
        collection = self.open_mongo(collection_dict[collection_key])
        self.query('insert or replace into user_rate_%s values (?, ?, ?)' %collection_key, (
            data['user'], 
            data['item'], 
            float(data['value']), 
        ))
        
        item_scores = self.query('select rating from user_rate_%s where item=?' %collection_key, (data['item'], ))
        item_scores = [ele['rating'] for ele in item_scores]
        avg_score = round(sum(item_scores) / len(item_scores), 1)
        collection.find_one_and_update({'_id': data['item']}, {'$set': {'avg_score': avg_score}})
        try:
            if time.time() - self.application.last_update > UPDATE_DELAY:
                await tornado.ioloop.IOLoop.current().run_in_executor(None, get_recommend_result, collection_key)
                self.application.last_update = time.time()
        except KeyError:
            logging.info('文档向量模型未更新，无法训练推荐系统')
        
class RecommenderHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, collection_key):
        collection = self.open_mongo(collection_dict[collection_key])
        page = int(self.get_query_argument('page', 1))
        
        rec_items = eval(self.query(
            'select rec_items from user_recommend_%s where name=?' %collection_key, (self.current_user, )
        )[0]['rec_items'])
        
        papers = []
        for item in rec_items[(page-1)*10:(page*10)+1]:
            item_doc = collection.find_one({'_id': item})
            if item_doc:
                papers.append(self.post_process(item_doc))
            else:
                papers.append(None)
        
        self.render('paper_list.html', collection=collection_key, papers=papers, page=page, total_num=len(rec_items))
    
class PaperEditHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, collection_key, paper_id):
        if not self.is_admin:
            raise tornado.web.HTTPError(403)
        collection = self.open_mongo(collection_dict[collection_key])
        paper = collection.find_one({'_id': paper_id})
        if not paper:
            raise tornado.web.HTTPError(404)
                
        self.render('paper_edit.html', collection=collection_key, paper=paper)
    
    @tornado.web.authenticated
    def post(self, collection_key, paper_id):
        if not self.is_admin:
            raise tornado.web.HTTPError(403)
        collection = self.open_mongo(collection_dict[collection_key])
        title = self.get_argument('title')
        summary = self.get_argument('summary')
        
        collection.find_one_and_update({'_id': paper_id}, {'$set': {'title': title, 'summary': summary}})
        self.query('delete from user_rate_%s where item=?' %collection_key, (paper_id, ))
        
        self.redirect('/%s/paper/%s' %(collection_key, paper_id))

class PaperDeleteHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, collection_key, paper_id):
        if not self.is_admin:
            raise tornado.web.HTTPError(403)
        collection = self.open_mongo(collection_dict[collection_key])
        collection.delete_one({'_id': paper_id})
        self.redirect('/%s/index' %collection_key)

class PaperYouRatingHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self, collection_key):
        collection = self.open_mongo(collection_dict[collection_key])
        page = int(self.get_query_argument('page', 1))
        records = self.query(
            'select item from user_rate_%s where user=? limit 11 offset ?' %collection_key,
            (self.current_user, (page - 1) * 10, )
        )
        total_num = self.query(
            'select count(*) from user_rate_%s where user=?' %collection_key, (self.current_user, )
        )[0]['count(*)']
        
        papers = []
        for record in records:
            item_doc = collection.find_one({'_id': record['item']})
            if item_doc:
                papers.append(self.post_process(item_doc))
            else:
                papers.append(None)
                
        self.render('paper_list.html', collection=collection_key, papers=papers, page=page, total_num=total_num)

class PaperRandomHandler(BaseHandler):
    def get(self, collection_key):
        collection = self.open_mongo(collection_dict[collection_key])
        
        papers = []
        id_set = set()
        for paper in collection.aggregate([{'$sample': {'size': 10}}]):
            if paper['_id'] not in id_set:
                id_set.add(paper['_id'])
                papers.append(self.post_process(paper))
        
        self.render('paper_list.html', collection=collection_key, papers=papers, page=1, total_num=len(papers))
    
class CommentHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        item = self.request.headers['item']
        page = int(self.request.headers['page']) - 1
        collection = self.request.headers['collection']
        
        comments = []
        for comment in self.application.mongo_client.user.comment.find(
            {'item': item, 'collection': collection},
            projection = {'_id': False, 'user': True, 'item': True, 'comment': True, 'update_time': True},
            skip = 10 * page,
            limit = 10,
            sort = [('update_time', pymongo.DESCENDING)],
        ):
            comment['update_time'] = datetime.datetime.fromtimestamp(comment['update_time']).strftime('%Y-%m-%d %H:%M:%S')
            comments.append(comment)
        
        self.finish({'comments': comments})
        
    @tornado.web.authenticated
    def post(self):
        data = json.loads(self.request.body)
        data['update_time'] = time.time()
        self.application.mongo_client.user.comment.insert_one(data)

class AIHandler(BaseHandler):
    async def get_ai_result(self, model_name, *args):
        request_id = uuid.uuid4().hex
        TASK_QUEUE.put((request_id, model_name, args))
        while True:
            result = RESULT_DICT.get(request_id)
            if result:
                RESULT_DICT.pop(request_id)
                return result
            else:
                await asyncio.sleep(0.1)

class ImageClsHandler(AIHandler):
    @tornado.web.authenticated
    async def get(self):
        img_file = 'static/%s_image' %self.current_user
        if os.path.exists(img_file):
            class_data = await self.get_ai_result('imageClassifier', img_file)
        else:
            class_data = None

        self.render('imgClassifier.html', class_data=class_data)
    
    @tornado.web.authenticated
    def post(self):
        img_byte = self.request.files.get('image', [{}])[0].get('body', None)
        if img_byte:
            open('static/%s_image' %self.current_user, 'wb').write(img_byte)
            
        self.redirect('/ai/imageClassifier')
                        
class TranslationHandler(AIHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('translation.html')
        
    @tornado.web.authenticated
    async def post(self):
        src_lang = self.get_argument('src_lang')
        dst_lang = self.get_argument('dst_lang')
        src_text = self.get_argument('src_text')
        
        dst_text = await self.get_ai_result('Translation', src_text, src_lang, dst_lang)
        self.finish(dst_text)
     
class TextGenerationHandler(AIHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('textGeneration.html')

    @tornado.web.authenticated
    async def post(self):
        prompt = self.request.body.decode()
        output_texts = await self.get_ai_result('TextGeneration', prompt)
        self.finish({'list': output_texts})
    
class ObjectDetectionHandler(AIHandler):
    def image_detect(self, img_file):
        self.ai_model_load('objectDetection')
        return self.application.ai_model.run(img_file)
    
    @tornado.web.authenticated
    def get(self):
        img_file = 'static/%s_bbox.jpg' %self.current_user
        if os.path.exists(img_file):
            show_image = True
        else:
            show_image = False

        self.render('objectDetection.html', show_image=show_image)
    
    @tornado.web.authenticated
    async def post(self):
        img_byte = self.request.files.get('image', [{}])[0].get('body', None)
        if img_byte:
            img_file = BytesIO(img_byte)
            output_img = await self.get_ai_result('ObjectDetection', img_file)
            output_img.save('static/%s_bbox.jpg' %self.current_user)
            
        self.redirect('/ai/objectDetection')
    
class TextClsHandler(AIHandler):
    @tornado.web.authenticated
    def get(self):
        self.render('textClassifier.html')
    
    @tornado.web.authenticated
    async def post(self):
        text = self.request.body.decode()
        class_scores = await self.get_ai_result('TextClassifier', text)
        self.finish({'results': class_scores[0]})
    
class Application(tornado.web.Application):
    def __init__(self):
        self.user_db = sqlite3.connect('user.db')
        self.user_db.row_factory = sqlite3.Row
        self.mongo_client = MongoClient(host='10.10.9.185', username='admin', password='admin')
        self.ai_model = None
        self.last_update = 0
        self.table_define()
        handlers = [
            (r'/', HomeHandler),
            (r"/([a-z]+)/index", PaperIndexHandler),
            (r"/([a-z]+)/topic/([0-9]+)", TopicHandler),
            (r"/([a-z]+)/paper/([0-9a-z.]+)", PaperHandler),
            (r"/([a-z]+)/paper/([0-9a-z.]+)/edit", PaperEditHandler),
            (r"/([a-z]+)/paper/([0-9a-z.]+)/delete", PaperDeleteHandler),
            (r"/([a-z]+)/youRating", PaperYouRatingHandler),
            (r"/([a-z]+)/random", PaperRandomHandler),
            (r'/([a-z]+)/search', SearchHandler),
            (r'/comment', CommentHandler),
            (r'/auth/login', LoginHandler),
            (r'/auth/create', UserCreateHandler),
            (r'/auth/logout', LogoutHandler),
            (r'/([a-z]+)/rating', RatingHandler),
            (r'/([a-z]+)/recommender', RecommenderHandler),
            (r'/ai/imageClassifier', ImageClsHandler),
            (r'/ai/translation', TranslationHandler),
            (r'/ai/textGeneration', TextGenerationHandler),
            (r'/ai/objectDetection', ObjectDetectionHandler),
            (r'/ai/textClassifier', TextClsHandler),
        ]
        settings = dict(
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
            xsrf_cookies=True,
            cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
            login_url="/auth/login",
            debug=True,
        )
        super().__init__(handlers, **settings)

    def table_define(self):
        with self.user_db as conn:
            conn.execute(
                'create table if not exists users (name text primary key not null unique, hashed_password text not null, phone text not null unique)'
            )
            
            for key in collection_dict:
                conn.execute(
                    'create table if not exists user_rate_%s (user text, item text, rating num, unique (user, item))' %key
                )
                conn.execute(
                    'create table if not exists user_recommend_%s (name text primary key not null unique, rec_items text)' %key
                )

def ai_process():
    ai_model = None
    while True:
        request_id, model_name, args = TASK_QUEUE.get()
        try:
            model_class = eval(model_name)
        except NameError:
            continue
        
        if not issubclass(type(ai_model), model_class):
            ai_model = model_class()
        
        ret = ai_model.run(*args)
        RESULT_DICT[request_id] = ret
    
if __name__ == "__main__":
#    p = Process(target=article_collect.run)
#    p.start()

    p2 = Process(target = ai_process)
    p2.start()
    
    tornado.options.parse_command_line()
    app = Application()
    app.listen(8000)
    tornado.ioloop.IOLoop.current().start()
