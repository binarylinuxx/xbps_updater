import gi
import subprocess
import threading
import configparser
import os
from datetime import datetime, timedelta
from pathlib import Path
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

class XBPSUpdaterApp(Gtk.Window):
    CONFIG_DIR = os.path.expanduser("~/.config/upd")
    CONFIG_FILE = os.path.join(CONFIG_DIR, "upd.ini")
    
    def __init__(self):
        Gtk.Window.__init__(self, title="XBPS Package Updater")
        self.set_default_size(800, 600)
        self.set_border_width(10)

        # Ensure config directory exists
        Path(self.CONFIG_DIR).mkdir(parents=True, exist_ok=True)

        # Load or create config
        self.config = self.load_config()
        self.last_check_date = self.get_last_check_date()

        # Main container
        self.notebook = Gtk.Notebook()
        self.add(self.notebook)

        # Create all pages
        self.create_package_list_page()
        self.create_updates_page()
        self.create_config_page()

        # Initial load
        if self.should_auto_check():
            self.load_packages()

    def load_config(self):
        config = configparser.ConfigParser()
        
        # Set default values
        defaults = {
            'check_every': 'week',
            'check_through': '1',
            'last_check': '',
            'notify_threshold': '150',
            'critical_threshold': '200'
        }
        
        config['Settings'] = defaults
        
        # Read existing config if available
        if os.path.exists(self.CONFIG_FILE):
            config.read(self.CONFIG_FILE)
        
        # Write defaults if file didn't exist or was missing values
        with open(self.CONFIG_FILE, 'w') as f:
            config.write(f)
        
        return config

    def get_last_check_date(self):
        last_check = self.config.get("Settings", "last_check", fallback="")
        try:
            return datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S") if last_check else None
        except ValueError:
            return None

    def should_auto_check(self):
        if not self.config.getboolean("Settings", "auto_check", fallback=True):
            return False
            
        check_every = self.config.get("Settings", "check_every", fallback="week")
        check_through = self.config.getint("Settings", "check_through", fallback=1)
        
        if not self.last_check_date:
            return True
            
        now = datetime.now()
        delta = now - self.last_check_date
        
        if check_every == "day":
            return delta.days >= check_through
        elif check_every == "week":
            return delta.days >= (7 * check_through)
        elif check_every == "month":
            return delta.days >= (30 * check_through)
        return True

    def save_config(self):
        with open(self.CONFIG_FILE, 'w') as f:
            self.config.write(f)

    def create_config_page(self):
        config_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        config_page.set_border_width(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<big><b>Configuration Settings</b></big>")
        config_page.pack_start(header, False, False, 10)

        # Auto-check toggle
        auto_check_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        config_page.pack_start(auto_check_box, False, False, 0)
        
        self.auto_check_switch = Gtk.Switch()
        self.auto_check_switch.set_active(
            self.config.getboolean("Settings", "auto_check", fallback=True)
        )
        auto_check_box.pack_start(Gtk.Label(label="Enable Automatic Checks:"), False, False, 0)
        auto_check_box.pack_start(self.auto_check_switch, False, False, 0)

        # Check frequency frame
        freq_frame = Gtk.Frame(label="Update Check Frequency")
        freq_frame.set_margin_top(20)
        freq_frame.set_margin_bottom(20)
        config_page.pack_start(freq_frame, False, False, 0)

        freq_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        freq_box.set_border_width(10)
        freq_frame.add(freq_box)

        # Check interval radio buttons
        self.daily_radio = Gtk.RadioButton.new_with_label_from_widget(None, "Daily")
        self.weekly_radio = Gtk.RadioButton.new_with_label_from_widget(self.daily_radio, "Weekly")
        self.monthly_radio = Gtk.RadioButton.new_with_label_from_widget(self.daily_radio, "Monthly")

        # Set current selection
        current_freq = self.config.get("Settings", "check_every", fallback="week")
        if current_freq == "day":
            self.daily_radio.set_active(True)
        elif current_freq == "week":
            self.weekly_radio.set_active(True)
        else:
            self.monthly_radio.set_active(True)

        freq_box.pack_start(self.daily_radio, False, False, 0)
        freq_box.pack_start(self.weekly_radio, False, False, 0)
        freq_box.pack_start(self.monthly_radio, False, False, 0)

        # Check through spin button
        through_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        freq_box.pack_start(through_box, False, False, 10)

        through_label = Gtk.Label(label="Check every:")
        through_box.pack_start(through_label, False, False, 0)

        self.through_spin = Gtk.SpinButton.new_with_range(1, 12, 1)
        self.through_spin.set_value(self.config.getint("Settings", "check_through", fallback=1))
        through_box.pack_start(self.through_spin, False, False, 0)

        self.interval_label = Gtk.Label()
        self.update_interval_label()
        through_box.pack_start(self.interval_label, False, False, 0)

        # Notification thresholds
        threshold_frame = Gtk.Frame(label="Notification Thresholds")
        threshold_frame.set_margin_bottom(20)
        config_page.pack_start(threshold_frame, False, False, 0)

        threshold_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        threshold_box.set_border_width(10)
        threshold_frame.add(threshold_box)

        # Warning threshold
        warn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        threshold_box.pack_start(warn_box, False, False, 0)
        
        warn_label = Gtk.Label(label="Warning notification at:")
        warn_box.pack_start(warn_label, False, False, 0)
        
        self.warn_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.warn_spin.set_value(self.config.getint("Settings", "notify_threshold", fallback=150))
        warn_box.pack_start(self.warn_spin, False, False, 0)
        warn_box.pack_start(Gtk.Label(label="packages"), False, False, 0)

        # Critical threshold
        crit_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        threshold_box.pack_start(crit_box, False, False, 0)
        
        crit_label = Gtk.Label(label="Critical notification at:")
        crit_box.pack_start(crit_label, False, False, 0)
        
        self.crit_spin = Gtk.SpinButton.new_with_range(1, 500, 1)
        self.crit_spin.set_value(self.config.getint("Settings", "critical_threshold", fallback=200))
        crit_box.pack_start(self.crit_spin, False, False, 0)
        crit_box.pack_start(Gtk.Label(label="packages"), False, False, 0)

        # Connect signals
        for radio in [self.daily_radio, self.weekly_radio, self.monthly_radio]:
            radio.connect("toggled", self.on_freq_changed)

        # Save button
        save_button = Gtk.Button(label="Save Configuration")
        save_button.get_style_context().add_class("suggested-action")
        save_button.set_margin_top(20)
        save_button.connect("clicked", self.on_save_config)
        config_page.pack_start(save_button, False, False, 0)

        self.notebook.append_page(config_page, Gtk.Label(label="Configuration"))

    def update_interval_label(self):
        if self.daily_radio.get_active():
            self.interval_label.set_text("day(s)")
        elif self.weekly_radio.get_active():
            self.interval_label.set_text("week(s)")
        else:
            self.interval_label.set_text("month(s)")

    def on_freq_changed(self, button):
        self.update_interval_label()

    def on_save_config(self, button):
        # Get selected frequency
        if self.daily_radio.get_active():
            freq = "day"
        elif self.weekly_radio.get_active():
            freq = "week"
        else:
            freq = "month"

        # Update config
        self.config["Settings"] = {
            "auto_check": str(self.auto_check_switch.get_active()),
            "check_every": freq,
            "check_through": str(self.through_spin.get_value_as_int()),
            "notify_threshold": str(self.warn_spin.get_value_as_int()),
            "critical_threshold": str(self.crit_spin.get_value_as_int()),
            "last_check": self.config.get("Settings", "last_check", fallback="")
        }
        
        self.save_config()

        # Show confirmation
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            message_format="Configuration saved successfully!"
        )
        dialog.run()
        dialog.destroy()

    def create_package_list_page(self):
        list_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        list_page.set_border_width(10)

        # Header
        header = Gtk.Label()
        header.set_markup("<b>Available Package Updates</b>")
        header.set_halign(Gtk.Align.START)
        list_page.pack_start(header, False, False, 0)

        # Refresh button
        self.refresh_button = Gtk.Button(label="Refresh Package List")
        self.refresh_button.connect("clicked", self.on_refresh_clicked)
        list_page.pack_start(self.refresh_button, False, False, 0)

        # Scrolled window
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        list_page.pack_start(scrolled, True, True, 0)

        # TreeView
        self.liststore = Gtk.ListStore(str, str, str)
        self.treeview = Gtk.TreeView(model=self.liststore)

        # Columns
        for i, title in enumerate(["Package", "Current Version", "New Version"]):
            renderer = Gtk.CellRendererText()
            column = Gtk.TreeViewColumn(title, renderer, text=i)
            if i == 0:
                column.set_sort_column_id(0)
            self.treeview.append_column(column)

        scrolled.add(self.treeview)

        # Status bar
        self.statusbar = Gtk.Statusbar()
        list_page.pack_start(self.statusbar, False, False, 0)

        self.notebook.append_page(list_page, Gtk.Label(label="Package List"))

    def create_updates_page(self):
        updates_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        updates_page.set_border_width(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<big><b>System Updates</b></big>")
        updates_page.pack_start(header, False, False, 10)

        # Update button
        self.update_button = Gtk.Button(label="Update All Packages")
        self.update_button.set_size_request(200, 50)
        self.update_button.get_style_context().add_class("suggested-action")
        self.update_button.connect("clicked", self.on_update_all_clicked)
        updates_page.pack_start(self.update_button, False, False, 20)

        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_text("Ready to update")
        updates_page.pack_start(self.progress_bar, False, False, 10)

        # Output console
        self.output_view = Gtk.TextView()
        self.output_view.set_editable(False)
        self.output_buffer = self.output_view.get_buffer()
        
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.add(self.output_view)
        updates_page.pack_start(scrolled, True, True, 0)

        self.notebook.append_page(updates_page, Gtk.Label(label="Updates"))

    def show_password_dialog(self):
        dialog = Gtk.Dialog(
            title="Confirm System Update",
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            buttons=(
                "Cancel", Gtk.ResponseType.CANCEL,
                "Update", Gtk.ResponseType.OK
            )
        )
        dialog.set_default_size(300, 150)

        content = dialog.get_content_area()
        
        warning = Gtk.Label(label="This will update your system packages.")
        warning.set_margin_bottom(10)
        content.pack_start(warning, False, False, 0)

        pass_label = Gtk.Label(label="Enter your password:")
        content.pack_start(pass_label, False, False, 0)

        self.pass_entry = Gtk.Entry()
        self.pass_entry.set_visibility(False)
        self.pass_entry.set_activates_default(True)
        content.pack_start(self.pass_entry, True, True, 0)

        content.show_all()
        response = dialog.run()
        password = self.pass_entry.get_text()
        dialog.destroy()

        return (response == Gtk.ResponseType.OK, password)

    def load_packages(self):
        self.refresh_button.set_sensitive(False)
        self._update_status("Loading package list...")

        # Update last check
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.config.set("Settings", "last_check", now)
        self.save_config()

        thread = threading.Thread(target=self._get_package_list)
        thread.daemon = True
        thread.start()

    def _get_package_list(self):
        try:
            output = subprocess.check_output(["xbps-install", "-un"], text=True)
            packages = []
            
            if output.strip():
                for line in output.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        packages.append((parts[0], parts[1], parts[2]))
            
            packages.sort(key=lambda x: x[0].lower())
            GLib.idle_add(self._update_package_list, packages)
            
            # Check thresholds
            warn_thresh = self.config.getint("Settings", "notify_threshold", fallback=150)
            crit_thresh = self.config.getint("Settings", "critical_threshold", fallback=200)
            
            if len(packages) > warn_thresh:
                self.send_notification(
                    "XBPS Package Updates",
                    f"Warning: {len(packages)} packages need updating!",
                    "critical" if len(packages) > crit_thresh else "normal"
                )
            
        except subprocess.CalledProcessError as e:
            GLib.idle_add(self._update_status, f"Error: {e}")
        finally:
            GLib.idle_add(self._enable_refresh)

    def on_update_all_clicked(self, button):
        confirmed, password = self.show_password_dialog()
        if not confirmed:
            self._append_output("Update cancelled by user.\n")
            return

        if not password:
            self._append_output("Error: No password provided.\n")
            return

        button.set_sensitive(False)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_text("Starting updates...")
        self.output_buffer.set_text("")
        
        thread = threading.Thread(target=self._perform_updates, args=(password,))
        thread.daemon = True
        thread.start()

    def _perform_updates(self, password):
        try:
            command = f"echo '{password}' | sudo -S xbps-install -Su"
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            for line in process.stdout:
                GLib.idle_add(self._append_output, line)
            
            process.wait()
            
            if process.returncode == 0:
                GLib.idle_add(self._update_complete, True)
                self.send_notification(
                    "XBPS Updates Complete",
                    "All packages have been successfully updated!",
                    "normal"
                )
            else:
                GLib.idle_add(self._update_complete, False)
                self.send_notification(
                    "XBPS Updates Failed",
                    "There were errors during the update process",
                    "critical"
                )
                
        except Exception as e:
            GLib.idle_add(self._append_output, f"Error: {str(e)}\n")
            GLib.idle_add(self._update_complete, False)
            self.send_notification(
                "XBPS Updates Error",
                f"Update process failed: {str(e)}",
                "critical"
            )

    def _update_complete(self, success):
        self.update_button.set_sensitive(True)
        if success:
            self.progress_bar.set_fraction(1.0)
            self.progress_bar.set_text("Updates completed successfully!")
            self.load_packages()
        else:
            self.progress_bar.set_fraction(0.0)
            self.progress_bar.set_text("Updates failed - see output")

    def _append_output(self, text):
        end_iter = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end_iter, text)
        mark = self.output_buffer.get_insert()
        iter = self.output_buffer.get_iter_at_mark(mark)
        self.output_view.scroll_to_iter(iter, 0.0, False, 0.0, 0.0)

    def _update_package_list(self, packages):
        self.liststore.clear()
        
        if not packages:
            self._update_status("All packages are up to date")
            self.update_button.set_sensitive(False)
            return
        
        for pkg in packages:
            self.liststore.append(pkg)
        
        self._update_status(f"Found {len(packages)} packages with updates")
        self.update_button.set_sensitive(True)

    def _update_status(self, message):
        self.statusbar.pop(0)
        self.statusbar.push(0, message)

    def _enable_refresh(self):
        self.refresh_button.set_sensitive(True)

    def send_notification(self, title, message, urgency="normal"):
        try:
            subprocess.run([
                "notify-send",
                "-i", "software-update-available",
                "-u", urgency,
                title,
                message
            ], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error sending notification: {e}")

    def on_refresh_clicked(self, button):
        self.load_packages()

def main():
    app = XBPSUpdaterApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
