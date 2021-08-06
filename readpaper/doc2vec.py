import re
import sys
import logging

import gensim
import jieba
from pymongo import MongoClient

from utils import collection_dict, collection_language

logging.basicConfig(format='[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s', level=logging.INFO)

class Corpus:
    def __init__(self, collection, filter_dict, language, tokens_only=False):
        self.collection = collection
        self.filter_dict = filter_dict
        self.tokens_only = tokens_only
        self.language = language
        
    def __iter__(self):
        docs = self.collection.find(self.filter_dict)
        for doc in docs:
            if self.language == 'EN':
                tokens = gensim.utils.simple_preprocess(doc['summary'])
            elif self.language == 'CN':
                text = re.sub(r'\s+', ' ', doc['summary'])
                tokens = jieba.lcut(text)
            else:
                raise ValueError('Unsupported language')
            
            doc_id = doc['_id']
            if self.tokens_only:
                yield tokens
            else:
                # For training data, add tags
                yield gensim.models.doc2vec.TaggedDocument(tokens, [doc_id])
            
def train(corpus, key):
    model = gensim.models.doc2vec.Doc2Vec(vector_size=100, min_count=2, epochs=10)
    model.build_vocab(corpus)
    model.train(corpus, total_examples=model.corpus_count, epochs=model.epochs)
    model.save('saved/%s_doc2vec.bin' %key)
            
def result_write(corpus, collection, key):
    model = gensim.models.doc2vec.Doc2Vec.load('saved/%s_doc2vec.bin' %key)
    for doc in corpus:
        doc_id = doc[1][0]
        words = doc[0]
        
        inferred_vector = model.infer_vector(words)
        sims = model.dv.most_similar([inferred_vector], topn=11)
        
        similar_paper = []
        for sim in sims:
            if sim[0] == doc_id:
                continue
            if sim[1] > 0:
                similar_paper.append(sim[0])
                if len(similar_paper) == 10:
                    break
            
        collection.find_one_and_update({'_id': doc_id}, {'$set': {'similar_paper': similar_paper}})

def main(key):
    client = MongoClient()
    collection = eval('client.' + collection_dict[key])
    language = collection_language[key]
    filter_dict = {}
    train_corpus = Corpus(collection, filter_dict, language)
    train(train_corpus, key)
    result_write(train_corpus, collection, key)
    
if __name__ == '__main__':
    for key in collection_dict:
        main(key)
    
    
