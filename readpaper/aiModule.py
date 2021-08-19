import json
import os
import sys
import random
import time

import opencc
import torch
import numpy as np
import matplotlib.pyplot as plt
import torchvision.transforms.functional as F
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
from transformers import AutoModelWithLMHead, AutoTokenizer, AutoModelForSequenceClassification, pipeline
from torchvision.utils import draw_bounding_boxes
from torchvision.models.detection import fasterrcnn_resnet50_fpn
from torchvision.transforms.functional import convert_image_dtype

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
        self.s2t_converter = opencc.OpenCC('s2t.json')
        self.t2s_converter = opencc.OpenCC('t2s.json')
        
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
        prompt = ''
        
        t0 = time.time()
        while True:
            if time.time() - t0 > run_time:
                break
            texts = self.run(prompt)
            random.shuffle(texts)
            prompt = prompt + texts[0]
            article += texts[0]
            print(article)
            
        return article

class ObjectDetection:
    def __init__(self):
        self.model = fasterrcnn_resnet50_fpn(pretrained=True, progress=False)
        self.model = self.model.eval()
        self.score_threshold = 0.8
        self.COCO_INSTANCE_CATEGORY_NAMES = [
            '__background__', 'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus',
            'train', 'truck', 'boat', 'traffic light', 'fire hydrant', 'N/A', 'stop sign',
            'parking meter', 'bench', 'bird', 'cat', 'dog', 'horse', 'sheep', 'cow',
            'elephant', 'bear', 'zebra', 'giraffe', 'N/A', 'backpack', 'umbrella', 'N/A', 'N/A',
            'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
            'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
            'bottle', 'N/A', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl',
            'banana', 'apple', 'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
            'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed', 'N/A', 'dining table',
            'N/A', 'N/A', 'toilet', 'N/A', 'tv', 'laptop', 'mouse', 'remote', 'keyboard', 'cell phone',
            'microwave', 'oven', 'toaster', 'sink', 'refrigerator', 'N/A', 'book',
            'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
        ]
        
    @staticmethod
    def show(imgs):
        if not isinstance(imgs, list):
            imgs = [imgs]
        fix, axs = plt.subplots(ncols=len(imgs), squeeze=False)
        for i, img in enumerate(imgs):
            img = img.detach()
            img = F.to_pil_image(img)
            axs[0, i].imshow(np.asarray(img))
            axs[0, i].set(xticklabels=[], yticklabels=[], xticks=[], yticks=[])
    
    def run(self, infile):
        img = Image.open(infile).convert('RGB')
        img = np.array(img)
        img = np.moveaxis(img, -1, 0)
        img = torch.tensor(img)
        
        batch_img = torch.stack([img])
        batch = convert_image_dtype(batch_img, dtype=torch.float)
        
        outputs = self.model(batch)
        
        img_with_boxes = []
        for img, output in zip(batch_img, outputs):
            idx = output['scores'] > self.score_threshold
            labels = []
            for label_idx in output['labels'][idx]:
                labels.append(self.COCO_INSTANCE_CATEGORY_NAMES[label_idx])
                
            img_with_boxes.append(
                draw_bounding_boxes(img, boxes=output['boxes'][idx], labels=labels, width=4)
            )
        
        output_img = img_with_boxes[0] #默认只有一张图片
        output_img = np.array(output_img)
        output_img = np.moveaxis(output_img, 0, -1)
        return Image.fromarray(output_img)
    
class TextClassifier:
    def __init__(self):
        tokenizer = AutoTokenizer.from_pretrained("uer/roberta-base-finetuned-chinanews-chinese")
        model = AutoModelForSequenceClassification.from_pretrained("uer/roberta-base-finetuned-chinanews-chinese")
        self.classifier = pipeline('sentiment-analysis', model=model, tokenizer=tokenizer, return_all_scores=True)

    def run(self, text):
        return self.classifier(text[:1000])
    
if __name__ == '__main__':
    gen = TextGeneration()
    gen.run_petition()
    
#    objDetection = ObjectDetection()
#    objDetection.run('test_image/kitten.jpg')

