import tkinter as tk
from tkinter import messagebox, StringVar

class LifiApp:
    def __init__(self, master):
        self.master = master
        master.title("Lifi GUI")

        # Improved visual organization
        self.frame = tk.Frame(master)
        self.frame.pack(padx=10, pady=10)

        self.input_var = StringVar()
        self.label = tk.Label(self.frame, text="Enter Your Input:")
        self.label.grid(row=0, column=0, sticky="w")

        self.entry = tk.Entry(self.frame, textvariable=self.input_var)
        self.entry.grid(row=0, column=1)

        self.submit_button = tk.Button(self.frame, text="Submit", command=self.process_input)
        self.submit_button.grid(row=0, column=2, padx=5)

        # Status indicator setup
        self.status_label = tk.Label(self.frame, text="Status: Ready")
        self.status_label.grid(row=1, columnspan=3, sticky="w")

    def process_input(self):
        user_input = self.input_var.get()
        if self.validate_input(user_input):
            self.status_label.config(text="Status: Processing...")
            # Process the input (Assuming some processing happens here)
            self.status_label.config(text="Status: Complete")
            messagebox.showinfo("Success", "Input processed successfully!")
        else:
            messagebox.showerror("Input Error", "Please enter a valid input!")
            self.status_label.config(text="Status: Input Error")

    def validate_input(self, user_input):
        # Simple validation for the example
        return len(user_input) > 0 and user_input.isalnum()

if __name__ == '__main__':
    root = tk.Tk()
    app = LifiApp(root)
    root.mainloop()