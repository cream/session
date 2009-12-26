#! /usr/bin/env python
# -*- coding: utf-8 -*-

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
# MA 02110-1301, USA.

import gobject
import dbus

class Manager(gobject.GObject):

    __gtype_name__ = 'Manager'
    __gsignals__ = {
        'state-changed': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_STRING,))
        }

    def __init__(self):

        gobject.GObject.__init__(self)

        self.bus_name = None
        self.object_path = None

        self.state = None


    def get_state(self):
        return self.state


class NetworkManager(Manager):

    __gtype_name__ = 'NetworkManager'

    def __init__(self):

        Manager.__init__(self)

        self.bus_name = 'org.freedesktop.NetworkManager'
        self.object_path = '/org/freedesktop/NetworkManager'

        self.bus = dbus.SystemBus()
        self.nm = self.bus.get_object(self.bus_name, self.object_path)

        self.state = self.nm.state()

        self.nm.connect_to_signal('StateChanged', self._set_state)


    def _set_state(self, state):

        self.state = state
        self.emit('state-changed', state)
