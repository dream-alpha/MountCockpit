#!/usr/bin/python
# coding=utf-8
#
# Copyright (C) 2018-2022 by dream-alpha
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


import logging
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigText


log_levels = {"ERROR": logging.ERROR, "INFO": logging.INFO, "DEBUG": logging.DEBUG}

# use moviecockpit debug settings


def getDebugLogDir():
	config.plugins.moviecockpit.debug_log_path = ConfigText(default="/media/hdd", fixed_size=False, visible_width=35)
	return config.plugins.moviecockpit.debug_log_path.value


def getDebugLogLevel():
	config.plugins.moviecockpit = ConfigSubsection()
	config.plugins.moviecockpit.debug_log_level = ConfigSelection(default="INFO", choices=log_levels.keys())
	return log_levels[config.plugins.moviecockpit.debug_log_level.value]
