"""HW3 design: a weight-tied two-branch encoder with a learned gate on the neighbour branch.

The HW2 MLP sees one flat vector  [own-title TF-IDF | neighbour-mean TF-IDF | journal one-hot]  and its first layer is

    h = ReLU(W_self x_self + W_nbr x_nbr + W_j x_j + b)            (HW2 baseline: untied weights, fixed addition)

x_self and x_nbr live in the *same* vocabulary space, yet the baseline learns two unrelated weight matrices for them.
The HW3 design shares one encoder E between the two branches and lets the network decide how much neighbour
information to add, in the spirit of a residual connection (own title = main path, neighbours = correction):

    h_self = E(x_self),  h_nbr = E(x_nbr)                           (tied: same weights for both branches)
    g      = sigmoid(a . [h_self, h_nbr] + c)                       (one gate value per paper, in (0, 1))
    h      = ReLU(h_self + g * h_nbr + W_j x_j)

Switches (`tied`, `gate`) turn each ingredient on/off so every ablation is the same code path:
    tied=False, gate="none"   -> mathematically the HW2 baseline (up to one redundant bias)
    gate="none"   fixed addition (g = 1)        gate="scalar"  one learned number shared by all papers
    gate="node"   per-paper gate (the design)   gate="zero"    neighbour branch removed (g = 0)
"""
import torch
from torch import nn


class GatedBranchNet(nn.Module):
    def __init__(self, n_text, n_journal, n_classes, hidden=64, dropout=0.3, tied=True, gate="node"):
        super().__init__()
        assert gate in ("node", "scalar", "none", "zero")
        self.n_text, self.gate_mode = n_text, gate
        self.enc_self = nn.Linear(n_text, hidden)
        self.enc_nbr = self.enc_self if tied else nn.Linear(n_text, hidden)  # tied -> the very same module
        self.enc_journal = nn.Linear(n_journal, hidden, bias=False)
        if gate == "node":
            self.gate = nn.Linear(2 * hidden, 1)
        elif gate == "scalar":
            self.gate_logit = nn.Parameter(torch.zeros(1))
        self.drop = nn.Dropout(dropout)
        self.out = nn.Linear(hidden, n_classes)
        self.last_gate = None  # gate values of the most recent forward pass (for analysis only)

    def gate_values(self, h_self, h_nbr):
        if self.gate_mode == "node":
            return torch.sigmoid(self.gate(torch.cat([h_self, h_nbr], dim=1)))  # [batch, 1]
        if self.gate_mode == "scalar":
            return torch.sigmoid(self.gate_logit).expand(h_self.shape[0], 1)
        return torch.full((h_self.shape[0], 1), 1.0 if self.gate_mode == "none" else 0.0)

    def forward(self, x):
        t = self.n_text
        x_self, x_nbr, x_j = x[:, :t], x[:, t:2 * t], x[:, 2 * t:]
        h_self, h_nbr = self.enc_self(x_self), self.enc_nbr(x_nbr)
        g = self.gate_values(h_self, h_nbr)
        self.last_gate = g.detach()
        h = torch.relu(h_self + g * h_nbr + self.enc_journal(x_j))
        return self.out(self.drop(h))


def count_params(model):
    return sum(p.numel() for p in model.parameters())
