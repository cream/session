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

import ctypes
import os
import subprocess
import thread
import signal

import gobject
import gtk
from xdg import DesktopEntry

import cream
import cream.ipc
import cream.extensions

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

    """ Wrapper for the XScreenSaverSession. """

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
        """
        Get the time since the last mouse movement.

        :returns: Time since last mouse/keyboard activity.
        :rtype: `int`
        """

        self.xss.XScreenSaverQueryInfo( self.dpy, self.root, self.xss_info)
        return int(round(float(self.xss_info.contents.idle) / 1000, 1))


class Subprocess(gobject.GObject):
    """ API for handling child processes of the Cream Session. """

    __gtype_name__ = 'Subprocess'
    __gsignals__ = {
        'exited': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (gobject.TYPE_INT, gobject.TYPE_INT))
        }

    def __init__(self, command, name=None):

        gobject.GObject.__init__(self)

        self.process = None
        self.pid = None
        self.stdout = None
        self.stderr = None

        self.command = command
        self.name = name


    def run(self):
        """ Run the process. """

        #self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        #self.pid = self.process.pid
        #self.stdout = self.process.stdout
        #self.stderr = self.process.stderr

        process_data = gobject.spawn_async(self.command,
                flags=gobject.SPAWN_SEARCH_PATH|gobject.SPAWN_DO_NOT_REAP_CHILD,
                standard_output=True,
                standard_error=True
                )

        self.pid = process_data[0]
        self.stdout = os.fdopen(process_data[2])
        self.stderr = os.fdopen(process_data[3])

        self.watch = gobject.child_watch_add(self.pid, self.exited_cb)


    def exited_cb(self, pid, condition):

        self.emit('exited', pid, condition)


class Session(cream.Module, cream.ipc.Object):
    """ The main class of the Cream Session. """

    __ipc_signals__ = {
        'status_changed': 's'
        }

    def __init__(self):

        cream.Module.__init__(self)

        cream.ipc.Object.__init__(self,
            'org.cream.session',
            '/org/cream/session'
        )

        self.status = STATUS_ACTIVE

        self.screensaver = XScreenSaverSession()
        gobject.timeout_add(1000, self.check_idle)

        self.run_autostart()

        api = cream.extensions.ExtensionInterface({
            })

        self.extensions = cream.extensions.ExtensionManager([os.path.join(self.context.working_directory, 'extensions')], api)
        self.extensions.load_by_name('Network')


    def run_autostart(self):
        """ Run the autostart. """

        autostart_dir = os.path.expanduser('~/.config/autostart/')

        self.messages.notice("Running autostart...")

        for i in os.listdir(autostart_dir):
            path = os.path.join(autostart_dir, i)
            if path.endswith('.desktop'):
                d = DesktopEntry.DesktopEntry(path)
                exec_path = d.get('Exec')
                self.messages.debug("Launching '{0}'...".format(d.get('Name')))
                p = Subprocess(exec_path.split(' '), d.get('Name'))
                p.connect('exited', self.child_exited)
                p.run()


    def show_log_dialog(self, button, message):
        """ Shows a given log message. """

        builder = gtk.Builder()
        builder.add_from_file(os.path.join(self.meta['path'], 'log_dialog.glade'))
        dialog = builder.get_object('dialog')
        buffer = builder.get_object('buffer')

        buffer.set_text(message)
        dialog.run()
        dialog.destroy()


    def child_exited(self, process, pid, condition):
        """ This is called when a child process exits. """

        if condition != 0:
            if process.name:
                m = '<span size="x-large" weight="bold">Sorry! The application <i>{0}</i> exited unexpectedly.</span>'.format(process.name)
            else:
                m = '<span size="x-large" weight="bold">Sorry! An application exited unexpectedly.</span>'
            m += "\nThis is something that should not happen. You may want to take a look at the error log if you would like to see some hints why this application crashed."

            dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR)
            dialog.set_markup(m)

            action_area = dialog.get_action_area()
            button = gtk.Button()
            button.set_label("View Log")
            button.set_image(gtk.image_new_from_stock(gtk.STOCK_DIALOG_ERROR, gtk.ICON_SIZE_BUTTON))
            button.connect('clicked', self.show_log_dialog, process.stderr.read())
            action_area.pack_start(button, True, True, 0)
            action_area.show_all()

            dialog.add_button(gtk.STOCK_CLOSE, gtk.RESPONSE_CLOSE)

            dialog.run()
            dialog.destroy()


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
        """
        Returns the status of the session.

        :returns: Status of the session.
        :rtype: `string`
        """

        return self.status


if __name__ == '__main__':
    session = Session()
    session.main(enable_threads=False)
    
