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


import os
from Components.Harddisk import Util
from Debug import logger
from FileUtils import readFile


ignore_mount_points = ("/", "none", "/proc", "/sys", "/dev/pts", "/dev", "/dev/shm", "/run", "/sysfscgroup", "/tmp", "/var/volatile")


def parseMounts():
	mount_points = []
	fstab_mounts = parseMountFile("/etc/fstab")
	proc_mounts = parseMountFile("/proc/mounts")
	for mount_point in fstab_mounts:
		if mount_point in proc_mounts:
			mount_points.append(mount_point)
	logger.debug("mount_points: %s", mount_points)
	return mount_points


def parseMountFile(path):
	mount_points = []
	lines = readFile(path).splitlines()
	for line in lines:
		_, mount_point, _, _, _, _ = Util.parseFstabLine(line)
		if mount_point not in ignore_mount_points:
			mount_points.append(mount_point)
	logger.debug("mount_points: %s", mount_points)
	return mount_points


def getBookmarkSpaceInfo(path):
	try:
		st = os.statvfs(path)
		free = (st.f_bavail * st.f_frsize)
		total = (st.f_blocks * st.f_frsize)
		used = (st.f_blocks - st.f_bfree) * st.f_frsize
		percent_used = round((float(used) / total) * 100, 1) if total > 0 else 0
	except Exception:
		free = -1
		total = -1
		used = -1
		percent_used = -1
	return percent_used, used, free
