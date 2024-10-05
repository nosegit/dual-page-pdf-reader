import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
from PIL import Image, ImageTk
from pdf2image import convert_from_path
from PyPDF2 import PdfReader
import os
import threading
import multiprocessing


class PDFReader:
    def __init__(self, root):
        self.root = root
        self.root.title("Dual Page PDF Reader")

        # Set default window size
        self.root.geometry("1200x850")  # Set your desired width and height here

        # Configure the grid to expand with the window
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self.canvas1 = tk.Canvas(root, bg="white")
        self.canvas2 = tk.Canvas(root, bg="white")
        self.canvas1.grid(row=0, column=0, sticky="nsew")
        self.canvas2.grid(row=0, column=1, sticky="nsew")


        # Page number display
        self.page_number_label = tk.Label(root, text="", font=("Arial", 10))
        self.page_number_label.grid(row=1, column=0, columnspan=2, sticky="n")

        self.pages = []
        self.current_page1 = 0
        self.current_page2 = 1
        self.is_shifted = False  # Track the shift state

        # Loading bar
        self.progress = ttk.Progressbar(root, orient="horizontal", mode="determinate")
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew")

        # Menu for opening files and navigation
        menu = tk.Menu(root)
        root.config(menu=menu)
        file_menu = tk.Menu(menu)
        view_menu = tk.Menu(menu)

        # Adding "File" menu
        menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open PDF", command=self.open_pdf)

        # Adding "View" menu with submenus
        menu.add_cascade(label="View", menu=view_menu)
        image_size_menu = tk.Menu(view_menu)
        view_menu.add_cascade(label="Image Size", menu=image_size_menu)
        image_size_menu.add_command(label="Small", command=lambda: self.resize_window(800, 600))
        image_size_menu.add_command(label="Medium", command=lambda: self.resize_window(1200, 850))
        image_size_menu.add_command(label="Large", command=lambda: self.resize_window(1280, 800))
        view_menu.add_command(label="Swap Pages", command=self.swap_pages)
        view_menu.add_command(label="Shift/Unshift Pages", command=self.toggle_shift)

        # Navigation buttons
        self.prev_button = tk.Button(root, text="Previous Page", command=self.previous_page)
        self.prev_button.grid(row=3, column=0, sticky="ew")

        self.next_button = tk.Button(root, text="Next Page", command=self.next_page)
        self.next_button.grid(row=3, column=1, sticky="ew")

        # Bind the close button to a custom function
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def resize_window(self, width, height):
        """Resize the application window."""
        self.root.geometry(f"{width}x{height}")

    def open_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if file_path:
            # Update window title with the PDF name
            pdf_name = os.path.basename(file_path)
            self.root.title(f"Dual Page PDF Reader - {pdf_name}")

            # Path to the poppler bin folder
            script_dir = os.path.dirname(os.path.abspath(__file__))
            self.poppler_bin_path = os.path.join(script_dir, 'poppler-24.07.0', 'Library', 'bin')

            # Reset state for new PDF
            self.pages = []  # Clear previous pages
            self.current_page1 = 0
            self.current_page2 = 1
            self.progress['value'] = 0
            self.progress.grid()  # Show progress bar

            # Disable buttons during loading
            self.prev_button.config(state="disabled")
            self.next_button.config(state="disabled")

            # Start loading in a separate thread
            threading.Thread(target=self.load_pdf, args=(file_path,)).start()

    def load_pdf(self, file_path):
        # Convert the PDF to images and update progress
        self.pages = self.convert_pdf_to_images(file_path)

        # Resize all pages to the smallest one
        self.shrink_pages_to_smallest()

        # Enable buttons after loading
        self.prev_button.config(state="normal")
        self.next_button.config(state="normal")

        self.current_page1, self.current_page2 = 0, 1
        self.load_pages(self.current_page1, self.current_page2)

        # Hide progress bar
        self.progress.grid_remove()

    def convert_pdf_to_images(self, file_path):
        # Get total number of pages using PyPDF2
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            total_pages = len(reader.pages)

        batch_size = 40  # Define your batch size
        with multiprocessing.Manager() as manager:
            completed_count = manager.Value('i', 0)  # Shared variable to track completed tasks

            # Convert pages using multiprocessing
            with multiprocessing.Pool() as pool:
                # Prepare the arguments for each batch
                for batch_start in range(1, total_pages + 1, batch_size):
                    batch_end = min(batch_start + batch_size - 1, total_pages)
                    args = [(file_path, i, self.poppler_bin_path, completed_count, total_pages) for i in range(batch_start, batch_end + 1)]

                    # Process the batch
                    batch_results = pool.starmap(self.convert_single_page, args)

                    # Append results to pages
                    for page in batch_results:
                        if page is not None:
                            self.pages.append(page)

                    # Update progress bar for conversion (0-50%)
                    completed_count.value += len(args)
                    self.progress['value'] = (completed_count.value / total_pages) * 50
                    self.progress.update()

        return self.pages

    @staticmethod
    def convert_single_page(file_path, page_number, poppler_bin_path, completed_count, total_pages):
        # Convert a single page from PDF to image
        try:
            page = convert_from_path(file_path, first_page=page_number, last_page=page_number, poppler_path=poppler_bin_path)[0]
            return page
        except Exception as e:
            print(f"Error converting page {page_number}: {e}")
            return None

    def shrink_pages_to_smallest(self):
        # Find the smallest page size
        if not self.pages:
            return  # No pages to process

        smallest_width = min(page.size[0] for page in self.pages)
        smallest_height = min(page.size[1] for page in self.pages)

        batch_size = 50  # Define your batch size
        with multiprocessing.Manager() as manager:
            completed_count = manager.Value('i', 0)  # Shared variable to track completed tasks

            # Resize all pages using multiprocessing
            with multiprocessing.Pool() as pool:
                for i in range(0, len(self.pages), batch_size):
                    batch = self.pages[i:i + batch_size]
                    args = [(page, smallest_width, smallest_height, completed_count, len(batch)) for page in batch]

                    # Process the batch
                    resized_batch = pool.starmap(self.resize_page, args)

                    # Append resized pages to pages list
                    self.pages[i:i + len(resized_batch)] = resized_batch

                    # Update progress bar for resizing (50-100%)
                    completed_count.value += len(args)
                    self.progress['value'] = 50 + (completed_count.value / len(self.pages)) * 50
                    self.progress.update()

    @staticmethod
    def resize_page(page, width, height, completed_count, total_pages):
        resized_page = page.resize((width, height), Image.LANCZOS)
        return resized_page

    def swap_pages(self):
        self.current_page1, self.current_page2 = self.current_page2, self.current_page1
        self.load_pages(self.current_page1, self.current_page2)

    def toggle_shift(self):
        if self.is_shifted:
            self.unshift_pages()
        else:
            self.shift_pages()

    def shift_pages(self):
        if self.pages:
            # Make sure we don't go beyond the number of pages
            if self.current_page2 < len(self.pages) - 1:
                self.current_page1 += 1
                self.current_page2 += 1
                self.is_shifted = True  # Update the shift state
                self.load_pages(self.current_page1, self.current_page2)

    def unshift_pages(self):
        if self.pages:
            # Make sure we don't go before page 0
            if self.current_page1 > 0:
                self.current_page1 -= 1
                self.current_page2 -= 1
                self.is_shifted = False  # Update the shift state
                self.load_pages(self.current_page1, self.current_page2)

    def next_page(self):
        if self.pages:
            # Make sure we don't go beyond the number of pages
            if self.current_page2 < len(self.pages) - 1:
                self.current_page1 += 2
                self.current_page2 += 2
                self.load_pages(self.current_page1, self.current_page2)

    def previous_page(self):
        if self.pages:
            # Make sure we don't go before page 0
            if self.current_page1 > 1:
                self.current_page1 -= 2
                self.current_page2 -= 2
                self.load_pages(self.current_page1, self.current_page2)

    def load_pages(self, page1_num, page2_num):
        if self.pages:
            # Update the page number display
            self.page_number_label.config(text=f"Page {page1_num + 1} and {page2_num + 1}")

            # Get page 1
            if page1_num < len(self.pages):
                page1_img = self.pages[page1_num]
                self.render_page(page1_img, self.canvas1)

            # Get page 2
            if page2_num < len(self.pages):
                page2_img = self.pages[page2_num]
                self.render_page(page2_img, self.canvas2)

    def render_page(self, page_img, canvas):
        # Resize the page image to fit the canvas, maintaining the aspect ratio
        canvas_width = canvas.winfo_width()
        canvas_height = canvas.winfo_height()

        # Get image dimensions
        img_width, img_height = page_img.size

        # Maintain aspect ratio
        ratio = min(canvas_width / img_width, canvas_height / img_height)
        new_width = int(img_width * ratio)
        new_height = int(img_height * ratio)

        resized_img = page_img.resize((new_width, new_height), Image.LANCZOS)

        # Convert the image for Tkinter
        tk_img = ImageTk.PhotoImage(resized_img)

        # Clear the canvas and display the new image
        canvas.delete("all")
        canvas.create_image(0, 0, anchor=tk.NW, image=tk_img)
        canvas.image = tk_img  # Keep reference to avoid garbage collection
        
    def on_close(self):
        """Clean up and close the application."""
        # When closing, all pools created in the context of the `with` statement will be terminated automatically.
        self.root.destroy()  # Close the Tkinter window

# Initialize the GUI
if __name__ == "__main__":
    root = tk.Tk()
    app = PDFReader(root)
    root.mainloop()
