import os
import re
import json
import time
import random
import sqlite3

import bcrypt
import tornado.ioloop
import tornado.web
import tornado.options
import pymongo
from pymongo import MongoClient

from rec_sys import get_recommend_result

UPDATE_DELAY = 60 * 5

class BaseHandler(tornado.web.RequestHandler):
    def custom_find(self, collection, *args, **kwargs):
        my_params = {'projection': ['_id', 'title', 'summary', 'updated', 'avg_score']}
        my_params.update(kwargs)
        return collection.find(*args, **my_params)
        
    def find_sort_by_updated(self, filter, page):
        papers = []
        num_skip = (page - 1) * 10
        if num_skip < 0:
            raise tornado.web.HTTPError(400)
            
        for doc in self.custom_find(
            self.application.mongo_client.paper.cs_paper_abs,
            filter, 
            skip=num_skip, 
            limit=11, 
            sort=[('updated', pymongo.DESCENDING)]
        ):
            papers.append(doc)
            
        if not papers:
            raise tornado.web.HTTPError(404)
        
        return papers
        
    def prepare(self):
        # get_current_user cannot be a coroutine, so set
        # self.current_user in prepare instead.
        current_user = self.get_secure_cookie("username")
        if current_user:
            self.current_user = current_user
            
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
    def get(self):
        self.render('base.html')
        
class PaperIndexHandler(BaseHandler):
    def get(self):
        page = int(self.get_query_argument('page', 1))
        papers = self.find_sort_by_updated({}, page)
        n_papers = self.application.mongo_client.paper.cs_paper_abs.count_documents({})
        self.render('paper.html', papers=papers, page=page, total_num=n_papers)

class TopicHandler(BaseHandler):
    def get(self, topic_index):
        filter = {'topic_index': int(topic_index)}
        page = int(self.get_query_argument('page', 1))
        papers = self.find_sort_by_updated(filter, page)
        n_papers = self.application.mongo_client.paper.cs_paper_abs.count_documents(filter)
        self.render('topic.html', papers=papers, page=page, total_num=n_papers)
        
class PaperHandler(BaseHandler):
    def get(self, paper_id):
        paper = self.application.mongo_client.paper.cs_paper_abs.find_one({'_id': paper_id})
        if not paper:
            raise tornado.web.HTTPError(404)
            
        sim_title = []
        sim_ids = paper.get('similar_paper', [])
        for sim_id in sim_ids:
            title = self.application.mongo_client.paper.cs_paper_abs.find_one({'_id': sim_id})['title']
            sim_title.append((sim_id, title))
               
        my_score = self.query('select rating from user_rate where user=? and item=?', (
            self.current_user.decode(), 
            paper_id,
        ))
        my_score = [ele['rating'] for ele in my_score]
        my_score = my_score[0] if my_score else 0
        
        self.render('paper_text.html', paper=paper, sim_title=sim_title, my_score=my_score)

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
    def get(self):
        keyword = self.get_argument('keyword')
        no_word_list = re.findall(r'\W+$', keyword)
        if no_word_list:
            keyword = keyword[:-(len(no_word_list[-1]))]
            
        p = re.compile('\\b%s\\b' %(
            re.escape(re.sub(r'\s+', ' ', keyword)).replace('\\ ', '\s*')
        ), flags=re.I)
        filter = {'$or': [{'title': p}, {'summary': p}]}
        
        page = int(self.get_query_argument('page', 1))
        papers = self.find_sort_by_updated(filter, page)
        n_papers = self.application.mongo_client.paper.cs_paper_abs.count_documents(filter)
        self.render('paper.html', papers=papers, page=page, total_num=n_papers)
        
class RatingHandler(BaseHandler):
    @tornado.web.authenticated
    async def post(self):
        data = json.loads(self.request.body)
        self.query('insert or replace into user_rate values (?, ?, ?)', (
            data['user'], 
            data['item'], 
            float(data['value']), 
        ))
        
        item_scores = self.query('select rating from user_rate where item=?', (data['item'], ))
        item_scores = [ele['rating'] for ele in item_scores]
        avg_score = round(sum(item_scores) / len(item_scores), 1)
        self.application.mongo_client.paper.cs_paper_abs.find_one_and_update({'_id': data['item']}, {'$set': {'avg_score': avg_score}})
        if time.time() - self.application.last_update > UPDATE_DELAY:
            await tornado.ioloop.IOLoop.current().run_in_executor(None, get_recommend_result)
            self.application.last_update = time.time()
        
class RecommenderHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        page = int(self.get_query_argument('page', 1))
        
        rec_items = eval(self.query(
            'select rec_items from user_recommend where name=?', (self.current_user.decode(), )
        )[0]['rec_items'])
        
        papers = []
        for item in rec_items[(page-1)*10:(page*10)+1]:
            papers.append(self.application.mongo_client.paper.cs_paper_abs.find_one({'_id': item}))
        
        self.render('paper.html', papers=papers, page=page, total_num=len(rec_items))
        
class Application(tornado.web.Application):
    def __init__(self):
        self.user_db = sqlite3.connect('user.db')
        self.user_db.row_factory = sqlite3.Row
        self.mongo_client = MongoClient()
        self.last_update = 0
        handlers = [
            (r'/', HomeHandler),
            (r"/paper/index", PaperIndexHandler),
            (r"/topic/([0-9]+)", TopicHandler),
            (r"/paper/([0-9.]+)", PaperHandler),
            (r'/search', SearchHandler),
            (r'/auth/login', LoginHandler),
            (r'/auth/create', UserCreateHandler),
            (r'/auth/logout', LogoutHandler),
            (r'/rating', RatingHandler),
            (r'/recommender', RecommenderHandler),
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

if __name__ == "__main__":
    tornado.options.parse_command_line()
    app = Application()
    app.listen(8000)
    tornado.ioloop.IOLoop.current().start()
