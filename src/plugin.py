#!/usr/bin/python
# coding=utf-8
#
# Copyright (C) 2018-2024 by dream-alpha
#
# In case of reuse of this source code please do not remove this copyright.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For more information on the GNU General Public License see:
# <http://www.gnu.org/licenses/>.


from Plugins.Plugin import PluginDescriptor
from .Debug import logger
from .Version import VERSION
from .MountCockpit import MountCockpit
from .ConfigInit import ConfigInit


def autoStart(reason, **__):
	if reason == 0:
		logger.info("--- startup")
		MountCockpit()
	elif reason == 1:
		logger.info("--- shutdown")
	else:
		logger.info("reason not handled: %s", reason)


def Plugins(**__):
	logger.info("  +++ Version: %s starts...", VERSION)
	ConfigInit()
	descriptors = [
		PluginDescriptor(
			where=[
				PluginDescriptor.WHERE_AUTOSTART
			],
			fnc=autoStart
		)
	]
	return descriptors