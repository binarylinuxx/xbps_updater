#!/usr/bin/env python3
import gi
import subprocess
import threading
import configparser
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

# Constants
CONFIG_DIR = Path.home() / ".config" / "xbps-updater"
CONFIG_FILE = CONFIG_DIR / "config.ini"
DEFAULT_CONFIG = {
    'check_every': 'week',
    'check_through': '1',
    'notify_threshold': '150',
    'critical_threshold': '200',
    'auto_check': 'true',
    'confirm_updates': 'true',
    'use_sudo': 'false'  # Новая опция
}

class XBPSUpdaterApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="XBPS Package Updater")
        self.set_default_size(800, 600)
        self.set_border_width(10)
        
        # Initialize configuration
        self._setup_config()
        
        # Build UI
        self._build_ui()
        
        # Load initial data if needed
        if self._should_auto_check():
            self.load_packages()

    def _setup_config(self) -> None:
        """Setup configuration directories and load settings"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        
        self.config = configparser.ConfigParser()
        self.config['Settings'] = DEFAULT_CONFIG.copy()
        
        if CONFIG_FILE.exists():
            self.config.read(CONFIG_FILE)
        else:
            with open(CONFIG_FILE, 'w') as f:
                self.config.write(f)
        
        self.last_check_date = self._get_last_check_date()
    
    def _get_last_check_date(self) -> Optional[datetime]:
        """Get the date of the last update check"""
        last = self.config.get('Settings', 'last_check', fallback='')
        try:
            return datetime.strptime(last, "%Y-%m-%d %H:%M:%S") if last else None
        except ValueError:
            return None

    def _should_auto_check(self) -> bool:
        """Determine if automatic check should run based on settings"""
        if not self.config.getboolean('Settings', 'auto_check', fallback=True):
            return False
            
        if not self.last_check_date:
            return True
            
        # Calculate time since last check
        now = datetime.now()
        delta = now - self.last_check_date
        
        # Get check frequency settings
        interval = self.config.getint('Settings', 'check_through', fallback=1)
        unit = self.config.get('Settings', 'check_every', fallback='week')
        
        # Define time thresholds based on settings
        thresholds = {
            'day': timedelta(days=interval),
            'week': timedelta(weeks=interval),
            'month': timedelta(days=30 * interval)
        }
        
        return delta >= thresholds.get(unit, timedelta(weeks=1))

    def _build_ui(self) -> None:
        """Build the main user interface"""
        self.notebook = Gtk.Notebook()
        self.add(self.notebook)
        
        # Create the three main pages
        self._create_package_list_page()
        self._create_updates_page()
        self._create_config_page()

    def _create_package_list_page(self) -> None:
        """Create the package list page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        page.set_border_width(10)

        # Add header
        header = Gtk.Label()
        header.set_markup("<b>Available Package Updates</b>")
        page.pack_start(header, False, False, 0)

        # Add refresh button
        self.refresh_btn = Gtk.Button(label="Refresh Package List")
        self.refresh_btn.connect("clicked", self.on_refresh)
        page.pack_start(self.refresh_btn, False, False, 0)

        # Add package list with scrolling
        scrolled = Gtk.ScrolledWindow()
        self.pkg_list = Gtk.ListStore(str, str, str)  # name, current, new
        self.treeview = Gtk.TreeView(model=self.pkg_list)
        
        # Add columns
        column_titles = ["Package", "Current", "Available"]
        for i, title in enumerate(column_titles):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            column.set_resizable(True)
            column.set_min_width(150)
            self.treeview.append_column(column)
        
        scrolled.add(self.treeview)
        page.pack_start(scrolled, True, True, 0)

        # Add status bar
        self.statusbar = Gtk.Statusbar()
        page.pack_start(self.statusbar, False, False, 0)

        self.notebook.append_page(page, Gtk.Label(label="Packages"))

    def _create_updates_page(self) -> None:
        """Create the system updates page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(20)

        # Add header
        header = Gtk.Label()
        header.set_markup("<big><b>System Updates</b></big>")
        page.pack_start(header, False, False, 10)

        # Add update button
        self.update_btn = Gtk.Button(label="Update All Packages")
        self.update_btn.connect("clicked", self.on_update)
        page.pack_start(self.update_btn, False, False, 20)

        # Add progress bar
        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        page.pack_start(self.progress, False, False, 10)

        # Add output view with scrolling
        self.output = Gtk.TextView()
        self.output.set_editable(False)
        self.output.set_monospace(True)
        scroll = Gtk.ScrolledWindow()
        scroll.add(self.output)
        page.pack_start(scroll, True, True, 0)

        self.notebook.append_page(page, Gtk.Label(label="Updates"))

    def _create_config_page(self) -> None:
        """Create the configuration page"""
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(20)

        # Add header
        header = Gtk.Label()
        header.set_markup("<big><b>Configuration</b></big>")
        page.pack_start(header, False, False, 10)

        # Add settings widgets
        # Auto-check toggle
        auto_box = Gtk.Box(spacing=10)
        self.auto_switch = Gtk.Switch()
        self.auto_switch.set_active(self.config.getboolean('Settings', 'auto_check', fallback=True))
        auto_box.pack_start(Gtk.Label(label="Automatic checks:"), False, False, 0)
        auto_box.pack_start(self.auto_switch, False, False, 0)
        page.pack_start(auto_box, False, False, 0)

        # Confirm updates toggle
        confirm_box = Gtk.Box(spacing=10)
        self.confirm_switch = Gtk.Switch()
        self.confirm_switch.set_active(self.config.getboolean('Settings', 'confirm_updates', fallback=True))
        confirm_box.pack_start(Gtk.Label(label="Confirm before updating:"), False, False, 0)
        confirm_box.pack_start(self.confirm_switch, False, False, 0)
        page.pack_start(confirm_box, False, False, 0)

        # Use sudo toggle (новая опция)
        sudo_box = Gtk.Box(spacing=10)
        self.sudo_switch = Gtk.Switch()
        self.sudo_switch.set_active(self.config.getboolean('Settings', 'use_sudo', fallback=False))
        sudo_box.pack_start(Gtk.Label(label="Use sudo instead of pkexec:"), False, False, 0)
        sudo_box.pack_start(self.sudo_switch, False, False, 0)
        page.pack_start(sudo_box, False, False, 0)

        # Frequency selection
        freq_frame = Gtk.Frame(label="Check Frequency")
        freq_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Create radio buttons
        self.freq_daily = Gtk.RadioButton.new_with_label(None, "Daily")
        self.freq_weekly = Gtk.RadioButton.new_with_label_from_widget(self.freq_daily, "Weekly")
        self.freq_monthly = Gtk.RadioButton.new_with_label_from_widget(self.freq_daily, "Monthly")
        
        # Set active based on config
        current_freq = self.config.get('Settings', 'check_every', fallback='week')
        freq_map = {
            'day': self.freq_daily,
            'week': self.freq_weekly,
            'month': self.freq_monthly
        }
        freq_map[current_freq].set_active(True)
        
        for btn in [self.freq_daily, self.freq_weekly, self.freq_monthly]:
            freq_box.pack_start(btn, False, False, 0)
            
        freq_frame.add(freq_box)
        page.pack_start(freq_frame, False, False, 10)

        # Interval selection
        interval_box = Gtk.Box(spacing=10)
        self.interval_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
        self.interval_spin.set_value(self.config.getint('Settings', 'check_through', fallback=1))
        interval_box.pack_start(Gtk.Label(label="Interval:"), False, False, 0)
        interval_box.pack_start(self.interval_spin, False, False, 0)
        page.pack_start(interval_box, False, False, 0)

        # Thresholds
        thresh_frame = Gtk.Frame(label="Notification Thresholds")
        thresh_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        # Warning threshold
        warn_box = Gtk.Box(spacing=10)
        self.warn_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.warn_spin.set_value(self.config.getint('Settings', 'notify_threshold', fallback=150))
        warn_box.pack_start(Gtk.Label(label="Warning at:"), False, False, 0)
        warn_box.pack_start(self.warn_spin, False, False, 0)
        thresh_box.pack_start(warn_box, False, False, 0)
        
        # Critical threshold
        crit_box = Gtk.Box(spacing=10)
        self.crit_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.crit_spin.set_value(self.config.getint('Settings', 'critical_threshold', fallback=200))
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

    def load_packages(self) -> None:
        """Load available package updates"""
        self.refresh_btn.set_sensitive(False)
        self._update_status("Checking for updates...")
        
        # Update last check time
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.config.set('Settings', 'last_check', now)
        with open(CONFIG_FILE, 'w') as f:
            self.config.write(f)
        
        # Start background thread
        thread = threading.Thread(target=self._fetch_packages)
        thread.daemon = True
        thread.start()

    def _fetch_packages(self) -> None:
        """Background thread to fetch packages"""
        try:
            result = subprocess.run(
                ["xbps-install", "-un"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                check=True
            )
            
            packages = []
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    packages.append((parts[0], parts[1], parts[2]))
            
            GLib.idle_add(self._update_package_list, packages)
            
            # Check notification thresholds
            count = len(packages)
            if count > 0:
                self._check_notification_thresholds(count)
                
        except subprocess.CalledProcessError as e:
            GLib.idle_add(self._update_status, f"Error checking updates: {e.stderr.strip()}")
        except Exception as e:
            GLib.idle_add(self._update_status, f"Unexpected error: {str(e)}")
        finally:
            GLib.idle_add(lambda: self.refresh_btn.set_sensitive(True))

    def _check_notification_thresholds(self, count: int) -> None:
        """Check if notification thresholds are exceeded and notify if needed"""
        warn = self.config.getint('Settings', 'notify_threshold', fallback=150)
        crit = self.config.getint('Settings', 'critical_threshold', fallback=200)
        
        if count > warn:
            urgency = "critical" if count > crit else "normal"
            self._send_notification(
                "Updates Available",
                f"{count} packages need updating",
                urgency
            )

    def on_update(self, widget: Gtk.Widget) -> None:
        """Handle update button click"""
        # Check if confirmation is needed
        if self.config.getboolean('Settings', 'confirm_updates', fallback=True):
            if not self._confirm_update():
                return
        
        # Prepare UI for update
        widget.set_sensitive(False)
        self.progress.set_fraction(0)
        self.progress.set_text("Preparing updates...")
        
        # Clear previous output
        buf = self.output.get_buffer()
        buf.set_text("")
        
        # Check authentication
        if not self._check_auth():
            self._append_output("Error: Authentication failed. Make sure you have proper privileges.\n")
            widget.set_sensitive(True)
            self.progress.set_text("Authentication failed")
            return
        
        # Start update in background
        thread = threading.Thread(target=self._perform_update)
        thread.daemon = True
        thread.start()

    def _confirm_update(self) -> bool:
        """Show confirmation dialog for updates"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=f"Update {len(self.pkg_list)} packages?"
        )
        dialog.format_secondary_text("This action requires administrator privileges.")
        response = dialog.run()
        dialog.destroy()
        
        return response == Gtk.ResponseType.YES

    def _check_auth(self) -> bool:
        """Check if user can perform privileged operations"""
        use_sudo = self.config.getboolean('Settings', 'use_sudo', fallback=False)
        
        if use_sudo:
            # Check if sudo is available and configured
            try:
                result = subprocess.run(
                    ["sudo", "-n", "true"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                return result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                return False
        else:
            # Check pkexec
            try:
                result = subprocess.run(
                    ["pkexec", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                return result.returncode == 0
            except (subprocess.SubprocessError, FileNotFoundError):
                return False

    def _perform_update(self) -> None:
        """Perform system updates with configured privilege escalation"""
        try:
            use_sudo = self.config.getboolean('Settings', 'use_sudo', fallback=False)
            
            if use_sudo:
                cmd = ["sudo", "xbps-install", "-Syu"]
            else:
                cmd = ["pkexec", "xbps-install", "-Syu"]
            
            proc = subprocess.Popen(
                cmd,
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
                self._send_notification(
                    "Updates Complete", 
                    "System updated successfully",
                    "normal"
                )
            else:
                GLib.idle_add(self._update_complete, False)
                self._send_notification(
                    "Update Failed",
                    "Error during package update",
                    "critical"
                )
                
        except Exception as e:
            GLib.idle_add(self._append_output, f"Error: {str(e)}\n")
            GLib.idle_add(self._update_complete, False)

    def _update_complete(self, success: bool) -> None:
        """Handle update completion"""
        self.update_btn.set_sensitive(True)
        if success:
            self.progress.set_fraction(1)
            self.progress.set_text("Updates completed successfully")
            self.load_packages()  # Refresh package list
        else:
            self.progress.set_fraction(0)
            self.progress.set_text("Updates failed - see output")

    def on_save_config(self, widget: Gtk.Widget) -> None:
        """Save configuration changes"""
        # Determine frequency setting
        freq = 'day' if self.freq_daily.get_active() else \
               'week' if self.freq_weekly.get_active() else 'month'
        
        # Update config values
        self.config.set('Settings', 'auto_check', str(self.auto_switch.get_active()))
        self.config.set('Settings', 'confirm_updates', str(self.confirm_switch.get_active()))
        self.config.set('Settings', 'use_sudo', str(self.sudo_switch.get_active()))
        self.config.set('Settings', 'check_every', freq)
        self.config.set('Settings', 'check_through', str(self.interval_spin.get_value_as_int()))
        self.config.set('Settings', 'notify_threshold', str(self.warn_spin.get_value_as_int()))
        self.config.set('Settings', 'critical_threshold', str(self.crit_spin.get_value_as_int()))
        
        # Save to file
        with open(CONFIG_FILE, 'w') as f:
            self.config.write(f)
        
        # Show confirmation
        self._show_info_dialog("Configuration saved successfully!")

    def _show_info_dialog(self, message: str) -> None:
        """Show an information dialog with the given message"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.run()
        dialog.destroy()

    def on_refresh(self, widget: Gtk.Widget) -> None:
        """Handle refresh button click"""
        self.load_packages()

    def _update_package_list(self, packages: List[Tuple[str, str, str]]) -> None:
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

    def _update_status(self, message: str) -> None:
        """Update status bar message"""
        self.statusbar.pop(0)
        self.statusbar.push(0, message)

    def _append_output(self, text: str) -> None:
        """Append text to output console and auto-scroll"""
        buf = self.output.get_buffer()
        buf.insert(buf.get_end_iter(), text)
        
        # Auto-scroll to bottom
        mark = buf.get_insert()
        iter = buf.get_iter_at_mark(mark)
        self.output.scroll_to_iter(iter, 0.0, False, 0.0, 0.0)

    def _send_notification(self, title: str, message: str, urgency: str = "normal") -> None:
        """Send desktop notification using notify-send"""
        try:
            subprocess.run([
                "notify-send",
                "-u", urgency,
                "-i", "software-update-available",
                title,
                message
            ])
        except Exception as e:
            print(f"Notification failed: {e}")


def run_background_service():
    """Run as a background service checking for updates"""
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    
    last_check = None
    while True:
        # Check if it's time to look for updates
        now = datetime.now()
        if last_check is None:
            do_check = True
        else:
            # Calculate time since last check
            delta = now - last_check
            
            # Get check frequency settings
            interval = config.getint('Settings', 'check_through', fallback=1)
            unit = config.get('Settings', 'check_every', fallback='week')
            
            # Define time thresholds based on settings
            thresholds = {
                'day': timedelta(days=interval),
                'week': timedelta(weeks=interval),
                'month': timedelta(days=30 * interval)  # Approximate
            }
            
            do_check = delta >= thresholds.get(unit, timedelta(weeks=1))
        
        if do_check:
            try:
                # Check for updates
                result = subprocess.run(
                    ["xbps-install", "-un"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    check=True
                )
                
                # Count packages needing updates
                count = len([l for l in result.stdout.splitlines() if l.strip()])
                
                # Check against thresholds
                if count > config.getint('Settings', 'notify_threshold', fallbox=150):
                    urgency = "critical" if count > config.getint('Settings', 'critical_threshold', fallback=200) else "normal"
                    subprocess.run([
                        "notify-send",
                        "-u", urgency,
                        "-i", "software-update-available",
                        "Updates Available",
                        f"{count} packages need updating"
                    ])
                
                # Update last check time
                config.set('Settings', 'last_check', now.strftime("%Y-%m-%d %H:%M:%S"))
                with open(CONFIG_FILE, 'w') as f:
                    config.write(f)
                
                last_check = now
                
            except subprocess.CalledProcessError as e:
                print(f"Background check failed: {e.stderr}")
            
        # Sleep for an hour before checking again
        time.sleep(3600)


def main():
    """Application entry point"""
    if "--background" in sys.argv:
        run_background_service()
    else:
        app = XBPSUpdaterApp()
        app.connect("destroy", Gtk.main_quit)
        app.show_all()
        Gtk.main()


if __name__ == "__main__":
    main()
