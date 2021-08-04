import logging

import jieba
from pymongo import MongoClient
from gensim.test.utils import common_texts
from gensim.models.doc2vec import Doc2Vec, TaggedDocument
from gensim.models import Phrases, LdaModel
from gensim.corpora import Dictionary
from nltk.tokenize import RegexpTokenizer
from nltk.stem.wordnet import WordNetLemmatizer

from utils import collection_dict, collection_language

logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

def preprocess(doc, language, tokenizer, lemmatizer):
    doc = doc['summary'].lower().replace('_', '')
    if language == 'EN':
        doc = tokenizer.tokenize(doc)
        doc = [token for token in doc if not token.isnumeric()]
        doc = [token for token in doc if len(token) > 1]
        doc = [lemmatizer.lemmatize(token) for token in doc]
    elif language == 'CN':
        doc = jieba.lcut(doc)
        doc = tokenizer.tokenize(' '.join(doc))
        doc = [token for token in doc if not token.isnumeric()]
    else:
        raise ValueError('Unsupported language')
    return doc

class Corpus:
    def __init__(self, collection, filter_dict, language):
        self.collection = collection
        self.filter_dict = filter_dict
        self.language = language
        self.tokenizer = RegexpTokenizer(r'\w+')
        self.lemmatizer = WordNetLemmatizer()

    def __iter__(self):
        docs = self.collection.find(self.filter_dict)
        for i, doc in enumerate(docs):
            yield preprocess(doc, self.language, self.tokenizer, self.lemmatizer)

class BigramCorpus:
    def __init__(self, data_gen, bigram):
        self.data_gen = data_gen
        self.bigram = bigram
    
    def __iter__(self):
        for i, doc in enumerate(self.data_gen):
            for token in self.bigram[doc]:
                if '_' in token:
                    doc.append(token)
            yield doc
            
class BOW:
    def __init__(self, data_gen, dictionary):
        self.data_gen = data_gen
        self.dictionary = dictionary
        
    def __iter__(self):
        for doc in self.data_gen:
            yield self.dictionary.doc2bow(doc)
            
def result_write(collection, language, filter_dict, bigram, dictionary, model):
    tokenizer = RegexpTokenizer(r'\w+')
    lemmatizer = WordNetLemmatizer()
        
    docs = collection.find(filter_dict)
    result = {}
    for doc in docs:
        rawid = doc['_id']
        doc = preprocess(doc, language, tokenizer, lemmatizer)
        for token in bigram[doc]:
            if '_' in token:
                doc.append(token)
            
        x = dictionary.doc2bow(doc)
        scores = model[x]
        result[rawid] = sorted(scores, key=lambda ele:ele[1], reverse=True)[0][0]

    for rawid in result:
        collection.find_one_and_update({'_id': rawid}, {'$set': {'topic_index': result[rawid]}})
        
class Inference:
    def __init__(self):
        self.tokenizer = RegexpTokenizer(r'\w+')
        self.lemmatizer = WordNetLemmatizer()
        self.bigram = Phrases.load('saved/bigram.bin')
        self.dictionary = Dictionary.load('saved/dictionary.bin')
        self.model = LdaModel.load('saved/ldamodel.bin')
        
    def run(self, doc):
        doc = doc.lower().replace('_', '')
        doc = self.tokenizer.tokenize(doc) 
        doc = [token for token in doc if not token.isnumeric()]
        doc = [token for token in doc if len(token) > 1]
        doc = [self.lemmatizer.lemmatize(token) for token in doc]
        for token in self.bigram[doc]:
            doc.append(token)
            
        x = self.dictionary.doc2bow(doc)
        scores = self.model[x]
        return scores
        
def main(key):
    collection = collection_dict[key]
    language = collection_language[key]
    filter_dict = {}
    
    corpus = Corpus(collection, filter_dict, language)
    bigram = Phrases(corpus, min_count=20)
    bigram.save('saved/%s_bigram.bin' %key)
    
    bigram_corpus = BigramCorpus(corpus, bigram)
    dictionary = Dictionary(bigram_corpus)
    dictionary.filter_extremes(no_below=20, no_above=0.5)
    dictionary.save('saved/%s_dictionary.bin' %key)
    
    my_corpus = BOW(bigram_corpus, dictionary)
    
    # Set training parameters.
    num_topics = 10
    chunksize = 2000
    passes = 20
    iterations = 400
    eval_every = None  # Don't evaluate model perplexity, takes too much time.

    # Make a index to word dictionary.
    temp = dictionary[0]  # This is only to "load" the dictionary.
    id2word = dictionary.id2token

    model = LdaModel(
        corpus=my_corpus,
        id2word=id2word,
        chunksize=chunksize,
        alpha='auto',
        eta='auto',
        iterations=iterations,
        num_topics=num_topics,
        passes=passes,
        eval_every=eval_every
    )
    model.save('saved/%s_ldamodel.bin' %key)
    
    result_write(collection, language, filter_dict, bigram, dictionary, model)
        
if __name__ == '__main__':
    for key in collection_dict:
        main(key)
    
