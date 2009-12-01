#
# Copyright (C) 2009 Red Hat, Inc.
# Copyright (C) 2009 Cole Robinson <crobinso@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.
#

import gobject
import logging

import virtinst

MEDIA_TIMEOUT = 3

class vmmMediaDevice(gobject.GObject):
    __gsignals__ = {
        "media-added"  : (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE,
                          []),
        "media-removed"  : (gobject.SIGNAL_RUN_FIRST,
                            gobject.TYPE_NONE, []),
    }

    @staticmethod
    def mediadev_from_nodedev(conn, nodedev):
        if nodedev.device_type != "storage":
            return None

        if nodedev.drive_type != "cdrom":
            return None

        path = nodedev.block
        key = nodedev.name
        has_media = nodedev.media_available
        media_label = None
        media_key = None

        nodedev_obj = conn.vmm.nodeDeviceLookupByName(key)
        obj = vmmMediaDevice(path, key, has_media, media_label, media_key,
                             nodedev_obj)
        obj.enable_poll_for_media()

        return obj

    def __init__(self, path, key, has_media, media_label, media_key,
                 nodedev_obj = None):
        self.__gobject_init__()

        self.path = path
        self.key = key
        self._has_media = has_media
        self.media_label = media_label
        self.media_key = media_key

        self.nodedev_obj = nodedev_obj
        self.poll_signal = None

    def get_path(self):
        return self.path

    def get_key(self):
        return self.key

    def has_media(self):
        return self._has_media
    def get_media_label(self):
        return self.media_label
    def get_media_key(self):
        return self.media_key

    def set_media(self, has_media, media_label, media_key):
        self._has_media = has_media
        self.media_label = media_label
        self.media_key = media_key
    def clear_media(self):
        self.set_media(None, None, None)

    def pretty_label(self):
        media_label = self.get_media_label()
        has_media = self.has_media()
        if not has_media:
            media_label = _("No media present")
        else:
            media_label = _("Media Unknown")

        return "%s (%s)" % (media_label, self.get_path())


    ############################
    # HAL media signal helpers #
    ############################

    def set_hal_media_signals(self, halhelper):
        halhelper.connect("optical-media-added", self.hal_media_added)
        halhelper.connect("device-removed", self.hal_media_removed)

    def hal_media_added(self, ignore, devpath, media_label, media_key):
        if devpath != self.get_path():
            return

        self.set_media(True, media_label, media_key)
        self.emit("media-added")

    def hal_media_removed(self, ignore, media_hal_path):
        if media_hal_path != self.get_media_key():
            return

        self.clear_media()
        self.emit("media-removed")


    #########################################
    # Nodedev API polling for media updates #
    #########################################
    def enable_poll_for_media(self):
        if self.poll_signal:
            return

        self.poll_signal = gobject.timeout_add(MEDIA_TIMEOUT * 1000,
                                               self._poll_for_media)

    def disable_poll_for_media(self):
        self.poll_signal = None

    def _poll_for_media(self):
        if not self.poll_signal:
            return False

        if not self.nodedev_obj:
            return False

        try:
            xml = self.nodedev_obj.XMLDesc(0)
        except:
            # Assume the device was removed
            return False

        try:
            vobj = virtinst.NodeDeviceParser.parse(xml)
            has_media = vobj.media_available
        except:
            logging.exception("Node device CDROM polling failed")
            return False

        if has_media != self.has_media():
            self.set_media(has_media, None, None)
            if has_media:
                self.emit("media-added")
            else:
                self.emit("media-removed")

        return True

gobject.type_register(vmmMediaDevice)