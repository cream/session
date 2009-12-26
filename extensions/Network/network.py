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

import cream.extensions

import backends

KNOWN_MANAGERS = {
    'org.freedesktop.NetworkManager': backends.NetworkManager
    }

STATES = ['unknown', 'connected', 'disconnected']

@cream.extensions.register
class Network(cream.extensions.Extension):

    __ipc_domain__ = 'org.cream.session.network'
    __ipc_signals__ = {
        'state_changed': 's'
        }

    def __init__(self, *args):

        cream.extensions.Extension.__init__(self, *args)

        self.system_bus = dbus.SystemBus()

        self.manager = None

        for k, v in KNOWN_MANAGERS.iteritems():
            if self.system_bus.name_has_owner(k):
                self.manager = v()
                self.manager.connect('state-changed', lambda m,s: self.emit_signal('state_changed', s))
                break


    @cream.ipc.method('', 's')
    def get_state(self):
        return str(self.manager.get_state())
