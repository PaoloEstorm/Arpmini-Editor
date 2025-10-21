import customtkinter as ctk
ctk.set_appearance_mode("dark")
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import os
import serial
import threading
import serial.tools.list_ports

NUM_SLOTS = 60
EXPORT_SIZE = 288 # 8X32(n.tracks X n.notes)+32(config) bytes

class ArpminiEditor(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("Arpmini Editor")
        self.geometry("420x330")
        self.resizable(False, False)

        self.slot_status = ["empty"] * NUM_SLOTS
        self.selected_slot = None
        self.serial_port = None
        self.connected = False

        self.app_center_x = 0
        self.app_center_y = 0
        self.update_app_center()  # initial calc
        self.bind("<Configure>", lambda e: self.update_app_center())

        self.create_widgets()
        self.refresh_serial_ports()
        self.monitor_connection()

    def update_app_center(self):
        self.update_idletasks()  # make sure sizes are updated
        app_x = self.winfo_rootx()
        app_y = self.winfo_rooty()
        app_width = self.winfo_width()
        app_height = self.winfo_height()
        self.app_center_x = app_x + app_width // 2
        self.app_center_y = app_y + app_height // 2

    def create_widgets(self):
        self.connected = False
        self.grid_columnconfigure(0, weight=1, uniform="group1")
        self.grid_columnconfigure(1, weight=2, uniform="group1")

        self.grid_rowconfigure(1, weight=1)

        # Connection bar
        self.connection_frame = ctk.CTkFrame(self)
        self.connection_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(5, 0))

        initial_ports = self.get_serial_ports()
        if not initial_ports:
            initial_ports = ["No ports found"]

        self.port_menu = ctk.CTkOptionMenu(self.connection_frame, values=initial_ports, width=305)
        self.port_menu.set(initial_ports[0])
        self.port_menu.grid(row=0, column=0, padx=5, pady=5)

        self.connect_button = ctk.CTkButton(self.connection_frame, text="Connect", command=self.toggle_connection, fg_color="#4CAF50",  hover_color="#309533", width=85, height=28)
        self.connect_button.grid(row=0, column=1, padx=5, pady=5)


        if initial_ports[0] == "No ports found":
            self.port_menu.configure(state="disabled")
            self.connect_button.configure(state="disabled")

        # Left side: Slot list
        self.slot_listbox = ctk.CTkScrollableFrame(self)
        self.slot_listbox.grid(row=1, column=0, sticky="nswe", padx=5, pady=5)
        self.slot_buttons = []

        for i in range(NUM_SLOTS):
            btn = ctk.CTkButton(self.slot_listbox, text=f"Empty {i+1}", width=107, height=40,
                                command=lambda i=i: self.select_slot(i))
            btn.pack(pady=2 , padx=0)
            self.slot_buttons.append(btn)

        # Set all slots disabled and gray at startup
        for i, btn in enumerate(self.slot_buttons):
            btn.configure(state="disabled", text=f"Slot {i+1}", fg_color="#444444")

        # Right side: Action buttons
        self.right_frame = ctk.CTkFrame(self)
        self.right_frame.grid(row=1, column=1, sticky="nswe", padx=5, pady=5)

        self.slot_label = ctk.CTkLabel(self.right_frame, text="Disconnected", text_color="#888888")
        self.slot_label.pack(pady=(10, 0))

        self.import_button = ctk.CTkButton(self.right_frame, text="Import Song",
                                           command=self.import_song, state="disabled")
        self.import_button.pack(pady=20)

        self.export_button = ctk.CTkButton(self.right_frame, text="Export Song",
                                           command=self.export_song, state="disabled")
        self.export_button.pack(pady=20)

        self.clear_button = ctk.CTkButton(self.right_frame, text="Clear Song",
                                          command=self.clear_song, state="disabled", fg_color="#ED3E3E", hover_color="#B82C2C")
        self.clear_button.pack(pady=20)

    def refresh_serial_ports(self):
        current_ports = self.get_serial_ports()
        if not current_ports:
            current_ports = ["No ports found"]

        menu_ports = self.port_menu.cget("values")

        if current_ports != list(menu_ports):
            self.port_menu.configure(values=current_ports)
            self.port_menu.set(current_ports[0])

            if current_ports[0] == "No ports found":
                self.port_menu.configure(state="disabled")
                self.connect_button.configure(state="disabled")
            else:
                self.port_menu.configure(state="normal")
                self.connect_button.configure(state="normal")

        self.after(2000, self.refresh_serial_ports)

    def monitor_connection(self):
        if self.connected and self.serial_port:
            try:
                self.serial_port.in_waiting  # simple connection test
            except (serial.SerialException, OSError):
                self.after(100, self.toggle_connection)  # call the disconnection
        self.after(1000, self.monitor_connection)  # check every second

    def get_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_info_map = {}
        items = []

        for port in ports:
            
            if port.vid == 0x2341 and port.pid == 0x9030:
                label = f"{port.device} - Arpmini"
                items.append(label)
                self.port_info_map[label] = port.device 

        if not items:
            items = ["No Arpmini found"]

        return items

    def toggle_connection(self):
        def set_enabled(state):
            for btn in self.slot_buttons:
                btn.configure(state=state)
            self.import_button.configure(state=state)
            self.export_button.configure(state=state)
            self.clear_button.configure(state=state)

        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.serial_port = None
            self.connect_button.configure(text="Connect", fg_color="#4CAF50", hover_color="#309533")
            set_enabled("disabled")
            self.slot_label.configure(text="Disconnected", text_color="#888888")

            self.connected = False
            self.port_menu.configure(state="normal")
            for i, btn in enumerate(self.slot_buttons):
                btn.configure(state="disabled", text=f"Slot {i+1}", fg_color="#444444")
            self.selected_slot = None
            self.import_button.configure(state="disabled")
            self.export_button.configure(state="disabled")
            self.clear_button.configure(state="disabled")
            return

        label = self.port_menu.get()
        port_name = self.port_info_map.get(label)

        if not port_name or label == "No ports found":
            self.show_popup("Error", "No serial ports available.")
            return


        try:
            self.serial_port = serial.Serial(port_name, 115200, timeout=1)
            self.connect_button.configure(text="Disconnect", fg_color="#ED3E3E", hover_color="#B82C2C")
            for btn in self.slot_buttons:
                btn.configure(state="normal")
            self.port_menu.configure(state="disabled")
            self.connected = True
            self.import_button.configure(state="disabled")
            self.export_button.configure(state="disabled")
            self.clear_button.configure(state="disabled")
            self.selected_slot = None
            self.update_right_buttons()
            threading.Thread(target=self.initial_check_all_slots, daemon=True).start()
        except serial.SerialException:
            self.show_popup("Connection Error", "Failed to connect to the device.")

    def initial_check_all_slots(self):
        for i in range(NUM_SLOTS):
            status = self.check_slot(i + 1)
            if status == 0:
                self.slot_status[i] = "empty"
            elif status == 1:
                self.slot_status[i] = "song"
            elif status == 2:
                self.slot_status[i] = "drum"
            self.update_slot_label(i)

    def update_slot_label(self, i):
        label = self.slot_status[i].capitalize() + f" {i+1}"

        if self.slot_status[i] == "empty":
            fg = "#444444"        # gray
            hover = "#3C3C3C"     # darker gray
        else:
            fg = "#1f6aa5"        # blu
            hover = "#154a7a"     # darker blu

        self.slot_buttons[i].configure(
            text=label,
            fg_color=fg,
            hover_color=hover
        )

    def select_slot(self, i):
        if not self.connected:
            return
        self.selected_slot = i
        # Reset all buttons color to base
        for j, btn in enumerate(self.slot_buttons):
            base_color = "#444444" if self.slot_status[j] == "empty" else "#1f6aa5"
            btn.configure(fg_color=base_color)

        # Make selected slot color darker
        if self.slot_status[i] == "empty":
            self.slot_buttons[i].configure(fg_color="#343434")
        else:
            self.slot_buttons[i].configure(fg_color="#163858")

        self.update_right_buttons()

    def update_right_buttons(self):
        i = self.selected_slot
        if i is None:
            self.import_button.configure(state="disabled")
            self.export_button.configure(state="disabled")
            self.clear_button.configure(state="disabled")
            if self.connected:
                self.slot_label.configure(text="Select one Slot", text_color="#DBDADA")

            else:
                self.slot_label.configure(text="Disconnected", text_color="#888888")

            return

        self.import_button.configure(state="normal")

        if self.slot_status[i] == "empty":
            self.export_button.configure(state="disabled")
            self.clear_button.configure(state="disabled")
        else:
            self.export_button.configure(state="normal")
            self.clear_button.configure(state="normal")

        slot_type = self.slot_status[i].capitalize()
        self.slot_label.configure(text=f"{slot_type} {i+1}")

    def check_slot(self, slot_number):
        if not self.serial_port:
            return 0
        try:
            self.serial_port.write(bytes([0xFC, slot_number, 0x00]))  # trigger dummy
            response = self.serial_port.read(2)
            if len(response) == 2 and response[1] == 0xFC:
                return response[0]
        except Exception:
            return 0
        return 0

    def import_song(self):
        file_path = fd.askopenfilename(filetypes=[("Arpmini Files", "*.arpmini")])
        if not file_path:
            return

        try:
            with open(file_path, 'rb') as f:
                data = f.read()
        except Exception as e:
            self.show_popup("Error", f"Could not read file: {e}")
            return

        if len(data) != EXPORT_SIZE:
            self.show_popup("Error", "Invalid file size. Must be exactly 288 bytes.")
            return

        if self.slot_status[self.selected_slot] != "empty":
            confirm = self.ask_yes_no("Overwrite Confirmation",
                                  "This operation will irreversibly overwrite the selected slot. Proceed?")
            if not confirm:
                return

        try:
            self.serial_port.write(bytes([0xFE, self.selected_slot + 1]))
            for byte in data:
                self.serial_port.write(bytes([byte]))
                ack = self.serial_port.read(1)
                if ack != bytes([0xFE]):
                    self.show_popup("Error", "Invalid ACK during transfer.")
                    return
            final_ack = self.serial_port.read(1)
            if final_ack != bytes([0xFF]):
                self.show_popup("Error", "Final confirmation byte not received.")
                return
            status = self.check_slot(self.selected_slot + 1)
            if status == 0:
                self.slot_status[self.selected_slot] = "empty"
            elif status == 1:
                self.slot_status[self.selected_slot] = "song"
            elif status == 2:
                self.slot_status[self.selected_slot] = "drum"
            self.update_slot_label(self.selected_slot)
            self.update_right_buttons()
            self.show_popup("Success", f"Slot {self.selected_slot + 1} updated successfully.")
        except Exception as e:
            self.show_popup("Error", f"Import failed: {e}")

    def export_song(self):
        file_path = fd.asksaveasfilename(defaultextension=".arpmini",
                                         filetypes=[("Arpmini Files", "*.arpmini")])
        if not file_path:
            return
        if not self.serial_port or not self.serial_port.is_open:
            self.show_popup("Error", "Serial port not connected.")
            return

        try:
            self.serial_port.write(bytes([0xFD, self.selected_slot + 1, 0x00]))  # trigger dummy
            data = self.serial_port.read(EXPORT_SIZE + 1)
            if len(data) == EXPORT_SIZE + 1 and data[-1] == 0xFF:
                with open(file_path, 'wb') as f:
                    f.write(data[:-1])
                self.show_popup("Export", f"Exported slot {self.selected_slot + 1} to {file_path}")
            else:
                self.show_popup("Error", "Invalid or incomplete data received from device.")
        except Exception as e:
            self.show_popup("Error", f"Export failed: {e}")

    def clear_song(self):
        if self.selected_slot is None:
            return
        confirm = self.ask_yes_no("Clear Slot Confirmation",
                              "This operation will irreversibly erase the selected slot. Proceed?")
        if not confirm:
            return

        try:
            self.serial_port.write(bytes([0xFE, self.selected_slot + 1]))
            self.serial_port.write(bytes([0x00]))
            ack = self.serial_port.read(1)
            if ack != bytes([0xFE]):
                self.show_popup("Error", "Acknowledgment byte not received after sending 0x00.")
                return
            self.serial_port.write(bytes([0xFF]))
            final_ack = self.serial_port.read(1)
            if final_ack != bytes([0xFF]):
                self.show_popup("Error", "Final acknowledgment byte not received.")
                return
            status = self.check_slot(self.selected_slot + 1)
            if status == 0:
                self.slot_status[self.selected_slot] = "empty"
            elif status == 1:
                self.slot_status[self.selected_slot] = "song"
            elif status == 2:
                self.slot_status[self.selected_slot] = "drum"
            self.update_slot_label(self.selected_slot)
            self.update_right_buttons()
            self.show_popup("Success", f"Slot {self.selected_slot + 1} cleared successfully.")
        except Exception as e:
            self.show_popup("Error", f"Clear operation failed: {e}")

    def show_popup(self, title, message):
        popup_width = 300
        popup_height = 150

        popup = ctk.CTkToplevel(self)
        popup.withdraw()  # temporarely hide
        popup.overrideredirect(True)
        popup.title(title)
        popup.resizable(False, False)

        popup.transient(self)       # link the popup to the main window
        popup.lift()                # bring the popup to the front
        popup.grab_set()            # block interaction outside the popup
        popup.focus_force()         # force the focus

        # Calculate the position before showing it
        pos_x = self.app_center_x - (popup_width // 2)
        pos_y = self.app_center_y - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{pos_x}+{pos_y}")

        popup.deiconify() # show popup

        label = ctk.CTkLabel(popup, text=message, wraplength=280)
        label.pack(pady=20)

        ok_button = ctk.CTkButton(popup, text="OK", command=popup.destroy)
        ok_button.pack(pady=10)

        popup.grab_set()
        popup.focus_force()

    def ask_yes_no(self, title, message):
        response = [None]
        popup_width = 300
        popup_height = 150

        popup = ctk.CTkToplevel(self)
        popup.withdraw()  # temporarely hide
        popup.overrideredirect(True)
        popup.title(title)
        popup.resizable(False, False)

        popup.transient(self)       # link the popup to the main window
        popup.lift()                # bring the popup to the front
        popup.grab_set()            # block interaction outside the popup
        popup.focus_force()         # force the focus

        pos_x = self.app_center_x - (popup_width // 2)
        pos_y = self.app_center_y - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{pos_x}+{pos_y}")

        popup.deiconify() # show popup
        popup.grab_set()

        label = ctk.CTkLabel(popup, text=message, wraplength=260)
        label.pack(padx=20, pady=20)

        def on_yes():
            response[0] = True
            popup.destroy()

        def on_no():
            response[0] = False
            popup.destroy()

        btn_frame = ctk.CTkFrame(popup, fg_color=popup._fg_color, border_width=0)
        btn_frame.pack(pady=10)

        yes_btn = ctk.CTkButton(btn_frame, text="Yes", command=on_yes, width=100)
        yes_btn.pack(side="left", padx=10)

        no_btn = ctk.CTkButton(btn_frame, text="No", command=on_no, width=100)
        no_btn.pack(side="left", padx=10)

        popup.wait_window()
        return response[0]

if __name__ == '__main__':
    app = ArpminiEditor()
    app.mainloop()
