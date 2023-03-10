# Models

# Imports
import fractions
from typing import Union, Type, Tuple
import torch
import torch.nn as nn
import torchvision.models

#
# Classification models
#

# Fully connected classification network
class FCNet(nn.Module):

	def __init__(self, in_features, num_classes, num_layers, layer_features=384, act_func_factory=None, dropout_prob=0.2):
		super().__init__()
		if act_func_factory is None:
			act_func_factory = nn.ReLU
		self.layers = nn.Sequential(
			self._layer_block(in_features, layer_features, act_func_factory, dropout_prob),
			*(self._layer_block(layer_features, layer_features, act_func_factory, dropout_prob) for _ in range(num_layers - 1)),
			nn.Linear(in_features=layer_features, out_features=num_classes, bias=True),
		)

	@classmethod
	def _layer_block(cls, in_features, out_features, act_func_factory, dropout_prob):
		return nn.Sequential(
			nn.Linear(in_features=in_features, out_features=out_features, bias=False),
			nn.BatchNorm1d(num_features=out_features),
			act_func_factory(inplace=True),
			nn.Dropout1d(p=dropout_prob),
		)

	def forward(self, x):
		return self.layers(torch.flatten(x, 1))

# WideResNet classification network (generalisation of version from original paper, also correcting the counting of network depth)
class WideResNet(nn.Module):

	def __init__(self, num_classes, in_channels=3, width=10, depth=26, groups=3, thickness=16, dropout_prob=0, act_func_factory=None):
		super().__init__()

		if act_func_factory is None:
			act_func_factory = nn.ReLU
		num_blocks = (depth - 2) // (2 * groups)
		if 2 * groups * num_blocks + 2 != depth:
			raise ValueError(f"Depth must be of the format {2 * groups}B+2 for integer B")
		widths = (thickness, *(thickness * width * 2 ** g for g in range(groups)))

		self.conv0 = nn.Conv2d(in_channels=in_channels, out_channels=widths[0], kernel_size=(3, 3), padding=1, bias=False)
		self.groups = nn.Sequential(*(self.create_group(in_channels=widths[g], out_channels=widths[g + 1], num_blocks=num_blocks, stride=1 if g == 0 else 2, dropout_prob=dropout_prob, act_func_factory=act_func_factory) for g in range(groups)))
		self.bn = nn.BatchNorm2d(num_features=widths[-1], affine=True, track_running_stats=True)
		self.act_func = act_func_factory(inplace=True)
		self.avgpool = nn.AdaptiveAvgPool2d(output_size=(1, 1))
		self.fc = nn.Linear(in_features=widths[-1], out_features=num_classes, bias=True)

		for m in self.modules():
			if isinstance(m, nn.Conv2d):
				nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
			elif isinstance(m, nn.BatchNorm2d):
				nn.init.constant_(m.weight, 1)
				nn.init.constant_(m.bias, 0)

	def forward(self, x):
		x = self.conv0(x)
		x = self.groups(x)
		x = self.act_func(self.bn(x))
		x = self.avgpool(x)
		x = torch.flatten(x, 1)
		x = self.fc(x)
		return x

	@classmethod
	def create_group(cls, in_channels, out_channels, num_blocks, stride, dropout_prob, act_func_factory):
		blocks = [cls.Block(in_channels=in_channels, out_channels=out_channels, stride=stride, dropout_prob=dropout_prob, act_func_factory=act_func_factory)]
		blocks.extend(cls.Block(in_channels=out_channels, out_channels=out_channels, stride=1, dropout_prob=dropout_prob, act_func_factory=act_func_factory) for _ in range(1, num_blocks))
		return nn.Sequential(*blocks)

	class Block(nn.Module):

		def __init__(self, in_channels, out_channels, stride, dropout_prob, act_func_factory):
			super().__init__()
			self.bn0 = nn.BatchNorm2d(num_features=in_channels, affine=True, track_running_stats=True)
			self.act_func = act_func_factory(inplace=True)
			self.conv0 = nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=(3, 3), stride=stride, padding=1, bias=False)
			self.dropout = None if dropout_prob <= 0 else nn.Dropout2d(p=dropout_prob, inplace=True)
			self.bn1 = nn.BatchNorm2d(num_features=out_channels, affine=True, track_running_stats=True)
			self.conv1 = nn.Conv2d(in_channels=out_channels, out_channels=out_channels, kernel_size=(3, 3), stride=(1, 1), padding=1, bias=False)
			self.convdim = None if in_channels == out_channels else nn.Conv2d(in_channels=in_channels, out_channels=out_channels, kernel_size=(1, 1), stride=stride, bias=False)

		def forward(self, x):
			y = self.act_func(self.bn0(x))
			o = self.conv0(y)
			if self.dropout:
				o = self.dropout(o)
			o = self.act_func(self.bn1(o))
			o = self.conv1(o)
			if self.convdim:
				return o + self.convdim(y)
			else:
				return o + x

# Swin Transformer large model
def swin_l(**kwargs):
	# noinspection PyProtectedMember
	return torchvision.models.swin_transformer._swin_transformer(
		patch_size=[4, 4],
		embed_dim=192,
		depths=[2, 2, 18, 2],
		num_heads=[6, 12, 24, 48],
		window_size=[7, 7],
		stochastic_depth_prob=0.5,
		weights=None,
		progress=True,
		**kwargs,
	)

#
# Modules
#

# Module that simply passes through a tensor
class Identity(nn.Module):

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return x

# Module that simply clones a tensor
class Clone(nn.Module):

	# noinspection PyMethodMayBeStatic
	def forward(self, x):
		return x.clone()

#
# Utilities
#

# Execute pending actions
def execute_pending_actions(actions):
	for func, *args in actions:
		func(*args)

# Enqueue pending actions to scale the channels of a network by a certain fractional factor
def pending_scale_channels(module, actions, factor: fractions.Fraction, skip_inputs, skip_outputs):
	# noinspection PyProtectedMember
	for attr_key in module._modules.keys():
		submodule = getattr(module, attr_key)
		submodule_class = type(submodule)
		if submodule_class == nn.Conv2d:
			scale_input = submodule not in skip_inputs
			scale_output = submodule not in skip_outputs
			if scale_input or scale_output:
				replace_conv2d(module, attr_key, dict(
					in_channels=scale_by_factor(submodule.in_channels, factor) if scale_input else submodule.in_channels,
					out_channels=scale_by_factor(submodule.out_channels, factor) if scale_output else submodule.out_channels,
				), submodule=submodule, actions=actions)
		elif submodule_class == nn.BatchNorm2d:
			if submodule not in skip_inputs:
				device, dtype = (submodule.weight.device, submodule.weight.dtype) if submodule.weight is not None else (submodule.running_mean.device, submodule.running_mean.dtype) if submodule.running_mean is not None else (None, None)
				actions.append((replace_submodule, module, attr_key, submodule_class, (), dict(
					num_features=scale_by_factor(submodule.num_features, factor),
					eps=submodule.eps,
					momentum=submodule.momentum,
					affine=submodule.affine,
					track_running_stats=submodule.track_running_stats,
					device=device,
					dtype=dtype,
				)))
		elif submodule_class == nn.Linear:
			scale_input = submodule not in skip_inputs
			scale_output = submodule not in skip_outputs
			if scale_input or scale_output:
				actions.append((replace_submodule, module, attr_key, submodule_class, (), dict(
					in_features=scale_by_factor(submodule.in_features, factor) if scale_input else submodule.in_features,
					out_features=scale_by_factor(submodule.out_features, factor) if scale_output else submodule.out_features,
					bias=submodule.bias is not None,
					device=submodule.weight.device,
					dtype=submodule.weight.dtype,
				)))

# Enqueue pending actions to change the stride of all convolutions to (1, 1)
def pending_destride(module, actions):
	# noinspection PyProtectedMember
	for attr_key in module._modules.keys():
		submodule = getattr(module, attr_key)
		submodule_class = type(submodule)
		if submodule_class == nn.Conv2d and submodule.stride != (1, 1):
			replace_conv2d(module, attr_key, dict(stride=(1, 1)), submodule, actions=actions)

# Enqueue pending actions to replace certain activation functions with another activation function type
def pending_replace_act_func(module, actions, act_func_classes: Union[Type, Tuple[Type, ...]], factory, klass):
	# noinspection PyProtectedMember
	for attr_key in module._modules.keys():
		submodule = getattr(module, attr_key)
		if isinstance(submodule, act_func_classes):
			if submodule.__class__ != klass:
				actions.append((replace_submodule, module, attr_key, factory, (), dict(inplace=getattr(submodule, 'inplace', False))))

# Replace a module with a new one (pending action if actions is provided)
def replace_module(module, attr_key, factory_kwargs, replace_kwargs, submodule, actions=None):
	kwargs = dict(factory_kwargs)
	kwargs.update(replace_kwargs)
	if kwargs != factory_kwargs:
		if actions is None:
			replace_submodule(module, attr_key, type(submodule), (), kwargs)
		else:
			actions.append((replace_submodule, module, attr_key, type(submodule), (), kwargs))

# Replace a nn.Conv2D with a new one (pending action if actions is provided)
def replace_conv2d(module, attr_key, replace_kwargs, submodule=None, actions=None):
	if submodule is None:
		submodule = getattr(module, attr_key)
	replace_module(module, attr_key, dict(
		in_channels=submodule.in_channels,
		out_channels=submodule.out_channels,
		kernel_size=submodule.kernel_size,
		stride=submodule.stride,
		padding=submodule.padding,
		dilation=submodule.dilation,
		groups=submodule.groups,
		bias=submodule.bias is not None,
		padding_mode=submodule.padding_mode,
		device=submodule.weight.device,
		dtype=submodule.weight.dtype,
	), replace_kwargs, submodule, actions=actions)

# Replace a nn.MaxPool2d with a new one or identity (pending action if actions is provided)
def replace_maxpool2d(module, attr_key, replace_kwargs, identity=False, submodule=None, actions=None):
	if identity:
		if actions is None:
			replace_submodule(module, attr_key, Identity, (), {})
		else:
			actions.append((replace_submodule, module, attr_key, Identity, (), {}))
	else:
		if submodule is None:
			submodule = getattr(module, attr_key)
		replace_module(module, attr_key, dict(
			kernel_size=submodule.kernel_size,
			stride=submodule.stride,
			padding=submodule.padding,
			dilation=submodule.dilation,
			return_indices=submodule.return_indices,
			ceil_mode=submodule.ceil_mode,
		), replace_kwargs, submodule, actions=actions)

# Replace a submodule with another new one
def replace_submodule(module, attr_key, factory, factory_args, factory_kwargs):
	setattr(module, attr_key, factory(*factory_args, **factory_kwargs))

# Helper for applying a fractional scale factor to an integer
def scale_by_factor(value: int, factor: fractions.Fraction):
	scaled_value = value * factor
	if scaled_value.denominator != 1:
		raise ValueError(f"Scaling {value} by {factor} does not result in an integer output")
	return scaled_value.numerator
# EOF
