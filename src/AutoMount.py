#!/usr/bin/python
# coding: utf-8
import os
from copy import deepcopy
from xml.etree.cElementTree import parse as cet_parse
from Components.Console import Console
from Components.Harddisk import harddiskmanager, Util
from Tools.Directories import isMount, removeDir, createDir
from .Debug import logger


XML_FSTAB = "/etc/enigma2/automounts.xml"


class AutoMount():
	MOUNT_BASE = "/media/"
	DEFAULT_OPTIONS_NFS = {
		"isMounted": False, "active": False, "ip": "192.168.0.1", "sharename": "Sharename", "sharedir": "/export/hdd", "username": "",
		"password": "", "mounttype" : "nfs", "options" : "rw,nolock,tcp", "hdd_replacement" : False
	}
	DEFAULT_OPTIONS_CIFS = {
		"isMounted": False, "active": False, "ip": "192.168.0.1", "sharename": "Sharename", "sharedir": "/export/hdd", "username": "",
		"password": "", "mounttype" : "cifs", "options" : "rw", "hdd_replacement" : False
	}

	def __init__(self):
		self._mounts = {}
		self._console = Console()
		self._numActive = 0
		self.reload(deactivate=True)
		self.save()

	def _getAutoMounts(self):
		return self._mounts

	def _setAutoMounts(self, automounts):
		self._mounts = automounts

	mounts = property(_getAutoMounts)  # , _setAutoMounts)

	def _parse(self, tree, types, defaults):
		def setFromTag(parent, key, data, abool=False):
			elements = parent.findall(key)
			if elements:
				val = elements[0].text
				if abool:
					val = val == "True"
				if val is not None:
					data[key] = val

		keys = ["active", "hdd_replacement", "ip", "sharedir", "sharename", "options", "username", "password"]
		bool_keys = ["active", "hdd_replacement"]
		for i, _item in enumerate(types):
			mounttype = types[i]
			for parent in tree.findall(mounttype):
				for mount in parent.findall("mount"):
					data = deepcopy(defaults[i])
					try:
						for key in keys:
							setFromTag(mount, key, data, key in bool_keys)
						logger.debug("%s share %s", mounttype.upper(), data)
						if data["active"]:
							self._numActive += 1
						# Workaround for nfs shares previously being saved without their leading /
						if mounttype == "nfs" and not data["sharedir"].startswith("/"):
							data["sharedir"] = "/%s" % data["sharedir"]
						self._mounts[data["sharename"]] = data
					except Exception as e:
						logger.warning("Error reading %s share: %s", mounttype.upper(), e)

	def load(self):
		self._mounts = {}
		self._numActive = 0
		if os.path.exists(XML_FSTAB):
			try:
				tree = cet_parse(XML_FSTAB).getroot()
				self._parse(tree, ["nfs", "cifs"], [AutoMount.DEFAULT_OPTIONS_NFS, AutoMount.DEFAULT_OPTIONS_CIFS])
			except Exception as msg:
				logger.error("error msg: %s", msg)
		logger.info("mounts.keys(): %s", list(self._mounts.keys()))

	def reload(self, callback=None, deactivate=False):
		self.load()
		if self._mounts:
			for sharename in self._mounts:
				if deactivate:
					self._mounts[sharename]["active"] = False
				self._applyShare(self._mounts[sharename])
			self._reloadSystemd(callback=self._onSharesApplied)
			logger.debug("self._mounts: %s", self._mounts)
			if callback is not None:
				callback(True)

	def apply(self, shares_changed, callback=None):
		logger.info("shares_changed: %s", shares_changed)
		for sharename in shares_changed:
			self._applyShare(self._mounts[sharename])
		self._reloadSystemd(callback=self._onSharesApplied)
		logger.debug("self._mounts: %s", self._mounts)
		if callback is not None:
			callback(True)

	def sanitizeOptions(self, options, cifs=False):
		self._ensureOption(options, "x-systemd.automount")
		self._ensureOption(options, "rsize", "rsize=8192")
		self._ensureOption(options, "wsize", "wsize=8192")
		self._ensureOption(options, "x-systemd.device-timeout", "x-systemd.device-timeout=5")
		self._ensureOption(options, "x-systemd.idle-timeout", "x-systemd.idle-timeout=10")
		self._ensureOption(options, "soft")
		if not cifs:
			self._ensureOption(options, "retry", "retry=0")
			self._ensureOption(options, "retrans", "retrans=1")
			self._ensureOption(options, "timeo", "timeo=2")
			if "tcp" not in options and "udp" not in options:
				options.append("tcp")

		return options

	def _ensureOption(self, options, key, default=None):
		if default is None:
			default = key
		for option in options:
			if option.startswith(key):
				return
		options.append(default)

	def _applyShare(self, data, callback=None):
		logger.debug("...")
		if data["active"]:
			mountpoint = AutoMount.MOUNT_BASE + data["sharename"]
			logger.info("mountpoint: %s", mountpoint)
			createDir(mountpoint)
			tmpsharedir = data["sharedir"].replace(" ", "\\040")

			if data["mounttype"] == "nfs":
				opts = self.sanitizeOptions(data["options"].split(","))
				remote = "%s:%s" % (data["ip"], tmpsharedir)
				harddiskmanager.modifyFstabEntry(remote, mountpoint, mode="add_deactivated", extopts=opts, fstype="nfs")

			elif data["mounttype"] == "cifs":
				opts = self.sanitizeOptions(data["options"].split(","), cifs=True)
				if data["password"]:
					opts.extend(["username=%s" % (data["username"]), "password=%s" % (data["password"])])
				else:
					opts.extend(["guest"])
				remote = "//%s/%s" % (data["ip"], tmpsharedir)
				harddiskmanager.modifyFstabEntry(remote, mountpoint, mode="add_deactivated", extopts=opts, fstype="cifs")
		else:
			mountpoint = AutoMount.MOUNT_BASE + data["sharename"]
			self.deactivateMount(mountpoint)
		if callback:
			callback(True)

	def _onSharesApplied(self):
		logger.debug("...")
		for sharename, data in list(self._mounts.items()):
			mountpoint = AutoMount.MOUNT_BASE + sharename
			data["isMounted"] = Util.findInMtab(dst=mountpoint)
			desc = data["sharename"]
			if data["hdd_replacement"]:  # hdd replacement hack
				self._linkAsHdd(mountpoint)
			harddiskmanager.addMountedPartition(mountpoint, desc)

	def _linkAsHdd(self, path):
		hdd_dir = "/media/hdd"
		logger.info("symlink %s %s", path, hdd_dir)
		if os.path.islink(hdd_dir):
			if os.readlink(hdd_dir) != path:
				os.remove(hdd_dir)
				os.symlink(path, hdd_dir)
		elif not isMount(hdd_dir):
			if os.path.isdir(hdd_dir):
				removeDir(hdd_dir)
		try:
			os.symlink(path, hdd_dir)
			createDir(hdd_dir + "/movie")
		except OSError:
			logger.info("adding symlink failed!")

	def getMounts(self):
		return self._mounts

	def getMountsAttribute(self, mountpoint, attribute):
		if mountpoint in self._mounts:
			if attribute in self._mounts[mountpoint]:
				return self._mounts[mountpoint][attribute]
		return None

	def setMountAttributes(self, mountpoint, attributes):
		mount = self._mounts.get(mountpoint, None)
		logger.warning("before: %s", mount)
		if mount:
			mount.update(attributes)
		logger.warning("after: %s", mount)

	def save(self):
		alist = ["<?xml version='1.0' encoding='UTF-8'?>\n"]
		alist.append("<mountmanager>\n")

		for _sharename, sharedata in list(self._mounts.items()):
			if sharedata["mounttype"] == "nfs":
				# workaround for nfs shares previously saved without leading /
				if not sharedata["sharedir"].startswith("/"):
					sharedata["sharedir"] = "/%s" % sharedata["sharedir"]
			alist.append("<%s>\n" % sharedata["mounttype"])
			alist.append(" <mount>\n")
			alist.append("".join(["  <active>", str(sharedata["active"]), "</active>\n"]))
			alist.append("".join(["  <hdd_replacement>", str(sharedata["hdd_replacement"]), "</hdd_replacement>\n"]))
			alist.append("".join(["  <ip>", sharedata["ip"], "</ip>\n"]))
			alist.append("".join(["  <sharename>", sharedata["sharename"], "</sharename>\n"]))
			alist.append("".join(["  <sharedir>", sharedata["sharedir"], "</sharedir>\n"]))
			alist.append("".join(["  <options>", sharedata["options"], "</options>\n"]))

			if sharedata["mounttype"] == "cifs":
				alist.append("".join(["  <username>", sharedata["username"], "</username>\n"]))
				alist.append("".join(["  <password>", sharedata["password"], "</password>\n"]))
			alist.append(" </mount>\n")
			alist.append("</%s>\n" % sharedata["mounttype"])

		alist.append("</mountmanager>\n")

		try:
			with open(XML_FSTAB, "w") as f:
				f.writelines(alist)
		except Exception as e:
			logger.warning("Error Saving Mounts List: %s", e)

	def deactivateMount(self, mountpoint, callback=None):
		logger.debug("mountpoint: %s", mountpoint)
		res = False
		entry = Util.findInFstab(src=None, dst=mountpoint)
		if entry:
			self._unmount(mountpoint)
			harddiskmanager.modifyFstabEntry(entry["src"], entry["dst"], mode="remove")
			harddiskmanager.removeMountedPartition(mountpoint)
			res = True
		if callback is not None:
			callback(res)

	def removeMount(self, mountpoint, callback=None):
		res = False
		entry = Util.findInFstab(src=None, dst=mountpoint)
		if entry:
			sharename = os.path.basename(mountpoint)
			if sharename in self._mounts:
				del self._mounts[sharename]
			self._unmount(mountpoint)
			harddiskmanager.modifyFstabEntry(entry["src"], entry["dst"], mode="remove")
			harddiskmanager.removeMountedPartition(mountpoint)
			res = True
		if callback is not None:
			callback(res)

	def _unmount(self, mountpoint):
		logger.debug("mountpoint: %s", mountpoint)
		if isMount(mountpoint):
			self._console.ePopen("umount -fl %s" % mountpoint, self._onConsoleFinished)

	def _reloadSystemd(self, **kwargs):
		self._console.ePopen("systemctl daemon-reload && systemctl restart remote-fs.target", self._onConsoleFinished, kwargs)

	def _onConsoleFinished(self, *args):
		kwargs = {}
		if len(args) > 2:
			kw = args[2]
			if isinstance(kw, dict):
				kwargs = kw
		logger.debug("args=%s\nkwargs=%s", args, kwargs)
		callback = kwargs.get("callback", None)
		if callback:
			args = kwargs.get("args", [])
			callback(*args)


iAutoMount = AutoMount()
