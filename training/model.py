"""A small multi-layer perceptron (MLP) for node classification."""
import torch
from torch import nn

ACTIVATIONS = {"relu": nn.ReLU, "tanh": nn.Tanh, "sigmoid": nn.Sigmoid, "leaky_relu": nn.LeakyReLU}


class MLP(nn.Module):
    """input -> [Linear -> activation -> Dropout] x n_layers -> Linear (one logit per class)."""

    def __init__(self, n_in, n_classes, hidden=128, n_layers=1, activation="relu", dropout=0.3):
        super().__init__()
        layers, d = [], n_in
        for _ in range(n_layers):
            layers += [nn.Linear(d, hidden), ACTIVATIONS[activation](), nn.Dropout(dropout)]
            d = hidden
        layers.append(nn.Linear(d, n_classes))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)  # raw logits; softmax is folded into the cross-entropy loss
