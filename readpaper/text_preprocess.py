import re
import json
import random

from pymongo import MongoClient

def preprocess():
    """用于预处理MongoDB中存储的新闻文档"""
    c = MongoClient(host='10.10.9.185', username='admin', password='admin')
    vocab = set()
    vocab_file = 'vocab_en.json'
    
    train_file = open('clm_train.txt', 'w')
    valid_file = open('clm_valid.txt', 'w')
    for doc in c.article.crawl.find():
        text = doc['summary']
        text = re.sub(r'([a-zA-Z])\s+(?=[a-zA-Z])', r'\1<|eos|>', text) #保留英文之间的空格
        text = re.sub(r'\s+', '', text)
        text = text.replace('<|eos|>', ' ')
        
        if random.random() < 0.01:
            valid_file.write('\t' + text + '\n')
        else:
            train_file.write('\t' + text + '\n')
            
        for char in text:
            vocab.add(char)
    
    vocab_dict = {'id2token': {}, 'token2id': {}}
    idx = 0
    for char in vocab:
        vocab_dict['id2token'][idx] = char
        vocab_dict['token2id'][char] = idx
        idx += 1
        
    json.dump(vocab_dict, open(vocab_file, 'w'), ensure_ascii=False)
    
if __name__ == '__main__':
    preprocess()
