# Danbooru Random Tag Generator (UI Version)
#
# A graphical user interface for the tag generator script.
# This version provides a window with interactive controls and automatically
# determines the total number of tag pages for a truly random selection.
#
# -- How to Use --
# 1. Make sure you have Python installed on your system.
# 2. Install the 'requests' library by opening your terminal or command prompt and running:
#    pip install requests
# 3. Save this script as a file (e.g., danbooru_tag_generator_ui.py).
# 4. Run the script from your terminal with:
#    python danbooru_tag_generator_ui.py

import requests
import random
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading

# --- Core API Logic ---

def fetch_tags(count):
    """
    Fetches a specified number of random tags from the Danbooru API by
    sampling tags from random posts, bypassing the 1000-page limit.
    This version prepends 'artist: ' to all artist tags and tracks source posts.
    Returns a tuple: (list_of_tags, list_of_post_urls, full_tag_pool, status_message)
    """
    # Using sets to automatically handle duplicates
    collected_tags = set()
    collected_artist_tags = set()
    source_post_urls = set()
    
    # We need to fetch enough posts to get a good variety of unique tags.
    # Let's aim to collect at least 3 times the needed tags as candidates.
    needed_candidates = count * 3 + 20 # Add a buffer
    max_requests = 10 # Safety break to prevent infinite loops
    requests_made = 0

    while len(collected_tags) + len(collected_artist_tags) < needed_candidates and requests_made < max_requests:
        # This endpoint respects the 'random=true' parameter, allowing a true random sample.
        api_url = f"https://danbooru.donmai.us/posts.json?limit=100&random=true"
        requests_made += 1
        
        try:
            headers = {'User-Agent': 'Danbooru-Random-Tag-Generator-UI/2.2'}
            response = requests.get(api_url, headers=headers, timeout=15)
            response.raise_for_status()
            posts = response.json()
            
            if not posts:
                continue

            for post in posts:
                # Add the post's URL to our sources set
                if 'id' in post:
                    source_post_urls.add(f"https://danbooru.donmai.us/posts/{post['id']}")

                # Danbooru API conveniently splits tags by category in post objects
                # Categories: 0=general, 1=artist, 3=copyright, 4=character, 5=meta
                general_tags = post.get('tag_string_general', '').split()
                copyright_tags = post.get('tag_string_copyright', '').split()
                character_tags = post.get('tag_string_character', '').split()
                meta_tags = post.get('tag_string_meta', '').split()
                
                collected_tags.update(general_tags)
                collected_tags.update(copyright_tags)
                collected_tags.update(character_tags)
                collected_tags.update(meta_tags)
                
                # Add artist tags to a separate set to be formatted later
                artist_tags = post.get('tag_string_artist', '').split()
                collected_artist_tags.update(artist_tags)
                                
        except requests.exceptions.RequestException as e:
            # If the API fails, stop and inform the user.
            return [], [], [], f"Error: Failed to fetch posts from Danbooru. {e}"

    # Combine the collected tags, formatting artist tags appropriately.
    final_pool = list(collected_tags) + [f"artist: {tag}" for tag in collected_artist_tags]
    
    if len(final_pool) < count:
        # Not enough unique tags were found, so return everything we have.
        random.shuffle(final_pool)
        return final_pool, list(source_post_urls), final_pool, f"Warning: Found only {len(final_pool)} unique tags. Returning all."

    # Randomly select the requested number of tags from the final pool.
    selected_tags = random.sample(final_pool, count)
    
    return selected_tags, list(source_post_urls), final_pool, f"Success! Generated {len(selected_tags)} tags from random posts."

# --- Tkinter UI Application Class ---

class TagGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Danbooru Random Tag Generator")
        self.root.geometry("800x600")
        self.root.minsize(600, 450)
        self.post_source_urls = []
        self.full_tag_pool = []

        # --- LAYOUT MANAGEMENT ---
        # Status bar is created first and packed at the bottom to reserve its space.
        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor='w')
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # A new container for the main content that will fill the remaining space.
        content_container = ttk.Frame(root)
        content_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- SCROLLBAR IMPLEMENTATION ---
        # The canvas and scrollbar now belong to the content_container, not the root window.
        self.canvas = tk.Canvas(content_container)
        self.scrollbar = ttk.Scrollbar(content_container, orient="vertical", command=self.canvas.yview)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)
        # --- END SCROLLBAR IMPLEMENTATION ---

        # Style configuration
        style = ttk.Style()
        style.configure("TLabel", padding=5, font=('Helvetica', 10))
        style.configure("TButton", padding=5, font=('Helvetica', 10, 'bold'))
        style.configure("TRadiobutton", padding=5, font=('Helvetica', 10))
        style.configure("TFrame", padding=10)
        style.configure("Header.TLabel", font=('Helvetica', 14, 'bold'))

        # Main content is now placed in the scrollable_frame
        main_frame = self.scrollable_frame 

        # --- UI Elements ---
        ttk.Label(main_frame, text="Tag Generation Options", style="Header.TLabel").pack(pady=(10, 10), padx=10)

        # Mode selection
        self.mode = tk.StringVar(value="fixed")
        fixed_radio = ttk.Radiobutton(main_frame, text="Fixed Number", variable=self.mode, value="fixed", command=self.toggle_mode)
        random_radio = ttk.Radiobutton(main_frame, text="Random Range", variable=self.mode, value="random", command=self.toggle_mode)
        fixed_radio.pack(anchor='w', padx=10)
        random_radio.pack(anchor='w', padx=10)
        
        # Input fields frame
        self.input_frame = ttk.Frame(main_frame)
        self.input_frame.pack(fill=tk.X, pady=5, padx=10)
        
        self.fixed_entry = self.create_input_field("Number of tags:", 0)
        self.min_entry = self.create_input_field("Minimum tags:", 1)
        self.max_entry = self.create_input_field("Maximum tags:", 2)

        # Generate button
        self.generate_button = ttk.Button(main_frame, text="Generate Tags", command=self.start_generation_thread)
        self.generate_button.pack(pady=10, fill=tk.X, padx=10)

        # Results and Pool Area using PanedWindow
        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(pady=5, fill=tk.BOTH, expand=True, padx=10)

        # Left Pane: Generated Tags
        left_pane = ttk.Frame(paned_window, padding=5)
        paned_window.add(left_pane, weight=1)
        ttk.Label(left_pane, text="Generated Tags").pack(anchor='w')
        self.results_text = scrolledtext.ScrolledText(left_pane, wrap=tk.WORD, height=10, state='disabled', font=('Helvetica', 10))
        self.results_text.pack(fill=tk.BOTH, expand=True)

        # Right Pane: Full Tag Pool
        right_pane = ttk.Frame(paned_window, padding=5)
        paned_window.add(right_pane, weight=1)
        self.tag_pool_label_var = tk.StringVar(value="Full Tag Pool")
        ttk.Label(right_pane, textvariable=self.tag_pool_label_var).pack(anchor='w')
        self.tag_pool_text = scrolledtext.ScrolledText(right_pane, wrap=tk.WORD, height=10, state='disabled', font=('Helvetica', 10))
        self.tag_pool_text.pack(fill=tk.BOTH, expand=True)
        
        # Save buttons frame
        save_frame = ttk.Frame(main_frame)
        save_frame.pack(fill=tk.X, pady=(5,10), padx=10)
        save_frame.columnconfigure(0, weight=1)
        save_frame.columnconfigure(1, weight=1)

        self.save_tags_button = ttk.Button(save_frame, text="Save Tags to .txt", command=self.save_tags_file, state='disabled')
        self.save_tags_button.grid(row=0, column=0, sticky='ew', padx=(0, 5))
        
        self.save_sources_button = ttk.Button(save_frame, text="Save Post Sources to .txt", command=self.save_post_sources, state='disabled')
        self.save_sources_button.grid(row=0, column=1, sticky='ew', padx=(5, 0))
        
        self.toggle_mode()

    def on_canvas_configure(self, event):
        """Resizes the inner frame to match the canvas width."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Handles mouse wheel scrolling for Windows, MacOS, and Linux."""
        # The delta value differs by OS, this logic handles them.
        if event.num == 5 or event.delta == -120:
            delta = 1
        elif event.num == 4 or event.delta == 120:
            delta = -1
        else:
            delta = -1 * (event.delta // 120) # For high-precision mice
            
        self.canvas.yview_scroll(delta, "units")

    def create_input_field(self, label_text, row):
        """Helper to create a label and entry widget."""
        ttk.Label(self.input_frame, text=label_text).grid(row=row, column=0, sticky='w', padx=5)
        entry = ttk.Entry(self.input_frame, width=10)
        entry.grid(row=row, column=1, sticky='w')
        return entry

    def toggle_mode(self):
        """Enable/disable input fields based on selected mode."""
        if self.mode.get() == "fixed":
            self.fixed_entry.config(state='normal')
            self.min_entry.config(state='disabled')
            self.max_entry.config(state='disabled')
        else: # random mode
            self.fixed_entry.config(state='disabled')
            self.min_entry.config(state='normal')
            self.max_entry.config(state='normal')

    def start_generation_thread(self):
        """Starts the tag fetching process in a new thread to avoid freezing the UI."""
        self.generate_button.config(state='disabled')
        self.save_tags_button.config(state='disabled')
        self.save_sources_button.config(state='disabled')
        
        # Clear previous data and UI elements
        self.post_source_urls = [] 
        self.full_tag_pool = []
        self.results_text.config(state='normal')
        self.results_text.delete('1.0', tk.END)
        self.results_text.config(state='disabled')
        self.tag_pool_text.config(state='normal')
        self.tag_pool_text.delete('1.0', tk.END)
        self.tag_pool_text.config(state='disabled')
        self.tag_pool_label_var.set("Full Tag Pool")

        self.update_status("Validating input...")

        try:
            if self.mode.get() == 'fixed':
                count = int(self.fixed_entry.get())
            else:
                min_val = int(self.min_entry.get())
                max_val = int(self.max_entry.get())
                if min_val > max_val:
                    messagebox.showerror("Input Error", "Minimum value cannot be greater than the maximum value.")
                    self.generate_button.config(state='normal')
                    self.update_status("Ready.")
                    return
                count = random.randint(min_val, max_val)
            
            threading.Thread(target=self.run_fetch_logic, args=(count,), daemon=True).start()

        except ValueError:
            messagebox.showerror("Input Error", "Please enter valid whole numbers for the tag amounts.")
            self.generate_button.config(state='normal')
            self.update_status("Ready.")
    
    def update_status(self, message):
        """Schedules a status bar update on the main thread."""
        self.root.after(0, self.status_var.set, message)

    def run_fetch_logic(self, count):
        """The actual logic that runs in the background."""
        self.update_status("Fetching tags from random posts...")
        tags, post_urls, full_pool, message = fetch_tags(count)
        self.post_source_urls = post_urls
        self.full_tag_pool = full_pool
        
        # Update UI with final result
        self.root.after(0, self.update_ui, tags, message)

    def update_ui(self, tags, message):
        """Updates the UI with the results from the background thread."""
        self.status_var.set(message)
        
        # --- Update Generated Tags Box ---
        self.results_text.config(state='normal')
        self.results_text.delete('1.0', tk.END)
        if tags is not None and tags:
            formatted_tags = [tag.replace('_', ' ') for tag in tags]
            self.results_text.insert(tk.END, ", ".join(formatted_tags))
            self.save_tags_button.config(state='normal')
        self.results_text.config(state='disabled')
        
        # --- Update Full Tag Pool Box ---
        self.tag_pool_text.config(state='normal')
        self.tag_pool_text.delete('1.0', tk.END)
        if self.full_tag_pool:
            self.tag_pool_label_var.set(f"Full Tag Pool ({len(self.full_tag_pool)} tags)")
            formatted_pool = sorted([tag.replace('_', ' ') for tag in self.full_tag_pool])
            self.tag_pool_text.insert(tk.END, "\n".join(formatted_pool))
        else:
            self.tag_pool_label_var.set("Full Tag Pool")
        self.tag_pool_text.config(state='disabled')

        # --- Update Buttons ---
        if self.post_source_urls:
            self.save_sources_button.config(state='normal')
        self.generate_button.config(state='normal')

    def save_tags_file(self):
        """Opens a save dialog and saves the generated tags to a text file."""
        content = self.results_text.get('1.0', tk.END).strip()
        if not content:
            messagebox.showwarning("Warning", "There are no tags to save.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Save Tags As..."
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                self.update_status(f"Tags saved to {filepath}")
            except IOError as e:
                messagebox.showerror("Save Error", f"Could not save file. Reason: {e}")
                
    def save_post_sources(self):
        """Saves the list of source post URLs to a text file."""
        if not self.post_source_urls:
            messagebox.showwarning("Warning", "There are no post sources to save.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Save Post Sources As..."
        )
        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(sorted(self.post_source_urls)))
                self.update_status(f"Post sources saved to {filepath}")
            except IOError as e:
                messagebox.showerror("Save Error", f"Could not save file. Reason: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = TagGeneratorApp(root)
    root.mainloop()

