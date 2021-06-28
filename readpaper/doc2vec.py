import logging

import gensim
from pymongo import MongoClient

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

class Corpus:
    def __init__(self, collection, filter_dict, tokens_only=False):
        self.collection = collection
        self.filter_dict = filter_dict
        self.tokens_only = tokens_only
        
    def __iter__(self):
        docs = self.collection.find(self.filter_dict)
        for doc in docs:
            tokens = gensim.utils.simple_preprocess(doc['summary'])
            doc_id = doc['_id']
            if self.tokens_only:
                yield tokens
            else:
                # For training data, add tags
                yield gensim.models.doc2vec.TaggedDocument(tokens, [doc_id])
            
def train(corpus):
    model = gensim.models.doc2vec.Doc2Vec(vector_size=100, min_count=2, epochs=10)
    model.build_vocab(corpus)
    model.train(corpus, total_examples=model.corpus_count, epochs=model.epochs)
    model.save('saved/doc2vec.bin')
            
def result_write(corpus, collection):
    model = gensim.models.doc2vec.Doc2Vec.load('saved/doc2vec.bin')
    for doc in corpus:
        doc_id = doc[1][0]
        print(doc_id)
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

if __name__ == '__main__':
    client = MongoClient()
    collection = client.paper.cs_paper_abs
    filter_dict = {}
    
    train_corpus = Corpus(collection, filter_dict)
    train(train_corpus)
    result_write(train_corpus, collection)
    
    
