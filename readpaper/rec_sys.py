import time
import sqlite3
import logging

import lightfm
import lightfm.data
import gensim
import numpy as np
from pymongo import MongoClient
from scipy import sparse

def get_recommend_result():
    """获取推荐结果
    1、获取所有的用户和推荐对象
    2、获取推荐对象的特征
    3、获取所有的评分
    4、构建模型并获取推荐结果
    """
    
    t0 = time.time()
    mongo_client = MongoClient()
    conn = sqlite3.connect('user.db')

    users = []
    items = []

    for row in conn.execute('select name from users').fetchall():
        users.append(row[0])

    for paper in mongo_client.paper.cs_paper_abs.find(projection=[]):
        items.append(paper['_id'])
        
    doc_model = gensim.models.doc2vec.Doc2Vec.load('saved/doc2vec.bin')
    item_features = []
    for item in items:
        item_features.append(doc_model[item])
    item_features = sparse.csr_matrix(np.array(item_features))
        
    ratings = conn.execute('select * from user_rate').fetchall()
        
    dataset = lightfm.data.Dataset()
    dataset.fit(users, items)
    _, weights = dataset.build_interactions(ratings)
    
    rec_model = lightfm.LightFM(loss='warp')
    rec_model.fit(weights, item_features=item_features, epochs=30)
    
    n_items = len(items)
    
    ratings = [(ele[0], ele[1]) for ele in ratings]
    for user in users:
        scores = rec_model.predict(dataset.mapping()[0][user], np.arange(n_items), item_features=item_features)
        top_items = np.argsort(-scores)
        count = 0
        rec_items = []
        for item in top_items:
            item_id = items[item]
            if (user, item_id) not in ratings:
                rec_items.append(item_id)
                count += 1
                if count == 100:
                    break
        
        with conn:
            conn.execute('insert or replace into user_recommend values (?, ?)', (user, repr(rec_items), ))
    
    logging.info('推荐系统更新耗时:%.3f' %(time.time() - t0))
    
if __name__ == '__main__':
    get_recommend_result()

