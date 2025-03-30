#!/usr/bin/env python3
import gi
import subprocess
import threading
import configparser
import os
import sys
import time
import dbus
import dbus.exceptions
from datetime import datetime, timedelta
from pathlib import Path

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

class XBPSUpdaterApp(Gtk.Window):
    CONFIG_DIR = Path.home() / ".config" / "xbps-updater"
    CONFIG_FILE = CONFIG_DIR / "config.ini"
    
    def __init__(self):
        Gtk.Window.__init__(self, title="XBPS Package Updater")
        self.set_default_size(800, 600)
        self.set_border_width(10)
        
        # Initialize components
        self._setup_directories()
        self.config = self._load_config()
        self.last_check_date = self._parse_last_check()
        
        # Build UI
        self._init_ui()
        
        # Load initial data
        if self._should_auto_check():
            self.load_packages()

    def _setup_directories(self):
        """Ensure required directories exist"""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        """Load or create configuration"""
        config = configparser.ConfigParser()
        defaults = {
            'check_every': 'week',
            'check_through': '1',
            'notify_threshold': '150',
            'critical_threshold': '200',
            'auto_check': 'true'
        }
        config['Settings'] = defaults
        
        if self.CONFIG_FILE.exists():
            config.read(self.CONFIG_FILE)
        
        with open(self.CONFIG_FILE, 'w') as f:
            config.write(f)
        
        return config

    def _parse_last_check(self):
        """Parse last check timestamp from config"""
        last = self.config.get('Settings', 'last_check', fallback='')
        try:
            return datetime.strptime(last, "%Y-%m-%d %H:%M:%S") if last else None
        except ValueError:
            return None

    def _should_auto_check(self):
        """Determine if automatic check should run"""
        if not self.config.getboolean('Settings', 'auto_check', fallback=True):
            return False
            
        now = datetime.now()
        delta = now - (self.last_check_date or datetime.min)
        
        interval = self.config.getint('Settings', 'check_through', fallback=1)
        unit = self.config.get('Settings', 'check_every', fallback='week')
        
        return {
            'day': delta.days >= interval,
            'week': delta.days >= (7 * interval),
            'month': delta.days >= (30 * interval)
        }[unit]

    def _init_ui(self):
        """Initialize user interface"""
        self.notebook = Gtk.Notebook()
        self.add(self.notebook)
        
        self._create_package_list_page()
        self._create_updates_page()
        self._create_config_page()

    def _create_package_list_page(self):
        """Package list page with available updates"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        page.set_border_width(10)

        # Header
        header = Gtk.Label()
        header.set_markup("<b>Available Package Updates</b>")
        page.pack_start(header, False, False, 0)

        # Refresh button
        self.refresh_btn = Gtk.Button(label="Refresh Package List")
        self.refresh_btn.connect("clicked", self.on_refresh)
        page.pack_start(self.refresh_btn, False, False, 0)

        # Package list
        scrolled = Gtk.ScrolledWindow()
        self.pkg_list = Gtk.ListStore(str, str, str)  # name, current, new
        self.treeview = Gtk.TreeView(model=self.pkg_list)
        
        # Columns
        for i, title in enumerate(["Package", "Current", "Available"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            self.treeview.append_column(column)
        
        scrolled.add(self.treeview)
        page.pack_start(scrolled, True, True, 0)

        # Status bar
        self.statusbar = Gtk.Statusbar()
        page.pack_start(self.statusbar, False, False, 0)

        self.notebook.append_page(page, Gtk.Label(label="Packages"))

    def _create_updates_page(self):
        """System updates page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<big><b>System Updates</b></big>")
        page.pack_start(header, False, False, 10)

        # Update button
        self.update_btn = Gtk.Button(label="Update All Packages")
        self.update_btn.connect("clicked", self.on_update)
        page.pack_start(self.update_btn, False, False, 20)

        # Progress
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        page.pack_start(self.progress, False, False, 10)

        # Output
        self.output = Gtk.TextView()
        self.output.set_editable(False)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.output)
        page.pack_start(scroll, True, True, 0)

        self.notebook.append_page(page, Gtk.Label(label="Updates"))

    def _create_config_page(self):
        """Configuration page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<big><b>Configuration</b></big>")
        page.pack_start(header, False, False, 10)

        # Auto-check toggle
        auto_box = Gtk.Box(spacing=10)
        self.auto_switch = Gtk.Switch()
        self.auto_switch.set_active(
            self.config.getboolean('Settings', 'auto_check', fallback=True)
        )
        auto_box.pack_start(Gtk.Label(label="Automatic checks:"), False, False, 0)
        auto_box.pack_start(self.auto_switch, False, False, 0)
        page.pack_start(auto_box, False, False, 0)

        # Frequency selection
        freq_frame = Gtk.Frame(label="Check Frequency")
        freq_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        self.freq_daily = Gtk.RadioButton.new_with_label(None, "Daily")
        self.freq_weekly = Gtk.RadioButton.new_with_label_from_widget(self.freq_daily, "Weekly")
        self.freq_monthly = Gtk.RadioButton.new_with_label_from_widget(self.freq_daily, "Monthly")
        
        current_freq = self.config.get('Settings', 'check_every', fallback='week')
        {
            'day': self.freq_daily,
            'week': self.freq_weekly,
            'month': self.freq_monthly
        }[current_freq].set_active(True)
        
        freq_box.pack_start(self.freq_daily, False, False, 0)
        freq_box.pack_start(self.freq_weekly, False, False, 0)
        freq_box.pack_start(self.freq_monthly, False, False, 0)
        freq_frame.add(freq_box)
        page.pack_start(freq_frame, False, False, 10)

        # Interval selection
        interval_box = Gtk.Box(spacing=10)
        self.interval_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
        self.interval_spin.set_value(
            self.config.getint('Settings', 'check_through', fallback=1)
        )
        interval_box.pack_start(Gtk.Label(label="Interval:"), False, False, 0)
        interval_box.pack_start(self.interval_spin, False, False, 0)
        page.pack_start(interval_box, False, False, 0)

        # Thresholds
        thresh_frame = Gtk.Frame(label="Notification Thresholds")
        thresh_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Warning threshold
        warn_box = Gtk.Box(spacing=10)
        self.warn_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.warn_spin.set_value(
            self.config.getint('Settings', 'notify_threshold', fallback=150)
        )
        warn_box.pack_start(Gtk.Label(label="Warning at:"), False, False, 0)
        warn_box.pack_start(self.warn_spin, False, False, 0)
        thresh_box.pack_start(warn_box, False, False, 0)
        
        # Critical threshold
        crit_box = Gtk.Box(spacing=10)
        self.crit_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.crit_spin.set_value(
            self.config.getint('Settings', 'critical_threshold', fallback=200)
        )
        crit_box.pack_start(Gtk.Label(label="Critical at:"), False, False, 0)
        crit_box.pack_start(self.crit_spin, False, False, 0)
        thresh_box.pack_start(crit_box, False, False, 0)
        
        thresh_frame.add(thresh_box)
        page.pack_start(thresh_frame, False, False, 10)

        # Save button
        save_btn = Gtk.Button(label="Save Configuration")
        save_btn.connect("clicked", self.on_save_config)
        page.pack_start(save_btn, False, False, 20)

        self.notebook.append_page(page, Gtk.Label(label="Configuration"))

    def _check_auth(self):
        """Check authorization using Polkit"""
        try:
            # Small delay to ensure UI updates
            time.sleep(0.3)
            
            bus = dbus.SystemBus()
            proxy = bus.get_object(
                'org.freedesktop.PolicyKit1',
                '/org/freedesktop/PolicyKit1/Authority'
            )
            authority = dbus.Interface(
                proxy,
                'org.freedesktop.PolicyKit1.Authority'
            )
            
            subject = ('unix-process', {
                'pid': dbus.UInt32(os.getpid()),
                'start-time': dbus.UInt64(0)
            })
            
            result = authority.CheckAuthorization(
                subject,
                'org.freedesktop.policykit.exec',
                {},
                dbus.UInt32(1),  # Allow user interaction
                ''
            )
            return result[0]
        except dbus.exceptions.DBusException as e:
            print(f"DBus error: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

    def load_packages(self):
        """Load available package updates"""
        self.refresh_btn.set_sensitive(False)
        self._update_status("Checking for updates...")
        
        # Update last check time
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.config.set('Settings', 'last_check', now)
        with open(self.CONFIG_FILE, 'w') as f:
            self.config.write(f)
        
        thread = threading.Thread(target=self._fetch_packages)
        thread.daemon = True
        thread.start()

    def _fetch_packages(self):
        """Background thread to fetch packages"""
        try:
            output = subprocess.check_output(
                ["xbps-install", "-un"],
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            packages = []
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    packages.append((parts[0], parts[1], parts[2]))
            
            GLib.idle_add(self._update_package_list, packages)
            
            # Check notification thresholds
            warn = self.config.getint('Settings', 'notify_threshold', fallback=150)
            crit = self.config.getint('Settings', 'critical_threshold', fallback=200)
            count = len(packages)
            
            if count > warn:
                urgency = "critical" if count > crit else "normal"
                self.send_notification(
                    "Updates Available",
                    f"{count} packages need updating",
                    urgency
                )
                
        except subprocess.CalledProcessError as e:
            GLib.idle_add(self._update_status, "Error checking updates")
            print(f"Update check failed: {e.stderr}")
        finally:
            GLib.idle_add(lambda: self.refresh_btn.set_sensitive(True))

    def on_update(self, widget):
        """Handle update button click"""
        widget.set_sensitive(False)
        self.progress.set_fraction(0)
        self.progress.set_text("Preparing updates...")
        
        # Clear previous output
        buf = self.output.get_buffer()
        buf.set_text("")
        
        if not self._check_auth():
            self._append_output("Authentication failed\n")
            widget.set_sensitive(True)
            self.progress.set_text("Authentication failed")
            return
            
        thread = threading.Thread(target=self._perform_update)
        thread.daemon = True
        thread.start()

    def _perform_update(self):
        """Perform system updates"""
        try:
            proc = subprocess.Popen(
                ["xbps-install", "-Syu"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            for line in proc.stdout:
                GLib.idle_add(self._append_output, line)
                if "downloaded" in line.lower():
                    GLib.idle_add(
                        self.progress.set_fraction,
                        min(0.9, self.progress.get_fraction() + 0.1)
                    )
            
            proc.wait()
            
            if proc.returncode == 0:
                GLib.idle_add(self._update_complete, True)
                self.send_notification(
                    "Updates Complete", 
                    "System updated successfully",
                    "normal"
                )
            else:
                GLib.idle_add(self._update_complete, False)
                self.send_notification(
                    "Update Failed",
                    "Error during package update",
                    "critical"
                )
                
        except Exception as e:
            GLib.idle_add(self._append_output, f"Error: {str(e)}\n")
            GLib.idle_add(self._update_complete, False)
            print(f"Update failed: {str(e)}")

    def _update_complete(self, success):
        """Handle update completion"""
        self.update_btn.set_sensitive(True)
        if success:
            self.progress.set_fraction(1)
            self.progress.set_text("Updates completed successfully")
            self.load_packages()
        else:
            self.progress.set_fraction(0)
            self.progress.set_text("Updates failed - see output")

    def on_save_config(self, widget):
        """Save configuration changes"""
        # Get frequency setting
        freq = ('day' if self.freq_daily.get_active() else
               'week' if self.freq_weekly.get_active() else 'month')
        
        # Update config
        self.config.set('Settings', 'auto_check', str(self.auto_switch.get_active()))
        self.config.set('Settings', 'check_every', freq)
        self.config.set('Settings', 'check_through', str(self.interval_spin.get_value_as_int()))
        self.config.set('Settings', 'notify_threshold', str(self.warn_spin.get_value_as_int()))
        self.config.set('Settings', 'critical_threshold', str(self.crit_spin.get_value_as_int()))
        
        with open(self.CONFIG_FILE, 'w') as f:
            self.config.write(f)
        
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Configuration saved successfully!"
        )
        dialog.run()
        dialog.destroy()

    def on_refresh(self, widget):
        """Handle refresh button click"""
        self.load_packages()

    def _update_package_list(self, packages):
        """Update package list display"""
        self.pkg_list.clear()
        
        if not packages:
            self._update_status("System is up to date")
            self.update_btn.set_sensitive(False)
            return
            
        for pkg in sorted(packages, key=lambda x: x[0].lower()):
            self.pkg_list.append(pkg)
        
        self._update_status(f"{len(packages)} updates available")
        self.update_btn.set_sensitive(True)

    def _update_status(self, message):
        """Update status bar message"""
        self.statusbar.pop(0)
        self.statusbar.push(0, message)

    def _append_output(self, text):
        """Append text to output console"""
        buf = self.output.get_buffer()
        buf.insert(buf.get_end_iter(), text)
        
        # Auto-scroll
        mark = buf.get_insert()
        iter = buf.get_iter_at_mark(mark)
        self.output.scroll_to_iter(iter, 0.0, False, 0.0, 0.0)

    def send_notification(self, title, message, urgency="normal"):
        """Send desktop notification"""
        try:
            bus = dbus.SessionBus()
            notify = bus.get_object(
                'org.freedesktop.Notifications',
                '/org/freedesktop/Notifications'
            )
            notify.Notify(
                'xbps-updater',
                0,
                'software-update-available',
                title,
                message,
                [],
                {'urgency': dbus.Byte(2 if urgency == "critical" else 1)},
                5000
            )
        except Exception as e:
            print(f"Notification failed: {e}")

def main():
    """Application entry point"""
    app = XBPSUpdaterApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    if "--background" in sys.argv:
        # Background service mode
        config = configparser.ConfigParser()
        config.read(Path.home() / ".config" / "xbps-updater" / "config.ini")
        
        last_check = None
        while True:
            now = datetime.now()
            delta = now - (last_check or datetime.min)
            
            interval = config.getint('Settings', 'check_through', fallback=1)
            unit = config.get('Settings', 'check_every', fallback='week')
            
            if {
                'day': delta.days >= interval,
                'week': delta.days >= (7 * interval),
                'month': delta.days >= (30 * interval)
            }[unit]:
                try:
                    output = subprocess.check_output(
                        ["xbps-install", "-un"],
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    
                    count = len([l for l in output.splitlines() if l.strip()])
                    if count > config.getint('Settings', 'notify_threshold', fallback=150):
                        urgency = ("critical" if count > config.getint('Settings', 'critical_threshold', fallback=200) 
                                 else "normal")
                        subprocess.run([
                            "notify-send",
                            "-u", urgency,
                            "-i", "software-update-available",
                            "Updates Available",
                            f"{count} packages need updating"
                        ])
                    
                    config.set('Settings', 'last_check', now.strftime("%Y-%m-%d %H:%M:%S"))
                    with open(Path.home() / ".config" / "xbps-updater" / "config.ini", 'w') as f:
                        config.write(f)
                    
                    last_check = now
                    
                except subprocess.CalledProcessError as e:
                    print(f"Background check failed: {e.stderr}")
                
            time.sleep(3600)  # Check hourly
    else:
        # GUI mode
        main()
