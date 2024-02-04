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


import os
from enigma import eTimer, eConsoleAppContainer
from Components.config import config
from .Debug import logger
from .MountUtils import parseMounts, getBookmarkSpaceInfo
from .AutoMount import iAutoMount
from .DelayTimer import DelayTimer


instance = None
POLL_TIME = 5000


class MountCockpit():

	def __init__(self):
		self.ping_timer = eTimer()
		self.ping_timer_conn = self.ping_timer.timeout.connect(self.executePing)
		self.ping_container = eConsoleAppContainer()
		self.ping_stdoutAvail_conn = self.ping_container.stdoutAvail.connect(self.stdoutPingData)
		self.ping_stderrAvail_conn = self.ping_container.stderrAvail.connect(self.stderrPingData)
		self.ping_container_appClosed_conn = self.ping_container.appClosed.connect(self.finishedPing)
		self.bookmarks = {}
		self.mounts_table = {}
		self.ping_commands = ""
		self.shares_changed = []
		self.init_counter = 0
		self.init_complete = False
		self.init_complete_callback = None
		config.plugins.mountcockpit.enabled.addNotifier(self.onMountCockpitEnabledChange, initial_call=False)

	@staticmethod
	def getInstance():
		global instance
		if instance is None:
			instance = MountCockpit()
		return instance

	def registerBookmarks(self, plugin, bookmarks):
		logger.debug("plugin: %s, bookmarks: %s", plugin, bookmarks)
		self.bookmarks[plugin] = []
		for bookmark in bookmarks:
			bookmark = os.path.normpath(bookmark)
			if bookmark not in self.bookmarks[plugin]:
				self.bookmarks[plugin].append(bookmark)
		self.onMountsChange()
		if config.plugins.mountcockpit.enabled.value or not self.init_complete:
			self.startPolling()

	def onMountCockpitEnabledChange(self):
		if config.plugins.mountcockpit.enabled.value:
			self.startPolling()
		else:
			self.stopPolling()

	def onInitComplete(self, callback):
		self.init_complete_callback = callback
		if self.init_complete:
			self.init_complete_callback()
			self.init_complete_callback = None

	def check4InitComplete(self):
		self.init_counter += 1
		logger.debug("init_counter: %s", self.init_counter)
		if not self.init_complete and (not self.ping_commands or self.init_counter == 2):
			logger.debug("initialization complete")
			self.init_complete = True
			if self.init_complete_callback:
				DelayTimer(1000, self.init_complete_callback)
				self.init_complete_callback = None

	def initPingCommands(self):
		logger.debug("iAutoMount.mounts: %s", iAutoMount.mounts)
		ping_ips = []
		self.ping_commands = ""
		for sharename in iAutoMount.mounts:
			ip = iAutoMount.mounts[sharename]["ip"]
			if ip not in ping_ips:
				ping_ips.append(ip)
				if self.ping_commands:
					self.ping_commands += ";"
				self.ping_commands += "ping -c1 -w1 " + ip
		logger.debug("ping_commands: %s", self.ping_commands)

	def onMountsChange(self, _reason=None):
		logger.info("bookmarks: % s", self.bookmarks)
		self.init_complete = False
		self.init_counter = 0
		self.shares_changed = []
		mount_points = parseMounts()
		self.mounts_table = {}
		for _plugin, bookmarks in list(self.bookmarks.items()):
			for __bookmark in bookmarks:
				mount_point = None
				for __mount_point in mount_points:
					if os.path.realpath(__bookmark).startswith(__mount_point):
						mount_point = __mount_point
						break
				if mount_point is not None:
					self.mounts_table[__bookmark] = mount_point
		logger.info("bookmarks: %s", self.bookmarks)
		logger.info("mounts_table: %s", self.mounts_table)
		self.initPingCommands()
		self.check4InitComplete()

	# ping loop

	def stdoutPingData(self, data):
		# logger.info("...")
		# logger.info("data: %s", data)
		lines = data.splitlines()
		ip = packets = None
		for line in lines:
			line = " ".join(line.split())
			words = line.split(" ")
			if not ip and "PING" in line:
				ip = words[1]
			elif "packets received" in line:
				packets = int(words[3])
			if ip is not None and packets is not None:
				for sharename in iAutoMount.mounts:
					if iAutoMount.mounts[sharename]["ip"] == ip:
						if packets == 0:
							# logger.debug("%s (%s) is offline", sharename, ip)
							if iAutoMount.mounts[sharename]["active"]:
								iAutoMount.mounts[sharename]["active"] = False
								self.shares_changed.append(sharename)
						else:
							# logger.debug("%s (%s) is online", sharename, ip)
							if not iAutoMount.mounts[sharename]["active"]:
								iAutoMount.mounts[sharename]["active"] = True
								self.shares_changed.append(sharename)
				ip = packets = None
		for sharename in iAutoMount.mounts:
			logger.debug("sharename: %s, ip: %s, active: %s", sharename, iAutoMount.mounts[sharename]["ip"], iAutoMount.mounts[sharename]["active"])

	def stderrPingData(self, data):
		logger.info("data: %s", data)

	def executePing(self):
		if self.ping_commands:
			# logger.debug("ping_commands: %s", self.ping_commands)
			self.ping_container.execute(self.ping_commands)

	def finishedPing(self, _ret_val=None):
		# logger.debug("shares_changed: %s", self.shares_changed)
		if self.shares_changed:
			iAutoMount.apply(self.shares_changed, self.onMountsChange)
			iAutoMount.save()
		else:
			self.check4InitComplete()

	# polling

	def startPolling(self):
		self.executePing()
		self.ping_timer.stop()
		self.ping_timer.start(POLL_TIME)

	def stopPolling(self):
		self.ping_container.kill()
		self.ping_timer.stop()

	# mount point

	def getMountPoint(self, plugin, path):
		mount_point = None
		bookmark = self.getBookmark(plugin, path)
		if bookmark in self.mounts_table:
			mount_point = self.mounts_table[bookmark]
		logger.debug("path: %s, mount_point: %s", path, mount_point)
		return mount_point

	def sameMountPoint(self, plugin, path1, path2):
		return self.getMountPoint(plugin, path1) == self.getMountPoint(plugin, path2)

	# bookmark

	def isBookmark(self, path):
		is_bookmark = path in self.mounts_table
		logger.debug("path: %s, is_bookmark: %s", path, is_bookmark)
		return is_bookmark

	def getBookmark(self, plugin, path):
		# logger.debug("plugin: %s, path: %s", plugin, path)
		# logger.debug("self.bookmarks: %s", self.bookmarks[plugin])
		bookmark = None
		for __bookmark in self.bookmarks[plugin]:
			__bookmark = os.path.normpath(__bookmark)
			if path.startswith(__bookmark):
				bookmark = __bookmark
				break
		logger.debug("path: %s, bookmark: %s", path, bookmark)
		return bookmark

	def getMountedBookmarks(self, plugin):
		mounted_bookmarks = []
		if plugin in self.bookmarks:
			for bookmark in self.bookmarks[plugin]:
				if self.getMountPoint(plugin, bookmark):
					mounted_bookmarks.append(bookmark)
		logger.debug("plugin: %s, mounted_bookmarks: %s", plugin, mounted_bookmarks)
		return mounted_bookmarks

	def getBookmarksSpaceInfo(self, plugin):
		space_info = ""
		short_bookmarks = []
		for __bookmark in self.bookmarks[plugin]:
			short_bookmark = os.path.dirname(__bookmark)[len("/media/"):]
			if short_bookmark not in short_bookmarks:
				used_percent, used, available = getBookmarkSpaceInfo(__bookmark)
				if used >= 0 and available >= 0:
					if space_info != "":
						space_info += ", "
					space_info += short_bookmark + (": %.1f" % used_percent) + "%"
				short_bookmarks.append(short_bookmark)
		return space_info

	def getHomeDir(self, plugin):
		home = ""
		mounted_bookmarks = self.getMountedBookmarks(plugin)
		if mounted_bookmarks:
			home = mounted_bookmarks[0]
		logger.debug("home: %s", home)
		return home

	def getVirtualDirs(self, plugin, dirs):
		logger.info("plugin: %s, dirs: %s", plugin, dirs)
		bookmarks = self.getMountedBookmarks(plugin)
		all_dirs = []
		for adir in dirs:
			abookmark = self.getBookmark(plugin, adir)
			if abookmark:
				movie_dir = adir[len(abookmark):]
				for bookmark in bookmarks:
					bdir = os.path.normpath(bookmark + movie_dir)
					if bdir not in all_dirs:
						all_dirs.append(bdir)
		logger.debug("all_dirs: %s", all_dirs)
		return all_dirs
