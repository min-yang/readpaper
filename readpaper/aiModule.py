import json
import os
import sys
import random
import time

import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
from transformers import AutoModelWithLMHead, AutoTokenizer

class imageClassifier:
    def __init__(self):
        self.model = models.mobilenet_v2(pretrained=True)     # Trained on 1000 classes from ImageNet
        self.model.eval()

        self.img_class_map = None
        mapping_file_path = 'index_to_name.json'              # Human-readable names for Imagenet classes
        if os.path.isfile(mapping_file_path):
            with open (mapping_file_path) as f:
                self.img_class_map = json.load(f)
        
    # Transform input into the form our model expects
    def transform_image(self, infile):
        input_transforms = [
            transforms.Resize(255),                           # We use multiple TorchVision transforms to ready the image
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                [0.485, 0.456, 0.406],                        # Standard normalization for ImageNet model input
                [0.229, 0.224, 0.225]
            )
        ]
        my_transforms = transforms.Compose(input_transforms)
        image = Image.open(infile)                            # Open the image file
        timg = my_transforms(image)                           # Transform PIL image to appropriately-shaped PyTorch tensor
        timg.unsqueeze_(0)                                    # PyTorch models expect batched input; create a batch of 1
        return timg
        
    # Get a prediction
    def get_prediction(self, input_tensor):
        outputs = self.model.forward(input_tensor)            # Get likelihoods for all ImageNet classes
        outputs = torch.nn.Softmax(dim=1)(outputs)
        prediction = outputs.argsort(descending=True)[0][:5]  # Extract the most likely class
        scores = outputs[0][prediction]
        return prediction, scores

    # Make the prediction human-readable
    def render_prediction(self, prediction_idx):
        idxes, names = [], []
        for idx in prediction_idx:    
            stridx = str(idx.item())
            idxes.append(stridx)
            class_name = 'Unknown'
            if self.img_class_map is not None:
                if stridx in self.img_class_map is not None:
                    class_name = self.img_class_map[stridx][1]
            names.append(class_name)
            
        return idxes, names
        
    def run(self, infile):
        input_tensor = self.transform_image(infile)
        prediction_idx, scores = self.get_prediction(input_tensor)
        class_ids, class_names = self.render_prediction(prediction_idx)
        ret_data = []
        for i in range(len(class_names)):
            ret_data.append((class_names[i].replace('_', ' '), scores[i].item()))
        return ret_data
        
class Translation:
    def __init__(self):
        self.model = AutoModelWithLMHead.from_pretrained("Helsinki-NLP/opus-mt-en-zh")
        self.tokenizer = AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-zh")
        
    def run(self, text):
        inputs = self.tokenizer.encode(text, return_tensors='pt')
        outputs = self.model.generate(inputs)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
class TextGeneration:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained("hfl/chinese-xlnet-base")
        self.model = AutoModelWithLMHead.from_pretrained("hfl/chinese-xlnet-base")
        
    def run(self, prompt=''):
        prompt = prompt[-200:]
        encoded_prompt = self.tokenizer.encode(prompt, add_special_tokens=False, return_tensors="pt")
        if encoded_prompt.size()[-1] == 0:
            input_ids = None
        else:
            input_ids = encoded_prompt
            
        output_sequences = self.model.generate(
            input_ids = input_ids,
            max_length = 20 + len(encoded_prompt[0]),
            top_k = 0,
            top_p = 0.9,
            repetition_penalty = 2.0,
            do_sample = True,
            num_return_sequences = 4,
        )
        
        output_texts = []
        for  output_sequence in output_sequences:
            text = self.tokenizer.decode(output_sequence, clean_up_tokenization_spaces=True, skip_special_tokens=True)
            idx_start = len(self.tokenizer.decode(encoded_prompt[0], clean_up_tokenization_spaces=True, skip_special_tokens=True))
            output_texts.append(text[idx_start:])
        
        return output_texts
        
    def run_petition(self, run_time=60):
        article = ''
        prompt = '共同富裕是全体人民的富裕，是人民群众物质生活和精神生活都富裕，不是少数人的富裕，也不是整齐划一的平均主义，要分阶段促进共同富裕。要鼓励勤劳创新致富，坚持在发展中保障和改善民生，为人民提高受教育程度、增强发展能力创造更加普惠公平的条件，畅通向上流动通道，给更多人创造致富机会，形成人人参与的发展环境。'
        
        t0 = time.time()
        while True:
            if time.time() - t0 > run_time:
                break
            texts = self.run(prompt)
            random.shuffle(texts)
            prompt = prompt + texts[0]
            article += texts[0]
            
        return article
    
if __name__ == '__main__':
    gen = TextGeneration()
    gen.run_petition()
    
