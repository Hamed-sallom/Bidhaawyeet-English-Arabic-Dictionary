import os, sys, sqlite3, time
# Wayland and X11 safe platform environment fallback routing
os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QTextEdit, QPushButton, QTextBrowser, QLabel, QMessageBox, QInputDialog, QListWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, "dictionary.db")
AUDIO_DIR = os.path.join(SCRIPT_DIR, "audio")
IMAGES_DIR = os.path.join(SCRIPT_DIR, "images")

def setup_database_and_folders():
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lexicon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bija_word TEXT UNIQUE NOT NULL,
            english_word TEXT NOT NULL,
            arabic_word TEXT,
            notes TEXT,
            image_file TEXT,
            audio_file TEXT
        )
    """)
    
    # LA SOLUCIÓN REAL DEFINITIVA: Extraer estrictamente el elemento string del nombre (col[1])
    cursor.execute("PRAGMA table_info(lexicon)")
    column_names = [col[1] for col in cursor.fetchall()]
    
    if "arabic_word" not in column_names:
        cursor.execute("ALTER TABLE lexicon ADD COLUMN arabic_word TEXT")
        conn.commit()
        
    cursor.execute("SELECT COUNT(*) FROM lexicon")
    if cursor.fetchone() == 0:
        sample_data = [
            ("Tak", "Man", "رجل", "Noun, masculine.\nExample: 'Uu Tak, oo Tak' (The man).", "man.png", "tak.mp3"),
            ("Takat", "Woman", "امرأة", "Noun, feminine.\nExample: 'Tu Takat, Ti Takat' (The woman).", "woman.png", "takat.mp3")
        ]
        cursor.executemany("INSERT OR IGNORE INTO lexicon (bija_word, english_word, arabic_word, notes, image_file, audio_file) VALUES (?, ?, ?, ?, ?, ?)", sample_data)
        conn.commit()
    conn.close()

class AdvancedBidhaawyeetDictionary(QWidget):
    def __init__(self):
        super().__init__()
        self.current_audio = None
        self.current_word_id = None  
        self.is_admin = False  
        try:
            import pygame
            pygame.mixer.init()
            self.has_mixer = True
        except ImportError:
            self.has_mixer = False
        self.initUI()
        self.refresh_word_list()
        
    def initUI(self):
        self.setWindowTitle("Bidhaawyeet (Beja) Dictionary Studio")
        self.resize(1000, 750) 
        
        self.setStyleSheet("""
            QWidget { background-color: #0a2240; color: #f5f7fa; font-family: 'Helvetica'; }
            QLineEdit, QTextEdit { background-color: #12355b; color: white !important; border: 2px solid #009688; border-radius: 6px; padding-left: 10px; font-size: 14px; }
            QLineEdit#searchBar { height: 35px; }
            QTextBrowser { background-color: #12355b; color: white; border: 2px solid #009688; border-radius: 6px; padding: 10px; }
            QListWidget { background-color: #12355b; color: white; border: 1px solid #009688; border-radius: 6px; padding: 5px; font-size: 14px; }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #1a3a60; }
            QListWidget::item:selected { background-color: #009688; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton { background-color: #009688; color: white; border-radius: 6px; font-weight: bold; height: 35px; }
            QPushButton:disabled { background-color: #445566; color: #8899aa; }
            
            QWidget#adminPanel QLineEdit, QWidget#adminPanel QTextEdit { 
                background-color: #12355b !important; 
                color: white !important; 
                border: 2px solid #009688; 
                border-radius: 4px; 
                padding: 6px; 
                font-size: 13px; 
            }
            QWidget#adminPanel QLabel { color: #f5f7fa; font-weight: bold; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        top_header = QHBoxLayout()
        self.title_label = QLabel("Bidhaawyeet Digital Lexicon, by M.Karrar")
        self.title_label.setFont(QFont("Helvetica", 12, QFont.Bold))
        
        self.backup_btn = QPushButton("💾 Backup DB")
        self.backup_btn.setFixedWidth(110)
        self.backup_btn.setStyleSheet("background-color: #009688; font-size: 11px;")
        self.backup_btn.clicked.connect(self.backup_database)
        
        self.lock_btn = QPushButton("🔒 Admin Unlock")
        self.lock_btn.setFixedWidth(120)
        self.lock_btn.setStyleSheet("background-color: #0d47a1; font-size: 11px;")
        self.lock_btn.clicked.connect(self.prompt_admin_login)
        
        top_header.addWidget(self.title_label, stretch=1)
        top_header.addWidget(self.backup_btn)
        top_header.addWidget(self.lock_btn)
        main_layout.addLayout(top_header)
        
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBar")
        self.search_input.setPlaceholderText("Search in Bidhaawyeet, English, or Arabic...")
        self.search_input.returnPressed.connect(self.lookup_word)
        self.search_input.textChanged.connect(self.filter_word_list)
        
        self.search_btn = QPushButton("Search")
        self.search_btn.setFixedWidth(110)
        self.search_btn.clicked.connect(self.lookup_word)
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_btn)
        main_layout.addLayout(search_layout)
        
        content_grid = QGridLayout()
        
        translation_panel = QHBoxLayout()
        translation_panel.setSpacing(10)
        
        self.word_list_widget = QListWidget()
        self.word_list_widget.setFixedWidth(220) 
        self.word_list_widget.itemClicked.connect(self.word_list_item_clicked)
        
        self.trans_box = QTextBrowser()
        self.trans_box.setPlaceholderText("English & Arabic outputs...")
        
        translation_panel.addWidget(self.word_list_widget)
        translation_panel.addWidget(self.trans_box)
        
        content_grid.addWidget(QLabel("<b>Primary Translations & Word Index</b>"), 0, 0)
        content_grid.addLayout(translation_panel, 1, 0)
        
        right_panel = QVBoxLayout()
        self.image_box = QLabel("No Image Loaded")
        self.image_box.setFixedSize(240, 160)
        self.image_box.setStyleSheet("background-color: #12355b; border: 2px dashed #009688; border-radius: 6px;")
        self.image_box.setAlignment(Qt.AlignCenter)
        
        self.audio_btn = QPushButton("🔊 Play Pronunciation")
        self.audio_btn.setStyleSheet("background-color: #ff5722;") 
        self.audio_btn.setEnabled(False)
        self.audio_btn.clicked.connect(self.play_audio)
        
        self.notes_box = QTextBrowser()
        self.notes_box.setPlaceholderText("Linguistic details here...")
        
        right_panel.addWidget(QLabel("<b>Visual Reference</b>"))
        right_panel.addWidget(self.image_box)
        right_panel.addWidget(self.audio_btn)
        right_panel.addWidget(QLabel("<b>Grammar Notes</b>"))
        right_panel.addWidget(self.notes_box)
        
        content_grid.addLayout(right_panel, 0, 1, 2, 1)
        content_grid.setColumnStretch(0, 3)
        content_grid.setColumnStretch(1, 2)
        main_layout.addLayout(content_grid)
        # Admin Layout Widget Setup
        self.admin_widget = QWidget()
        self.admin_widget.setObjectName("adminPanel")
        self.admin_widget.setStyleSheet("background-color: #0e2e56; border-radius: 8px; padding: 10px;")
        self.admin_widget.setVisible(False) 
        
        form_layout = QGridLayout(self.admin_widget)
        self.input_bija = QLineEdit()
        self.input_english = QLineEdit()
        self.input_arabic = QLineEdit()
        self.input_arabic.setAlignment(Qt.AlignRight)
        self.input_image = QLineEdit()
        self.input_audio = QLineEdit()
        
        self.input_notes = QTextEdit()
        self.input_notes.setMaximumHeight(80)
        
        form_layout.addWidget(QLabel("Bija Word:"), 0, 0)
        form_layout.addWidget(self.input_bija, 0, 1)
        form_layout.addWidget(QLabel("English Translation:"), 1, 0)
        form_layout.addWidget(self.input_english, 1, 1)
        form_layout.addWidget(QLabel("Arabic Translation:"), 2, 0)
        form_layout.addWidget(self.input_arabic, 2, 1)
        form_layout.addWidget(QLabel("Image File Name:"), 3, 0)
        form_layout.addWidget(self.input_image, 3, 1)
        form_layout.addWidget(QLabel("Audio File Name:"), 4, 0)
        form_layout.addWidget(self.input_audio, 4, 1)
        form_layout.addWidget(QLabel("Grammar/Usage Notes (Supports HTML tables):"), 5, 0)
        form_layout.addWidget(self.input_notes, 5, 1)
        
        self.save_btn = QPushButton("💾 Save Entry")
        self.save_btn.setStyleSheet("background-color: #4caf50;")
        self.save_btn.clicked.connect(self.save_entry)
        form_layout.addWidget(self.save_btn, 6, 0, 1, 2)
        
        main_layout.addWidget(self.admin_widget)

    def prompt_admin_login(self):
        if self.is_admin:
            self.is_admin = False
            self.lock_btn.setText("🔒 Admin Unlock")
            self.lock_btn.setStyleSheet("background-color: #0d47a1; font-size: 11px;")
            self.admin_widget.setVisible(False)
            return
            
        text, ok = QInputDialog.getText(self, 'Security Access', 'Enter Admin Security Key:', QLineEdit.Password)
        if ok and text == 'admin': 
            self.is_admin = True
            self.lock_btn.setText("🔓 Admin Lock")
            self.lock_btn.setStyleSheet("background-color: #d32f2f; font-size: 11px;")
            self.admin_widget.setVisible(True)
        elif ok:
            QMessageBox.warning(self, "Access Denied", "Incorrect administrative password key.")

    def save_entry(self):
        bija = self.input_bija.text().strip()
        english = self.input_english.text().strip()
        arabic = self.input_arabic.text().strip()
        notes = self.input_notes.toPlainText().strip()
        image = self.input_image.text().strip()
        audio = self.input_audio.text().strip()
        
        if not bija or not english:
            QMessageBox.warning(self, "Data Missing", "Bija Word and English fields are strictly required.")
            return
            
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO lexicon (bija_word, english_word, arabic_word, notes, image_file, audio_file)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (bija, english, arabic, notes, image, audio))
            conn.commit()
            conn.close()
            
            self.input_bija.clear()
            self.input_english.clear()
            self.input_arabic.clear()
            self.input_notes.clear()
            self.input_image.clear()
            self.input_audio.clear()
            
            self.refresh_word_list()
            QMessageBox.information(self, "Success", f"'{bija}' successfully registered in database.")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Database operation failed:\n{e}")

    def refresh_word_list(self):
        self.word_list_widget.clear()
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT bija_word FROM lexicon ORDER BY bija_word ASC")
            for row in cursor.fetchall():
                item = row[0]
                self.word_list_widget.addItem(item)
                # Mantener los elementos ocultos por defecto al arrancar
                self.word_list_widget.item(self.word_list_widget.count() - 1).setHidden(True)
            conn.close()
        except Exception as e:
            pass

    def filter_word_list(self):
        search_text = self.search_input.text().lower().strip()
        
        for i in range(self.word_list_widget.count()):
            item = self.word_list_widget.item(i)
            if not search_text:
                item.setHidden(True)
            else:
                item.setHidden(not item.text().lower().startswith(search_text))

    def lookup_word(self):
        search_text = self.search_input.text().strip()
        if not search_text:
            return
        self.display_word_details(search_text)

    def word_list_item_clicked(self, item):
        self.display_word_details(item.text())

    def display_word_details(self, term):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT id, bija_word, english_word, arabic_word, notes, image_file, audio_file FROM lexicon WHERE bija_word=? OR english_word=? OR arabic_word=?", (term, term, term))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                self.current_word_id, bija, eng, arab, notes, img_file, aud_file = row
                
                html_report = f"""
                <h2 style='color:#009688; margin:0;'>{bija}</h2>
                <hr style='border:1px solid #009688;'>
                <p><b>English:</b> {eng}</p>
                <p><b>Arabic / العالمية:</b> <span style='font-size:16px;'>{arab if arab else '---'}</span></p>
                """
                self.trans_box.setHtml(html_report)
                
                if notes:
                    self.notes_box.setHtml(notes)
                else:
                    self.notes_box.setHtml("<i>No grammar notes provided for this term.</i>")
                
                if img_file:
                    full_img_path = os.path.join(IMAGES_DIR, img_file)
                    if os.path.exists(full_img_path):
                        pixmap = QPixmap(full_img_path).scaled(240, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.image_box.setPixmap(pixmap)
                    else:
                        self.image_box.setText("[ Image File Missing ]")
                        self.image_box.setPixmap(QPixmap())
                else:
                    self.image_box.setText("No Image Loaded")
                    self.image_box.setPixmap(QPixmap())
                    
                if aud_file:
                    self.current_audio = os.path.join(AUDIO_DIR, aud_file)
                    self.audio_btn.setEnabled(os.path.exists(self.current_audio))
                else:
                    self.current_audio = None
                    self.audio_btn.setEnabled(False)
        except Exception as e:
            pass

    def play_audio(self):
        if self.has_mixer and self.current_audio and os.path.exists(self.current_audio):
            import pygame
            try:
                pygame.mixer.music.load(self.current_audio)
                pygame.mixer.music.play()
            except Exception as e:
                QMessageBox.warning(self, "Audio Failure", f"Playback error:\n{e}")

    def backup_database(self):
        try:
            backup_file = os.path.join(SCRIPT_DIR, f"dictionary_bak_{int(time.time())}.db")
            conn = sqlite3.connect(DB_PATH)
            bck = sqlite3.connect(backup_file)
            conn.backup(bck)
            bck.close()
            conn.close()
            QMessageBox.information(self, "Backup Status", f"Database backed up securely:\n{os.path.basename(backup_file)}")
        except Exception as e:
            QMessageBox.critical(self, "Backup Error", f"Backup execution sequence failed:\n{e}")

if __name__ == "__main__":
    setup_database_and_folders()
    app = QApplication(sys.argv)
    ex = AdvancedBidhaawyeetDictionary()
    ex.show()
    sys.exit(app.exec_())
