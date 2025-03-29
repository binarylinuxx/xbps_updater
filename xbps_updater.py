#!/usr/bin/env python3
import gi
import subprocess
import threading
import configparser
import os
import sys
import time
import dbus
import tempfile
import logging
import gettext
from datetime import datetime, timedelta
from pathlib import Path

# Internationalization
gettext.bindtextdomain('xbps-updater', '/usr/share/locale')
gettext.textdomain('xbps-updater')
_ = gettext.gettext

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

class XBPSUpdaterConfig:
    """Handles configuration management"""
    def __init__(self):
        self.CONFIG_DIR = Path.home() / ".config" / "xbps-updater"
        self.CONFIG_FILE = self.CONFIG_DIR / "config.ini"
        self.config = self._load_config()

    def _load_config(self):
        """Load or create configuration file"""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        config = configparser.ConfigParser()
        defaults = {
            'check_every': 'week',
            'check_through': '1',
            'notify_threshold': '150',
            'critical_threshold': '200',
            'auto_check': 'true',
            'last_check': ''
        }
        config['Settings'] = defaults
        
        if self.CONFIG_FILE.exists():
            config.read(self.CONFIG_FILE)
        
        self._save_config(config)
        return config

    def _save_config(self, config=None):
        """Save configuration to file"""
        with open(self.CONFIG_FILE, 'w') as f:
            (config or self.config).write(f)

    def validate(self):
        """Validate configuration values"""
        try:
            thresholds = [
                self.getint('notify_threshold'),
                self.getint('critical_threshold')
            ]
            if not all(t > 0 for t in thresholds):
                raise ValueError(_("Thresholds must be positive"))
            if thresholds[0] >= thresholds[1]:
                raise ValueError(_("Warning threshold must be less than critical"))
            
            interval = self.getint('check_through')
            if not 1 <= interval <= 12:
                raise ValueError(_("Check interval must be 1-12"))
                
            return True
        except (ValueError, configparser.Error) as e:
            logging.error(_("Config validation failed: %s"), str(e))
            return False

    def get(self, key, default=None):
        """Get config value with optional default"""
        return self.config.get('Settings', key, fallback=default)

    def getint(self, key, default=0):
        """Get integer config value"""
        return self.config.getint('Settings', key, fallback=default)

    def getboolean(self, key, default=False):
        """Get boolean config value"""
        return self.config.getboolean('Settings', key, fallback=default)

    def set(self, key, value):
        """Set config value"""
        self.config.set('Settings', key, str(value))
        self._save_config()

class XBPSServiceManager:
    """Handles background service integration"""
    SERVICE_DIR = Path("/etc/sv/xbps-updater")
    LOG_DIR = SERVICE_DIR / "log"
    
    @classmethod
    def install_service(cls):
        """Install runit service files"""
        try:
            cls.SERVICE_DIR.mkdir(exist_ok=True)
            cls.LOG_DIR.mkdir(exist_ok=True)
            
            # Main run script
            run_script = cls.SERVICE_DIR / "run"
            run_script.write_text("""#!/bin/sh
exec 2>&1
exec chpst -u nobody /usr/local/bin/xbps-updater --background
""")
            run_script.chmod(0o755)
            
            # Log script
            log_run = cls.LOG_DIR / "run"
            log_run.write_text("""#!/bin/sh
exec svlogd -tt ./main
""")
            log_run.chmod(0o755)
            
            return True
        except Exception as e:
            logging.error(_("Service installation failed: %s"), str(e))
            return False

class XBPSUpdaterApp(Gtk.Window):
    """Main application window"""
    def __init__(self):
        Gtk.Window.__init__(self, title=_("XBPS Package Updater"))
        self.set_default_size(800, 600)
        self.set_border_width(10)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        self.config = XBPSUpdaterConfig()
        self.service = XBPSServiceManager()
        self.last_check_date = self._parse_last_check()
        
        # Build UI
        self._init_ui()
        
        # Load initial data
        if self._should_auto_check():
            self.load_packages()

    def _setup_logging(self):
        """Configure application logging"""
        log_dir = Path.home() / ".cache" / "xbps-updater"
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename=str(log_dir / "xbps-updater.log")
        )
        self.logger = logging.getLogger('xbps-updater')

    def _init_ui(self):
        """Initialize user interface"""
        self.notebook = Gtk.Notebook()
        self.add(self.notebook)
        
        self._create_package_list_page()
        self._create_updates_page()
        self._create_config_page()
        self._create_about_page()

    def _create_package_list_page(self):
        """Create package listing page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        page.set_border_width(10)

        # Header
        header = Gtk.Label()
        header.set_markup(_("<b>Available Package Updates</b>"))
        page.pack_start(header, False, False, 0)

        # Refresh button
        self.refresh_btn = Gtk.Button(label=_("Refresh Package List"))
        self.refresh_btn.connect("clicked", self.on_refresh)
        page.pack_start(self.refresh_btn, False, False, 0)

        # Package list
        scrolled = Gtk.ScrolledWindow()
        self.pkg_list = Gtk.ListStore(str, str, str)
        self.treeview = Gtk.TreeView(model=self.pkg_list)
        
        # Columns
        for i, title in enumerate([_("Package"), _("Current"), _("Available")]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            self.treeview.append_column(column)
        
        scrolled.add(self.treeview)
        page.pack_start(scrolled, True, True, 0)

        # Status bar
        self.statusbar = Gtk.Statusbar()
        page.pack_start(self.statusbar, False, False, 0)

        self.notebook.append_page(page, Gtk.Label(label=_("Packages")))

    def _create_updates_page(self):
        """Create system updates page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(20)

        # Header
        header = Gtk.Label()
        header.set_markup(_("<big><b>System Updates</b></big>"))
        page.pack_start(header, False, False, 10)

        # Update button
        self.update_btn = Gtk.Button(label=_("Update All Packages"))
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

        self.notebook.append_page(page, Gtk.Label(label=_("Updates")))

    def _create_config_page(self):
        """Create configuration page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(20)

        # Header
        header = Gtk.Label()
        header.set_markup(_("<big><b>Configuration</b></big>"))
        page.pack_start(header, False, False, 10)

        # Auto-check
        auto_box = Gtk.Box(spacing=10)
        self.auto_switch = Gtk.Switch()
        self.auto_switch.set_active(self.config.getboolean('auto_check'))
        auto_box.pack_start(Gtk.Label(label=_("Automatic checks:")), False, False, 0)
        auto_box.pack_start(self.auto_switch, False, False, 0)
        page.pack_start(auto_box, False, False, 0)

        # Frequency
        freq_frame = Gtk.Frame(label=_("Check Frequency"))
        freq_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        self.freq_daily = Gtk.RadioButton.new_with_label(None, _("Daily"))
        self.freq_weekly = Gtk.RadioButton.new_with_label_from_widget(self.freq_daily, _("Weekly"))
        self.freq_monthly = Gtk.RadioButton.new_with_label_from_widget(self.freq_daily, _("Monthly"))
        
        current_freq = self.config.get('check_every')
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

        # Interval
        interval_box = Gtk.Box(spacing=10)
        self.interval_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
        self.interval_spin.set_value(self.config.getint('check_through'))
        interval_box.pack_start(Gtk.Label(label=_("Interval:")), False, False, 0)
        interval_box.pack_start(self.interval_spin, False, False, 0)
        page.pack_start(interval_box, False, False, 0)

        # Thresholds
        thresh_frame = Gtk.Frame(label=_("Notification Thresholds"))
        thresh_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Warning threshold
        warn_box = Gtk.Box(spacing=10)
        self.warn_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.warn_spin.set_value(self.config.getint('notify_threshold'))
        warn_box.pack_start(Gtk.Label(label=_("Warning at:")), False, False, 0)
        warn_box.pack_start(self.warn_spin, False, False, 0)
        thresh_box.pack_start(warn_box, False, False, 0)
        
        # Critical threshold
        crit_box = Gtk.Box(spacing=10)
        self.crit_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.crit_spin.set_value(self.config.getint('critical_threshold'))
        crit_box.pack_start(Gtk.Label(label=_("Critical at:")), False, False, 0)
        crit_box.pack_start(self.crit_spin, False, False, 0)
        thresh_box.pack_start(crit_box, False, False, 0)
        
        thresh_frame.add(thresh_box)
        page.pack_start(thresh_frame, False, False, 10)

        # Save button
        save_btn = Gtk.Button(label=_("Save Configuration"))
        save_btn.connect("clicked", self.on_save_config)
        page.pack_start(save_btn, False, False, 20)

        self.notebook.append_page(page, Gtk.Label(label=_("Configuration")))

    def _create_about_page(self):
        """Create about page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(20)
        
        about = Gtk.AboutDialog()
        about.set_program_name(_("XBPS Updater"))
        about.set_version("1.0")
        about.set_copyright("© 2023 Void Linux Community")
        about.set_comments(_("Graphical interface for XBPS package manager"))
        about.set_license_type(Gtk.License.GPL_3_0)
        
        btn = Gtk.Button(label=_("About"))
        btn.connect("clicked", lambda _: about.run())
        page.pack_start(btn, False, False, 0)
        
        self.notebook.append_page(page, Gtk.Label(label=_("About")))

    def _parse_last_check(self):
        """Parse last check timestamp"""
        last = self.config.get('last_check')
        try:
            return datetime.strptime(last, "%Y-%m-%d %H:%M:%S") if last else None
        except ValueError:
            return None

    def _should_auto_check(self):
        """Determine if automatic check should run"""
        if not self.config.getboolean('auto_check'):
            return False
            
        now = datetime.now()
        delta = now - (self.last_check_date or datetime.min)
        
        interval = self.config.getint('check_through')
        unit = self.config.get('check_every')
        
        return {
            'day': delta.days >= interval,
            'week': delta.days >= (7 * interval),
            'month': delta.days >= (30 * interval)
        }[unit]

    def load_packages(self):
        """Load available package updates"""
        self.refresh_btn.set_sensitive(False)
        self._update_status(_("Checking for updates..."))
        
        # Update last check time
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.config.set('last_check', now)
        
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
            
            # Check thresholds
            warn = self.config.getint('notify_threshold')
            crit = self.config.getint('critical_threshold')
            count = len(packages)
            
            if count > warn:
                urgency = "critical" if count > crit else "normal"
                self.send_notification(
                    _("Updates Available"),
                    _("%d packages need updating") % count,
                    urgency
                )
                
        except subprocess.CalledProcessError as e:
            GLib.idle_add(self._update_status, _("Error checking updates"))
            self.logger.error("Update check failed: %s", e.stderr)
        finally:
            GLib.idle_add(lambda: self.refresh_btn.set_sensitive(True))

    def _update_package_list(self, packages):
        """Update package list display"""
        self.pkg_list.clear()
        
        if not packages:
            self._update_status(_("System is up to date"))
            self.update_btn.set_sensitive(False)
            return
            
        for pkg in sorted(packages, key=lambda x: x[0].lower()):
            self.pkg_list.append(pkg)
        
        self._update_status(_("%d updates available") % len(packages))
        self.update_btn.set_sensitive(True)

    def on_update(self, widget):
        """Handle update button click"""
        if not self._check_auth():
            self._append_output(_("Authentication failed\n"))
            return
            
        widget.set_sensitive(False)
        self.progress.set_fraction(0)
        self.progress.set_text(_("Starting updates..."))
        
        thread = threading.Thread(target=self._perform_update)
        thread.daemon = True
        thread.start()

    def _check_auth(self):
        """Check for authorization using polkit"""
        try:
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
        except Exception as e:
            self.logger.error("Authorization failed: %s", str(e))
            return False

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
                    _("Updates Complete"), 
                    _("System updated successfully"),
                    "normal"
                )
            else:
                GLib.idle_add(self._update_complete, False)
                self.send_notification(
                    _("Update Failed"),
                    _("Error during package update"),
                    "critical"
                )
                
        except Exception as e:
            GLib.idle_add(self._append_output, _("Error: %s\n") % str(e))
            GLib.idle_add(self._update_complete, False)
            self.logger.error("Update failed: %s", str(e))

    def _update_complete(self, success):
        """Handle update completion"""
        self.update_btn.set_sensitive(True)
        if success:
            self.progress.set_fraction(1)
            self.progress.set_text(_("Updates completed successfully"))
            self.load_packages()
        else:
            self.progress.set_fraction(0)
            self.progress.set_text(_("Updates failed - see output"))

    def on_save_config(self, widget):
        """Save configuration changes"""
        # Get frequency setting
        freq = ('day' if self.freq_daily.get_active() else
               'week' if self.freq_weekly.get_active() else 'month')
        
        # Update config
        self.config.set('auto_check', str(self.auto_switch.get_active()))
        self.config.set('check_every', freq)
        self.config.set('check_through', self.interval_spin.get_value_as_int())
        self.config.set('notify_threshold', self.warn_spin.get_value_as_int())
        self.config.set('critical_threshold', self.crit_spin.get_value_as_int())
        
        if not self.config.validate():
            self._show_error(_("Invalid configuration values"))
            return
            
        self._show_info(_("Configuration saved"))

    def on_refresh(self, widget):
        """Handle refresh button click"""
        self.load_packages()

    def _append_output(self, text):
        """Append text to output console"""
        buf = self.output.get_buffer()
        buf.insert(buf.get_end_iter(), text)
        
        # Auto-scroll
        mark = buf.get_insert()
        iter = buf.get_iter_at_mark(mark)
        self.output.scroll_to_iter(iter, 0.0, False, 0.0, 0.0)

    def _update_status(self, message):
        """Update status bar message"""
        self.statusbar.pop(0)
        self.statusbar.push(0, message)

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
            self.logger.error("Notification failed: %s", str(e))

    def _show_info(self, message):
        """Show info dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()

    def _show_error(self, message):
        """Show error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()

def main():
    """Application entry point"""
    app = XBPSUpdaterApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    if "--background" in sys.argv:
        # Background service mode
        config = XBPSUpdaterConfig()
        last_check = None
        
        while True:
            now = datetime.now()
            delta = now - (last_check or datetime.min)
            
            check_interval = {
                'day': timedelta(days=config.getint('check_through')),
                'week': timedelta(weeks=config.getint('check_through')),
                'month': timedelta(days=30*config.getint('check_through'))
            }[config.get('check_every')]
            
            if delta >= check_interval:
                try:
                    output = subprocess.check_output(
                        ["xbps-install", "-un"],
                        stderr=subprocess.PIPE,
                        universal_newlines=True
                    )
                    
                    count = len([l for l in output.splitlines() if l.strip()])
                    if count > config.getint('notify_threshold'):
                        urgency = ("critical" if count > config.getint('critical_threshold') 
                                 else "normal")
                        subprocess.run([
                            "notify-send",
                            "-u", urgency,
                            "-i", "software-update-available",
                            _("Updates Available"),
                            _("%d packages need updating") % count
                        ])
                    
                    config.set('last_check', now.strftime("%Y-%m-%d %H:%M:%S"))
                    last_check = now
                    
                except subprocess.CalledProcessError as e:
                    logging.error("Background check failed: %s", e.stderr)
                
            time.sleep(3600)  # Check hourly
    else:
        # GUI mode
        main()
