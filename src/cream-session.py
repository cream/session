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

import os
import subprocess
import thread
import signal

import ooxcb
from ooxcb.protocol import xproto, screensaver

import gobject
import gtk
from xdg import DesktopEntry

import cream
import cream.ipc
import cream.util.subprocess

IDLE_TIME = 5

STATUS_IDLE = 'idle'
STATUS_ACTIVE = 'active'

class UPower(object):
    
    def __init__(self):
        self.service = cream.ipc.get_object('org.freedesktop.UPower', '/org/freedesktop/UPower', interface='org.freedesktop.UPower', bus=cream.ipc.SYSTEM_BUS)
    
    def suspend(self):
        self.service.Suspend()
    
    def hibernate(self):
        self.service.Hibernate()


class XScreenSaverSession(object):

    """ Wrapper for the XScreenSaverSession. """

    def __init__(self):

        self.connection = ooxcb.connect()
        self.root = self.connection.setup.roots[self.connection.pref_screen].root


    def get_idle(self):
        """
        Get the time since the last mouse movement.

        :returns: Time since last mouse/keyboard activity.
        :rtype: `int`
        """

        reply = screensaver.DrawableMixin.query_info(self.root).reply()
        return int(round(float(reply.ms_since_user_input) / 1000, 1))


class Session(cream.Module, cream.ipc.Object):
    """ The main class of the Cream Session. """

    __ipc_signals__ = {
        'status_changed': 's'
        }

    def __init__(self):

        cream.Module.__init__(self, 'org.cream.Session')

        cream.ipc.Object.__init__(self,
            'org.cream.Session',
            '/org/cream/Session'
        )

        self.status = STATUS_ACTIVE
        self.upower = UPower()

        self.screensaver = XScreenSaverSession()
        gobject.timeout_add(1000, self.check_idle)

        self.load_modules()
        self.run_autostart()
        
        
    def load_modules(self):
    
        modules = cream.manifest.ManifestDB([
            '/usr/share/cream/'
        ], 'org.cream.Module')
    
        for mod in self.config.modules:
            self.messages.info("Loading '{0}'…".format(mod))
            
            mnfst = list(modules.get(id=mod))[0]
            exec_path = mnfst['exec']
            p = cream.util.subprocess.Subprocess(exec_path.split(' '), mnfst['name'])
            p.connect('exited', self.child_exited)
            p.run()


    def run_autostart(self):
        """ Run the autostart. """

        autostart_dir = os.path.expanduser('~/.config/autostart/')

        self.messages.info("Running autostart...")

        for i in os.listdir(autostart_dir):
            path = os.path.join(autostart_dir, i)
            if path.endswith('.desktop'):
                d = DesktopEntry.DesktopEntry(path)
                exec_path = d.get('Exec')
                self.messages.debug("Launching '{0}'...".format(d.get('Name')))
                p = cream.util.subprocess.Subprocess(exec_path.split(' '), d.get('Name'))
                p.connect('exited', self.child_exited)
                p.run()


    def child_exited(self, process, pid, condition):
        """ This is called when a child process exits. """
        
        self.messages.debug("Child '{0}' exited with condition '{1}'…".format(process.name, condition))

        if condition != 0:
            if process.name:
                title = '<span size="large" weight="bold">Sorry! The application <i>{0}</i> exited unexpectedly.</span>'.format(process.name)
            else:
                title = '<span size="large" weight="bold">Sorry! An application exited unexpectedly.</span>'
            
            description = "Normally, this points to an error in an application or faulty configuration. You may want to file a bug or contact the maintainer of that application."

            interface = gtk.Builder()
            interface.add_from_file(os.path.join(self.context.get_path(), 'data', 'interface.ui'))
            
            dialog = interface.get_object('crash_dialog')
            title_label = interface.get_object('title')
            description_label = interface.get_object('description')
            log_view = interface.get_object('log_view')
            restart_button = interface.get_object('restart_button')
            
            restart_button_label = restart_button.get_child().get_child().get_children()[1]
            restart_button_label.set_text("Restart Application")
            
            title_label.set_label(title)
            description_label.set_label(description)

            log_view.get_buffer().set_text(process.stderr.read())
            
            response = dialog.run()
            dialog.destroy()
            
            if response == 1:
                process.run()


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
            

    @cream.ipc.method('', '')
    def suspend(self):
        def suspend_cb():
            self.upower.suspend()

        self.messages.debug("Suspending…")        
        gobject.idle_add(suspend_cb)
            

    @cream.ipc.method('', '')
    def hibernate(self):
        def hibernate_cb():
            self.upower.hibernate()

        self.messages.debug("Hibernating…")        
        gobject.idle_add(hibernate_cb)


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

