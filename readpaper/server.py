import os
import random

import tornado.ioloop
import tornado.web
import tornado.options
from pymongo import MongoClient

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        num_skip = random.randint(0, self.application.mongo_client.paper.cs_paper_abs.estimated_document_count()-1)
        papers = []
        for doc in self.application.mongo_client.paper.cs_paper_abs.find(skip=num_skip, limit=10):
            papers.append(doc)
            
        self.render('paper.html', papers=papers, title='论文列表')

class TopicHandler(tornado.web.RequestHandler):
    def get(self, topic_index):
        filter = {'topic_index': int(topic_index)}

        papers = []
        num_skip = random.randint(0, self.application.mongo_client.paper.cs_paper_abs.estimated_document_count()-1)

        for doc in self.application.mongo_client.paper.cs_paper_abs.find(filter, skip=num_skip):
            papers.append(doc)
            if len(papers) == 10:
                break
        for doc in self.application.mongo_client.paper.cs_paper_abs.find(filter, limit=num_skip):
            if len(papers) == 10:
                break
            papers.append(doc)
             
        self.render('paper.html', papers=papers, title='%s 主题论文列表' %topic_index)

class Application(tornado.web.Application):
    def __init__(self):
        self.mongo_client = MongoClient()
        handlers = [
            (r"/", MainHandler),
            (r"/topic/([0-9]+)", TopicHandler),
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
