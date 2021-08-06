import re
import time
import sqlite3
import logging

import lightfm
import lightfm.data
import gensim
import numpy as np
from scipy import sparse
from pymongo import MongoClient

from utils import collection_dict

def get_recommend_result(key):
    """获取推荐结果
    1、获取所有的用户和推荐对象
    2、获取推荐对象的特征
    3、获取所有的评分
    4、构建模型并获取推荐结果
    """
    
    t0 = time.time()
    conn = sqlite3.connect('user.db')
    client = MongoClient()
    
    users = []
    for row in conn.execute('select name from users').fetchall():
        users.append(row[0])

    items = []
    collection = eval('client.' + collection_dict[key])
    for paper in collection.find(projection=[]):
        items.append(paper['_id'])
        
    doc_model = gensim.models.doc2vec.Doc2Vec.load('saved/%s_doc2vec.bin' %key)
    item_features = []
    item_without_feature = []
    for item in items:
        try:
            item_features.append(doc_model[item])
        except KeyError:
            item_without_feature.append(item)
    
    for item in item_without_feature:
        items.remove(item)
    
    item_features = sparse.csr_matrix(np.array(item_features))
    
    ratings = conn.execute('select * from user_rate_%s' %key).fetchall()
    valid_ratings = []
    for rating in ratings:
        if rating[1] not in item_without_feature:
            valid_ratings.append(rating)
    
    dataset = lightfm.data.Dataset()
    dataset.fit(users, items)
    try:
        _, weights = dataset.build_interactions(valid_ratings)
    except Exception as e:
        item_id = re.search(r'Item id (\w+)', str(e))
        if item_id:
            item_id = item_id.group(1)
            with conn:
                conn.execute('delete from user_rate_%s where item=?' %key, (item_id, ))
            logging.error('文章已经不存在，删除相关评分 [%s]' %item_id)
        return
    
    rec_model = lightfm.LightFM(loss='warp')
    rec_model.fit(weights, item_features=item_features, epochs=30)

    n_items = len(items)

    valid_ratings = [(ele[0], ele[1]) for ele in valid_ratings]
    for user in users:
        scores = rec_model.predict(dataset.mapping()[0][user], np.arange(n_items), item_features=item_features)
        top_items = np.argsort(-scores)
        count = 0
        rec_items = []
        for item in top_items:
            item_id = items[item]
            if (user, item_id) not in valid_ratings:
                rec_items.append(item_id)
                count += 1
                if count == 100:
                    break
    
        with conn:
            conn.execute('insert or replace into user_recommend_%s values (?, ?)' %key, (user, repr(rec_items), ))
    
    logging.info('推荐系统更新耗时:%.3f' %(time.time() - t0))
    
if __name__ == '__main__':
    for key in collection_dict:
        get_recommend_result(key)

