import json
import os
import sys

import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image

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
        
if __name__ == '__main__':
    img_cls = imageClassifier()
    img_cls.run(sys.argv[1])
    
