import torchvision.models as models
import torch.nn as nn


# Modify ResNet50 CNN architecture
class ResNet50_ImageEmbedder(nn.Module):
    def __init__(self):
        super(ResNet50_ImageEmbedder, self).__init__()

        self.model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
        self.model = nn.Sequential(
            *list(self.model.children())[:-1]  # remove classifier layer
        )

    def forward(self, x):
        return self.model(x)


def get_transforms():
    return models.ResNet50_Weights.DEFAULT.transforms()
