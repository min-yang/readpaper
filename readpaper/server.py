import os
import random

import tornado.ioloop
import tornado.web
import tornado.options
import pymongo
from pymongo import MongoClient

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        page = int(self.get_query_argument('page', 1))
        papers = []

        for doc in self.application.mongo_client.paper.cs_paper_abs.find(skip=num_skip, limit=10):
            papers.append(doc)
            
        self.render('paper.html', papers=papers, title='论文列表', page=None)

class TopicHandler(tornado.web.RequestHandler):
    def get(self, topic_index):
        filter = {'topic_index': int(topic_index)}
        
        page = int(self.get_query_argument('page', 1))
        papers = []
        num_skip = (page - 1) * 10
        if num_skip < 0:
            raise tornado.web.HTTPError(404)
            
        for doc in self.application.mongo_client.paper.cs_paper_abs.find(filter, skip=num_skip, limit=11, sort=[('updated', pymongo.DESCENDING)]):
            papers.append(doc)
            
        if not papers:
            raise tornado.web.HTTPError(404)
            
        self.render('paper.html', papers=papers, title='主题-%s 论文列表' %topic_index, page=page)

class PaperHandler(tornado.web.RequestHandler):
    def get(self, paper_id):
        paper = self.application.mongo_client.paper.cs_paper_abs.find_one({'_id': paper_id})
        if not paper:
            raise tornado.web.HTTPError(404)
            
        sim_title = []
        sim_ids = paper['similar_paper']
        for sim_id in sim_ids:
            title = self.application.mongo_client.paper.cs_paper_abs.find_one({'_id': sim_id})['title']
            sim_title.append((sim_id, title))
            
        self.render('paper_text.html', paper=paper, sim_title=sim_title)

class Application(tornado.web.Application):
    def __init__(self):
        self.mongo_client = MongoClient()
        handlers = [
            (r"/paper/all", MainHandler),
            (r"/topic/([0-9]+)", TopicHandler),
            (r"/paper/([0-9.]+)", PaperHandler),
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
