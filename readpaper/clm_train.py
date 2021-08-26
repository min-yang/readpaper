import os
import re
import json
from multiprocessing import cpu_count

from datasets import load_dataset
from transformers import AutoTokenizer
from transformers import AutoModelForCausalLM
from transformers import Trainer, TrainingArguments
from transformers import GPT2Config, GPT2LMHeadModel

block_size = 128
def group_texts(examples):
    # Concatenate all texts.
    concatenated_examples = {k: sum(examples[k], []) for k in examples.keys()}
    total_length = len(concatenated_examples[list(examples.keys())[0]])
    # We drop the small remainder, we could add padding if the model supported it instead of this drop, you can
        # customize this part to your needs.
    total_length = (total_length // block_size) * block_size
    # Split by chunks of max_len.
    result = {
        k: [t[i : i + block_size] for i in range(0, total_length, block_size)]
        for k, t in concatenated_examples.items()
    }
    result["labels"] = result["input_ids"].copy()
    return result
        
class myTokenizer:
    def __init__(self, vocab_file):
        vocab_dict = json.load(open(vocab_file))
        self.id2token = vocab_dict['id2token']
        self.token2id = vocab_dict['token2id']
        self.bos_token_id = len(self.id2token) # 对应\t
        self.id2token[self.bos_token_id] = '\t'
        self.token2id['\t'] = self.bos_token_id
    
    @property
    def size(self):
        return len(self.id2token)
    
    def __call__(self, text):
        return self.encode(text)
    
    def encode(self, text):
        data = {'input_ids': [], 'attention_mask': []}
        if isinstance(text, str):
            for char in text:
                token_id = self.token2id.get(char)
                if token_id:
                    data['input_ids'].append(token_id)
                    data['attention_mask'].append(1)
        elif isinstance(text, list):
            for ele in text:
                input_ids = []
                attention_mask = []
                for char in ele:
                    token_id = self.token2id.get(char)
                    if token_id:
                        input_ids.append(token_id)
                        attention_mask.append(1)
                data['input_ids'].append(input_ids)
                data['attention_mask'].append(attention_mask)
        return data
    
    def decode(self, id_list):
        if isinstance(id_list, int):
            id_list = [id_list]
            
        text = ''
        for token_id in id_list:
            if token_id == self.bos_token_id:
                text += '\t'
            else:
                token = self.id2token.get(str(token_id))
                if token:
                    text += token
        return text

def train_from_scratch():
    vocab_file = 'vocab_en.json'
    train_file = 'clm_train.txt'
    valid_file = 'clm_valid.txt' 
    output_dir = 'gpt2-chinese'
    
    if not os.path.exists(vocab_file):
        char_set = set()
        for line in open(train_file):
            line = re.sub(r'\s', '', line)
            for char in line:
                char_set.add(char)
        
        vocab_dict = {'id2token': {}, 'token2id': {}}
        idx = 0
        for char in char_set:
            vocab_dict['id2token'][idx] = char
            vocab_dict['token2id'][char] = idx
            idx += 1
            
        json.dump(vocab_dict, open(vocab_file, 'w'), ensure_ascii=False)
    
    tokenizer = myTokenizer(vocab_file)
    def tokenize_function(examples):
        return tokenizer.encode(examples['text'])
        
    datasets = load_dataset("text", data_files={"train": train_file, "validation": valid_file})
    tokenized_datasets = datasets.map(tokenize_function, batched=True, num_proc=cpu_count(), remove_columns=["text"])
    lm_datasets = tokenized_datasets.map(
        group_texts,
        batched=True,
        batch_size=1000,
        num_proc=cpu_count(),
    )

    training_args = TrainingArguments(
        output_dir,
        num_train_epochs=100,
        save_steps=5000,
        evaluation_strategy='steps',
        eval_steps=5000,
        save_total_limit=2,
        load_best_model_at_end=True,
        greater_is_better=False,
    )
    
    config = GPT2Config(
        vocab_size = tokenizer.size, 
        bos_token_id = tokenizer.bos_token_id,
        eos_token_id = tokenizer.bos_token_id,
        pad_token_id = tokenizer.bos_token_id,
    )
    model = GPT2LMHeadModel(config)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=lm_datasets['train'],
        eval_dataset=lm_datasets['validation'],
    )
    trainer.train(resume_from_checkpoint=None)
    trainer.save_model()
    
def finetune():
    train_file = 'clm_train.txt'
    valid_file = 'clm_valid.txt'  
    model_checkpoint = "hfl/chinese-xlnet-base"
    tokenizer = AutoTokenizer.from_pretrained(model_checkpoint, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(model_checkpoint)
    output_dir = 'chinese-xlnet-base-finetune'
    
    def tokenize_function(examples):
        return tokenizer(examples["text"])

    datasets = load_dataset("text", data_files={"train": train_file, "validation": valid_file})
    tokenized_datasets = datasets.map(tokenize_function, batched=True, num_proc=cpu_count(), remove_columns=["text"])
    lm_datasets = tokenized_datasets.map(
        group_texts,
        batched=True,
        batch_size=1000,
        num_proc=cpu_count(),
    )
    
    training_args = TrainingArguments(
        output_dir,
        num_train_epochs=10,
        learning_rate=2e-5,
        weight_decay=0.01,
        save_steps=5000,
        evaluation_strategy='steps',
        eval_steps=5000,
        save_total_limit=1,
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=lm_datasets['train'],
        eval_dataset=lm_datasets['validation'],
    )
    trainer.train(resume_from_checkpoint=None)
    trainer.save_model()
    
if __name__ == '__main__':
    train_from_scratch()
