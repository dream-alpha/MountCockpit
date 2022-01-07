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


from Version import ID, PLUGIN, VERSION
import logging
import os
import sys
import time
from DebugInit import getDebugLogLevel, getDebugLogDir

logger = None
streamer = None
format_string = (ID + ": " + "%(levelname)s: %(filename)s: %(funcName)s: %(message)s")


def initLogging():
	global logger
	global streamer
	if not logger:
		logger = logging.getLogger(ID)
		formatter = logging.Formatter(format_string)
		streamer = logging.StreamHandler(sys.stdout)
		streamer.setFormatter(formatter)
		logger.addHandler(streamer)
		logger.propagate = False
		setLogLevel(getDebugLogLevel())
		logger.info("********** %s %s **********", PLUGIN, VERSION)


def setLogLevel(level):
	logger.setLevel(level)
	streamer.setLevel(level)


def createLogFile():
	log_dir = getDebugLogDir()
	log_file = os.path.join(log_dir, ID + "_" + time.strftime("%Y%m%d_%H%M%S" + ".log"))
	logger.info("log_file: %s", log_file)
	if os.path.exists(log_dir):
		os.popen("journalctl | grep " + ID + " > " + log_file)
	else:
		logger.error("log dir does not exist: %s", log_dir)
