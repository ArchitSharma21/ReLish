# Activation functions

# Imports
import itertools
import functools
import torch
import torch.nn as nn
import torch.nn.functional as F
import util

#
# Activation functions
#

# Note: All JIT-scripted activation functions have an inplace argument, but do not actually support it, because scripted kernel fusions
#       often do not work across in-place operation boundaries. Thus, if any in-place operations are used in the implementation, the
#       performance drops to that of the non-scripted versions (or below).

# Mish: https://arxiv.org/pdf/1908.08681.pdf
class MishJIT(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, inplace=False):
		super().__init__()
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return mish_jit(x)

# noinspection PyUnusedLocal
@torch.jit.script
def mish_jit(x, inplace=False):
	return x.mul(F.softplus(x).tanh())

# E-swish: https://arxiv.org/pdf/1801.07145.pdf
class ESwish(nn.Module):

	__constants__ = ['beta', 'inplace']
	beta: float
	inplace: bool  # Ignored

	def __init__(self, beta=1.25, inplace=False):
		super().__init__()
		self.beta = beta
		self.inplace = inplace

	def forward(self, x):
		return eswish(x, beta=self.beta)

	def extra_repr(self):
		return f"beta={self.beta}"

# noinspection PyUnusedLocal
@torch.jit.script
def eswish(x, beta=1.25, inplace=False):
	return x.mul(x.sigmoid().mul(beta))

# SwishBeta: https://arxiv.org/pdf/1710.05941.pdf
class SwishBeta(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, init_beta=1.0, inplace=False, device=None, dtype=None):
		super().__init__()
		self.inplace = inplace
		factory_kwargs = {'device': device, 'dtype': dtype}
		self.beta = nn.Parameter(torch.tensor(float(init_beta), **factory_kwargs))

	def forward(self, x):
		return swish_beta(x, self.beta)

# noinspection PyUnusedLocal
@torch.jit.script
def swish_beta(x, beta, inplace=False):
	return x.mul(x.mul(beta).sigmoid())

# AltMish: Alternative A considered in mish paper (https://arxiv.org/pdf/1908.08681.pdf)
class AltMishA(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, inplace=False):
		super().__init__()
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return altmisha_jit(x)

# noinspection PyUnusedLocal
@torch.jit.script
def altmisha_jit(x, inplace=False):
	return x.tanh().mul(F.softplus(x))

# AltMish: Alternative B considered in mish paper (https://arxiv.org/pdf/1908.08681.pdf)
class AltMishB(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, inplace=False):
		super().__init__()
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return altmishb_jit(x)

# noinspection PyUnusedLocal
@torch.jit.script
def altmishb_jit(x, inplace=False):
	return x.mul((x.exp().tanh() + 1).log())  # Note: This probably has some numerical gradient issues due to log-of-exp scenario

# ReLish: C1 version, alpha = 1, beta = 1, gamma = 1
class ReLishA(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, inplace=False):
		super().__init__()
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return relisha_jit(x)

# noinspection PyUnusedLocal
@torch.jit.script
def relisha_jit(x, inplace=False):
	return x.mul(x.exp()).where(x < 0, x)

# ReLish: C2 version, alpha = 2, beta = 1, gamma = 1
class ReLishB(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, inplace=False):
		super().__init__()
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return relishb_jit(x)

# noinspection PyUnusedLocal
@torch.jit.script
def relishb_jit(x, inplace=False):
	return x.div(x.cosh()).where(x < 0, x)

# ReLish: C2 version, alpha = 1, beta = 1, gamma = 1
class ReLishC(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, inplace=False):
		super().__init__()
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return relishc_jit(x)

# noinspection PyUnusedLocal
@torch.jit.script
def relishc_jit(x, inplace=False):
	return x.div(x.cosh().mul(2) - 1).where(x < 0, x)

# ReLish: General C1 version
class ReLishG1(nn.Module):

	__constants__ = ['alpha', 'beta', 'gamma', 'inplace']
	alpha: float
	beta: float
	gamma: float
	inplace: bool  # Ignored

	def __init__(self, alpha=1.0, beta=1.0, gamma=1.0, inplace=False):
		super().__init__()
		self.alpha = alpha
		self.beta = beta
		self.gamma = gamma
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return relishg1_jit(x, alpha=self.alpha, beta=self.beta, gamma=self.gamma)

	def extra_repr(self):
		return f"alpha={self.alpha}, beta={self.beta}, gamma={self.gamma}"

# noinspection PyUnusedLocal
@torch.jit.script
def relishg1_jit(x, alpha=1.0, beta=1.0, gamma=1.0, inplace=False):
	gammax = x.mul(gamma)
	return gammax.mul(alpha).div(torch.expm1(x.mul(-beta)) + alpha).where(x < 0, gammax)

# ReLish: General C2 version
class ReLishG2(nn.Module):

	__constants__ = ['alpha', 'beta', 'gamma', 'inplace']
	alpha: float
	beta: float
	gamma: float
	inplace: bool  # Ignored

	def __init__(self, alpha=1.0, beta=1.0, gamma=1.0, inplace=False):
		super().__init__()
		self.alpha = alpha
		self.beta = beta
		self.gamma = gamma
		self.inplace = inplace

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return relishg2_jit(x, alpha=self.alpha, beta=self.beta, gamma=self.gamma)

	def extra_repr(self):
		return f"alpha={self.alpha}, beta={self.beta}, gamma={self.gamma}"

# noinspection PyUnusedLocal
@torch.jit.script
def relishg2_jit(x, alpha=1.0, beta=1.0, gamma=1.0, inplace=False):
	gammax = x.mul(gamma)
	return gammax.mul(alpha).div(x.mul(beta).cosh().mul(2) + (alpha - 2)).where(x < 0, gammax)

# ReLish: Parameterised C1 version
class ReLishP1(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, alpha=True, beta=True, gamma=True, inplace=False, device=None, dtype=None):
		super().__init__()
		self.inplace = inplace
		factory_kwargs = {'device': device, 'dtype': dtype}
		self.alpha = nn.Parameter(torch.tensor(1.0, **factory_kwargs)) if alpha else 1.0
		self.beta = nn.Parameter(torch.tensor(1.0, **factory_kwargs)) if beta else 1.0
		self.gamma = nn.Parameter(torch.tensor(1.0, **factory_kwargs)) if gamma else 1.0

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return relishg1_jit(x, alpha=self.alpha, beta=self.beta, gamma=self.gamma)

	def extra_repr(self):
		return f"alpha={'param' if isinstance(self.alpha, nn.Parameter) else self.alpha}, beta={'param' if isinstance(self.beta, nn.Parameter) else self.beta}, gamma={'param' if isinstance(self.gamma, nn.Parameter) else self.gamma}"

# ReLish: Parameterised C2 version
class ReLishP2(nn.Module):

	__constants__ = ['inplace']
	inplace: bool  # Ignored

	def __init__(self, alpha=True, beta=True, gamma=True, inplace=False, device=None, dtype=None):
		super().__init__()
		self.inplace = inplace
		factory_kwargs = {'device': device, 'dtype': dtype}
		self.alpha = nn.Parameter(torch.tensor(1.0, **factory_kwargs)) if alpha else 1.0
		self.beta = nn.Parameter(torch.tensor(1.0, **factory_kwargs)) if beta else 1.0
		self.gamma = nn.Parameter(torch.tensor(1.0, **factory_kwargs)) if gamma else 1.0

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return relishg2_jit(x, alpha=self.alpha, beta=self.beta, gamma=self.gamma)

	def extra_repr(self):
		return f"alpha={'param' if isinstance(self.alpha, nn.Parameter) else self.alpha}, beta={'param' if isinstance(self.beta, nn.Parameter) else self.beta}, gamma={'param' if isinstance(self.gamma, nn.Parameter) else self.gamma}"

#
# Utilities
#

# TODO: Update the sweep files with the new palette of activation functions
# TODO: Aria-2, Bent's Identity, SQNL, ELisH, Hard ELisH, SReLU, ISRU, ISRLU, Flatten T-Swish, SineReLU, Weighted Tanh, LeCun's Tanh

# Activation function factory map
# noinspection PyArgumentList
act_func_factory_map = {
	'relu': nn.ReLU,
	'relu6': nn.ReLU6,
	'prelu': lambda inplace=False, **kwargs: nn.PReLU(**kwargs),  # Note: Single learnable parameter is shared between all input channels, ideally do not use weight decay with this
	'rrelu': nn.RReLU,
	'threshold': functools.partial(nn.Threshold, threshold=-1.0, value=-1.0),
	'elu': functools.partial(nn.ELU, alpha=1.0),
	'celu': functools.partial(nn.CELU, alpha=0.5),  # Note: alpha = 1.0 would make CELU equivalent to ELU
	'selu': nn.SELU,
	'gelu-exact': lambda inplace=False, **kwargs: nn.GELU(approximate='none', **kwargs),
	'gelu-approx': lambda inplace=False, **kwargs: nn.GELU(approximate='tanh', **kwargs),
	'silu': nn.SiLU,
	'swish-beta': SwishBeta,
	'hardswish': nn.Hardswish,
	'mish': nn.Mish,
	'mish-jit': MishJIT,
	'sigmoid': lambda inplace=False, **kwargs: nn.Sigmoid(**kwargs),
	'hardsigmoid': nn.Hardsigmoid,
	'logsigmoid': lambda inplace=False, **kwargs: nn.LogSigmoid(**kwargs),
	'softshrink': lambda inplace=False, **kwargs: nn.Softshrink(lambd=0.5, **kwargs),
	'hardshrink': lambda inplace=False, **kwargs: nn.Hardshrink(lambd=0.5, **kwargs),
	'tanh': lambda inplace=False, **kwargs: nn.Tanh(**kwargs),
	'tanhshrink': lambda inplace=False, **kwargs: nn.Tanhshrink(**kwargs),
	'hardtanh': nn.Hardtanh,
	'softsign': lambda inplace=False, **kwargs: nn.Softsign(**kwargs),
	'softplus': lambda inplace=False, **kwargs: nn.Softplus(beta=1, **kwargs),
	'altmisha': AltMishA,
	'altmishb': AltMishB,
	'relisha': ReLishA,
	'relishb': ReLishB,
	'relishc': ReLishC,
}
act_func_extra_map = {
	'leakyrelu': ('leakyrelu-0.01', 'leakyrelu-0.05', 'leakyrelu-0.25'),
	'eswish': ('eswish-1.25', 'eswish-1.5', 'eswish-1.75'),
	'relishg1': ('relishg1-0.55-0.91-1.5',),
	'relishg2': ('relishg2-0.55-0.91-1.5',),
	'relishp1': ('relishp1-ppf', 'relishp1-ffp', 'relishp1-ppp'),
	'relishp2': ('relishp2-ppf', 'relishp2-ffp', 'relishp2-ppp'),
}
act_funcs = tuple(itertools.chain(act_func_factory_map.keys(), itertools.chain.from_iterable(act_func_extra_map.values())))

# Get a factory callable for a given activation function
def get_act_func_factory(name):
	# Returns a callable that accepts an 'inplace' keyword argument (and possibly other keyword arguments as well)
	factory = act_func_factory_map.get(name, None)
	if factory is not None:
		return factory
	elif name.startswith('leakyrelu-'):
		negative_slope = util.parse_value(name[10:], default=0.01, error="Invalid leaky ReLU negative slope specification")
		return functools.partial(nn.LeakyReLU, negative_slope=negative_slope)
	elif name.startswith('eswish-'):
		beta = util.parse_value(name[7:], default=1.25, error="Invalid E-swish beta specification")
		return functools.partial(ESwish, beta=beta)
	elif name.startswith('relishg1-'):
		params = name[9:].split('-')
		alpha = util.parse_value(params[0] if len(params) >= 1 else None, default=1.0, error="Invalid ReLish G1 alpha specification")
		beta = util.parse_value(params[1] if len(params) >= 2 else None, default=1.0, error="Invalid ReLish G1 beta specification")
		gamma = util.parse_value(params[2] if len(params) >= 3 else None, default=1.0, error="Invalid ReLish G1 gamma specification")
		return functools.partial(ReLishG1, alpha=alpha, beta=beta, gamma=gamma)
	elif name.startswith('relishg2-'):
		params = name[9:].split('-')
		alpha = util.parse_value(params[0] if len(params) >= 1 else None, default=1.0, error="Invalid ReLish G2 alpha specification")
		beta = util.parse_value(params[1] if len(params) >= 2 else None, default=1.0, error="Invalid ReLish G2 beta specification")
		gamma = util.parse_value(params[2] if len(params) >= 3 else None, default=1.0, error="Invalid ReLish G2 gamma specification")
		return functools.partial(ReLishG2, alpha=alpha, beta=beta, gamma=gamma)
	elif name.startswith('relishp1-'):
		if len(name) != 12 or any(c not in 'fp' for c in name[9:]):
			raise ValueError("Invalid ReLish P1 specification")
		alpha, beta, gamma = (c == 'p' for c in name[9:])
		return functools.partial(ReLishP1, alpha=alpha, beta=beta, gamma=gamma)
	elif name.startswith('relishp2-'):
		if len(name) != 12 or any(c not in 'fp' for c in name[9:]):
			raise ValueError("Invalid ReLish P2 specification")
		alpha, beta, gamma = (c == 'p' for c in name[9:])
		return functools.partial(ReLishP2, alpha=alpha, beta=beta, gamma=gamma)
	else:
		raise ValueError(f"Invalid activation function specification: {name}")
# EOF