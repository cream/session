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

import cream
import cream.ipc
import cream.extensions

import gobject

import ctypes, os

from xdg import DesktopEntry
import subprocess

IDLE_TIME = 5

STATUS_IDLE = 'idle'
STATUS_ACTIVE = 'active'


class XScreenSaverInfo(ctypes.Structure):

    """ typedef struct { ... } XScreenSaverInfo; """

    _fields_ = [('window',      ctypes.c_ulong), # screen saver window
                ('state',       ctypes.c_int),   # off,on,disabled
                ('kind',        ctypes.c_int),   # blanked,internal,external
                ('since',       ctypes.c_ulong), # milliseconds
                ('idle',        ctypes.c_ulong), # milliseconds
                ('event_mask',  ctypes.c_ulong)] # events


class XScreenSaverSession(object):

    def __init__( self):

        self.xlib = ctypes.cdll.LoadLibrary( 'libX11.so')
        self.dpy = self.xlib.XOpenDisplay( os.environ['DISPLAY'])

        if not self.dpy:
            raise Exception('Cannot open display')

        self.root = self.xlib.XDefaultRootWindow( self.dpy)
        self.xss = ctypes.cdll.LoadLibrary( 'libXss.so.1')
        self.xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)
        self.xss_info = self.xss.XScreenSaverAllocInfo()


    def get_idle( self):

        self.xss.XScreenSaverQueryInfo( self.dpy, self.root, self.xss_info)
        return int(round(float(self.xss_info.contents.idle) / 1000, 1))


class Session(cream.Module):

    __ipc_domain__ = 'org.cream.session'
    __ipc_signals__ = {
        'status_changed': 's'
        }

    def __init__(self):

        cream.Module.__init__(self)

        self.status = STATUS_ACTIVE

        self.screensaver = XScreenSaverSession()
        gobject.timeout_add(1000, self.check_idle)

        self.run_autostart()

        api = cream.extensions.ExtensionInterface({
            })

        self.extensions = cream.extensions.ExtensionManager([os.path.join(self._base_path, 'extensions')], api)
        self.extensions.load_by_name('Network')


    def run_autostart(self):

        autostart_dir = os.path.expanduser('~/.config/autostart/')

        self.messages.notice("Running autostart...")

        for i in os.listdir(autostart_dir):
            path = os.path.join(autostart_dir, i)
            if path.endswith('.desktop'):
                d = DesktopEntry.DesktopEntry(path)
                exec_path = d.get('Exec')
                self.messages.debug("Launching '{0}'...".format(d.get('Name')))
                subprocess.Popen(exec_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


    def check_idle(self):

        idle = self.screensaver.get_idle()

        if idle >= IDLE_TIME:
            status_new = STATUS_IDLE
        else:
            status_new = STATUS_ACTIVE

        if status_new != self.status:
            self.status = status_new
            self.messages.debug("Session is {0}.".format(self.status))
            self.emit_signal('status_changed', self.status)

        if self.status == STATUS_ACTIVE:
            gobject.timeout_add(1000, self.check_idle)
        elif self.status == STATUS_IDLE:
            gobject.timeout_add(100, self.check_idle)


    @cream.ipc.method('', 's')
    def get_status(self):
        return self.status


s = Session()
s.main()
