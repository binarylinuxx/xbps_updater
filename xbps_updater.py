import gi
import subprocess
import threading
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

class XBPSUpdaterApp(Gtk.Window):
    def __init__(self):
        Gtk.Window.__init__(self, title="XBPS Package Updater")
        self.set_default_size(600, 400)
        self.set_border_width(10)

        # Main container
        self.notebook = Gtk.Notebook()
        self.add(self.notebook)

        # Create Package List page
        self.create_package_list_page()
        # Create Updates page
        self.create_updates_page()

        # Initial load
        self.load_packages()

    def create_package_list_page(self):
        # Package List Page
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

        # Scrolled window for the list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        list_page.pack_start(scrolled, True, True, 0)

        # TreeView for packages
        self.liststore = Gtk.ListStore(str, str, str)  # name, current, new
        self.treeview = Gtk.TreeView(model=self.liststore)

        # Columns
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Package", renderer, text=0)
        column.set_sort_column_id(0)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Current Version", renderer, text=1)
        self.treeview.append_column(column)

        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("New Version", renderer, text=2)
        self.treeview.append_column(column)

        scrolled.add(self.treeview)

        # Status bar
        self.statusbar = Gtk.Statusbar()
        list_page.pack_start(self.statusbar, False, False, 0)

        self.notebook.append_page(list_page, Gtk.Label(label="Package List"))

    def create_updates_page(self):
        # Updates Page
        updates_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        updates_page.set_border_width(20)

        # Header
        header = Gtk.Label()
        header.set_markup("<big><b>System Updates</b></big>")
        updates_page.pack_start(header, False, False, 10)

        # Update All button
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

        # Output text view
        self.output_view = Gtk.TextView()
        self.output_view.set_editable(False)
        self.output_view.set_cursor_visible(False)
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

        content_area = dialog.get_content_area()
        
        # Warning message
        warning = Gtk.Label(label="This will update your system packages.")
        warning.set_margin_bottom(10)
        content_area.pack_start(warning, False, False, 0)

        # Password entry
        password_label = Gtk.Label(label="Enter your password:")
        content_area.pack_start(password_label, False, False, 0)

        password_entry = Gtk.Entry()
        password_entry.set_visibility(False)  # Hide password
        password_entry.set_activates_default(True)
        content_area.pack_start(password_entry, True, True, 0)

        content_area.show_all()
        
        response = dialog.run()
        password = password_entry.get_text()
        dialog.destroy()

        return (response == Gtk.ResponseType.OK, password)

    def load_packages(self):
        self.refresh_button.set_sensitive(False)
        self._update_status("Loading package list...")

        # Run in a separate thread to keep UI responsive
        thread = threading.Thread(target=self._get_package_list)
        thread.daemon = True
        thread.start()

    def _get_package_list(self):
        try:
            # Get list of outdated packages
            output = subprocess.check_output(["xbps-install", "-un"], text=True)
            packages = []
            
            if output.strip():
                for line in output.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        pkg_name = parts[0]
                        current_ver = parts[1]
                        new_ver = parts[2]
                        packages.append((pkg_name, current_ver, new_ver))
            
            # Sort alphabetically
            packages.sort(key=lambda x: x[0].lower())
            
            # Update UI in main thread
            GLib.idle_add(self._update_package_list, packages)
            
            # Check for large number of updates
            if len(packages) > 150:
                self.send_notification(
                    "XBPS Package Updates",
                    f"Warning: {len(packages)} packages need updating!",
                    "critical" if len(packages) > 200 else "normal"
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
            # Prepare the command with password for sudo
            command = f"echo '{password}' | sudo xbps-install -Syu"
            
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            
            # Read output line by line
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
            # Refresh package list
            self.load_packages()
        else:
            self.progress_bar.set_fraction(0.0)
            self.progress_bar.set_text("Updates failed - see output")

    def _append_output(self, text):
        end_iter = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end_iter, text)
        
        # Auto-scroll to the end
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
        """Send desktop notification"""
        try:
            subprocess.run([
                "notify-send",
                "-i", "software-update-available",
                "-u", urgency,
                title,
                message
            ])
        except FileNotFoundError:
            print("notify-send command not found. Desktop notifications unavailable.")
        except Exception as e:
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
