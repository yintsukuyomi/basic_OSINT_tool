import aiohttp
import asyncio
import sys
import os
import logging
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QTextEdit, QProgressBar, 
                            QMessageBox, QFileDialog, QStatusBar, QComboBox, QCheckBox, QScrollArea, QFormLayout)
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Translation dictionaries
translations = {
    'en': {
        'username_label': 'Username:',
        'search_button': 'Search',
        'save_button': 'Save',
        'copy_button': 'Copy',
        'ready_status': 'Ready',
        'enter_username': 'Please enter a username!',
        'searching_status': "Searching for username '{}'...",
        'search_completed': 'Search completed!',
        'warning': 'Warning',
        'no_results_save': 'No results to save!',
        'no_results_copy': 'No results to copy!',
        'error': 'Error',
        'save_error': 'Error saving file: {}',
        'saved_to_file': 'Results saved to {}!',
        'copied_to_clipboard': 'Results copied to clipboard!',
        'window_title': 'OSINT Tool',
        'found': '[+] FOUND: {}',
        'not_found': '[-] NOT FOUND: {}',
        'error_prefix': '[!] ERROR: {}',
        'timeout': '[-] TIMEOUT: {}',
        'clear_button': 'Clear',
        'include_timestamp': 'Include timestamp in results'
    },
    'ja': {
        'username_label': 'ユーザー名:',
        'search_button': '検索',
        'save_button': '保存',
        'copy_button': 'コピー',
        'ready_status': '準備完了',
        'enter_username': 'ユーザー名を入力してください！',
        'searching_status': "ユーザー名「{}」を検索中...",
        'search_completed': '検索完了！',
        'warning': '警告',
        'no_results_save': '保存する結果がありません！',
        'no_results_copy': 'コピーする結果がありません！',
        'error': 'エラー',
        'save_error': 'ファイル保存エラー: {}',
        'saved_to_file': '結果が{}に保存されました！',
        'copied_to_clipboard': '結果がクリップボードにコピーされました！',
        'window_title': 'OSINT ツール',
        'found': '[+] 発見: {}',
        'not_found': '[-] 未発見: {}',
        'error_prefix': '[!] エラー: {}',
        'timeout': '[-] タイムアウト: {}',
        'clear_button': 'クリア',
        'include_timestamp': '結果にタイムスタンプを含める'
    },
    'tr': {
        'username_label': 'Kullanıcı Adı:',
        'search_button': 'Ara',
        'save_button': 'Kaydet',
        'copy_button': 'Kopyala',
        'ready_status': 'Hazır',
        'enter_username': 'Lütfen bir kullanıcı adı girin!',
        'searching_status': "'{}' kullanıcı adı için arama yapılıyor...",
        'search_completed': 'Arama tamamlandı!',
        'warning': 'Uyarı',
        'no_results_save': 'Kaydedilecek sonuç bulunamadı!',
        'no_results_copy': 'Kopyalanacak sonuç bulunamadı!',
        'error': 'Hata',
        'save_error': 'Dosya kaydedilirken hata oluştu: {}',
        'saved_to_file': 'Sonuçlar {} dosyasına kaydedildi!',
        'copied_to_clipboard': 'Sonuçlar panoya kopyalandı!',
        'window_title': 'OSINT Aracı',
        'found': '[+] BULUNDU: {}',
        'not_found': '[-] YOK: {}',
        'error_prefix': '[!] HATA: {}',
        'timeout': '[-] ZAMAN AŞIMI: {}',
        'clear_button': 'Temizle',
        'include_timestamp': 'Sonuçlara zaman damgası ekle'
    }
}

class AsyncWorker(QThread):
    result_ready = pyqtSignal(str)
    progress_update = pyqtSignal(int, int)
    finished = pyqtSignal()

    def __init__(self, username, platforms, language='tr'):
        super().__init__()
        self.username = username
        self.platforms = platforms
        self.language = language

    async def fetch_platform(self, session, platform, username, index, total):
        url = platform.format(username=username)
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    result = translations[self.language]['found'].format(url)
                elif response.status == 404:
                    result = translations[self.language]['not_found'].format(url)
                else:
                    result = translations[self.language]['error_prefix'].format(f"{url} - HTTP {response.status}")
        except asyncio.TimeoutError:
            result = translations[self.language]['timeout'].format(url)
        except Exception as e:
            result = translations[self.language]['error_prefix'].format(f"{url} - {str(e)}")
            logging.error(f"Error fetching {url}: {str(e)}")
            
        self.progress_update.emit(index + 1, total)
        return result

    async def search_username_async(self):
        results = []
        total = len(self.platforms)

        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_platform(session, platform, self.username, i, total) 
                    for i, platform in enumerate(self.platforms)]
            for i, future in enumerate(asyncio.as_completed(tasks)):
                result = await future
                results.append(result)
                self.result_ready.emit(result)

        return results

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(self.search_username_async())
            loop.close()
            self.finished.emit()
        except Exception as e:
            self.result_ready.emit(f"Error: {str(e)}")
            self.finished.emit()

class OSINTApp(QWidget):
    def __init__(self):
        super().__init__()
        self.current_language = 'tr'  # Default language is Turkish
        self.platforms = [
            'https://github.com/{username}',
            'https://twitter.com/{username}',
            'https://www.instagram.com/{username}',
            'https://www.reddit.com/user/{username}',
            'https://www.facebook.com/{username}',
            'https://www.linkedin.com/in/{username}',
            'https://www.tiktok.com/@{username}',
            'https://www.pinterest.com/{username}',
            'https://www.youtube.com/user/{username}',
            'https://www.twitch.tv/{username}',
            'https://medium.com/@{username}',
            'https://dev.to/{username}',
            'https://www.behance.net/{username}',
            'https://gitlab.com/{username}',
            'https://www.quora.com/profile/{username}',
            'https://open.spotify.com/user/{username}',
            'https://steamcommunity.com/id/{username}',
            'https://soundcloud.com/{username}',
            'https://www.flickr.com/people/{username}',
            'https://vimeo.com/{username}',
            'https://t.me/{username}',
            'https://www.dailymotion.com/{username}',
            'https://www.patreon.com/{username}',
            'https://www.tumblr.com/{username}',
            'https://www.goodreads.com/{username}',
            'https://www.last.fm/user/{username}',
            'https://www.mixcloud.com/{username}',
            'https://www.slideshare.net/{username}',
            'https://www.deviantart.com/{username}',
            'https://www.okcupid.com/profile/{username}',
            'https://www.fiverr.com/{username}',
            'https://www.producthunt.com/@{username}',
            'https://www.about.me/{username}',
            'https://www.angellist.com/{username}',
            'https://www.bandcamp.com/{username}',
            'https://www.blogger.com/profile/{username}',
            'https://www.crunchbase.com/person/{username}',
            'https://www.dribbble.com/{username}',
            'https://www.etsy.com/people/{username}',
            'https://www.instructables.com/member/{username}',
            'https://www.kickstarter.com/profile/{username}',
            'https://www.livejournal.com/{username}',
            'https://www.myspace.com/{username}',
            'https://www.periscope.tv/{username}',
            'https://www.plurk.com/{username}',
            'https://www.snapchat.com/add/{username}',
            'https://www.tripit.com/people/{username}',
            'https://www.vine.co/{username}',
            'https://www.weibo.com/{username}',
            'https://www.wix.com/{username}',
            'https://www.yelp.com/user_details?userid={username}',
            'https://www.zhihu.com/people/{username}'
        ]
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)

        header_layout = QHBoxLayout()

        title_label = QLabel(translations[self.current_language]['window_title'])
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        lang_layout = QHBoxLayout()
        lang_label = QLabel('Dil:')
        lang_layout.addWidget(lang_label)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem('Türkçe', 'tr')
        self.lang_combo.addItem('English', 'en')
        self.lang_combo.addItem('日本語', 'ja')
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        self.lang_combo.setFixedWidth(100)
        lang_layout.addWidget(self.lang_combo)

        header_layout.addLayout(lang_layout)
        layout.addLayout(header_layout)

        line = QLabel()
        line.setFrameShape(QLabel.HLine)
        line.setFrameShadow(QLabel.Sunken)
        layout.addWidget(line)

        input_layout = QHBoxLayout()

        self.label = QLabel(translations[self.current_language]['username_label'])
        self.label.setFixedWidth(100)
        input_layout.addWidget(self.label)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("johndoe")
        input_layout.addWidget(self.input)

        self.search_btn = QPushButton(translations[self.current_language]['search_button'], self)
        self.search_btn.clicked.connect(self.start_search)
        self.search_btn.setFixedWidth(100)
        input_layout.addWidget(self.search_btn)

        layout.addLayout(input_layout)

        self.timestamp_checkbox = QCheckBox(translations[self.current_language]['include_timestamp'], self)
        layout.addWidget(self.timestamp_checkbox)

        progress_layout = QHBoxLayout()

        self.progress = QProgressBar(self)
        self.progress.setRange(0, 100)
        progress_layout.addWidget(self.progress)

        self.progress_label = QLabel("0/0")
        self.progress_label.setFixedWidth(50)
        progress_layout.addWidget(self.progress_label)

        layout.addLayout(progress_layout)

        self.result_area = QTextEdit(self)
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.save_btn = QPushButton(translations[self.current_language]['save_button'], self)
        self.save_btn.clicked.connect(self.save_results)
        self.save_btn.setEnabled(False)
        action_layout.addWidget(self.save_btn)

        self.copy_btn = QPushButton(translations[self.current_language]['copy_button'], self)
        self.copy_btn.clicked.connect(self.copy_to_clipboard)
        self.copy_btn.setEnabled(False)
        action_layout.addWidget(self.copy_btn)

        self.clear_btn = QPushButton(translations[self.current_language]['clear_button'], self)
        self.clear_btn.clicked.connect(self.clear_results)
        self.clear_btn.setFixedWidth(100)
        action_layout.addWidget(self.clear_btn)

        layout.addLayout(action_layout)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage(translations[self.current_language]['ready_status'])
        layout.addWidget(self.status_bar)

        self.setLayout(layout)
        self.setWindowTitle(translations[self.current_language]['window_title'])
        self.resize(600, 500)

        self.setStyleSheet("""
            QWidget {
                font-size: 11pt;
            }
            QProgressBar {
                text-align: center;
            }
            QLineEdit {
                padding: 5px;
            }
            QPushButton {
                padding: 5px 10px;
            }
        """)

    def change_language(self):
        self.current_language = self.lang_combo.currentData()
        self.label.setText(translations[self.current_language]['username_label'])
        self.search_btn.setText(translations[self.current_language]['search_button'])
        self.save_btn.setText(translations[self.current_language]['save_button'])
        self.copy_btn.setText(translations[self.current_language]['copy_button'])
        self.clear_btn.setText(translations[self.current_language]['clear_button'])
        self.timestamp_checkbox.setText(translations[self.current_language]['include_timestamp'])
        self.status_bar.showMessage(translations[self.current_language]['ready_status'])
        self.setWindowTitle(translations[self.current_language]['window_title'])

    def start_search(self):
        username = self.input.text().strip()
        if not username:
            self.show_message(translations[self.current_language]['warning'], translations[self.current_language]['enter_username'], QMessageBox.Warning)
            return

        self.result_area.clear()
        self.status_bar.showMessage(translations[self.current_language]['searching_status'].format(username))

        self.worker = AsyncWorker(username, self.platforms, self.current_language)
        self.worker.result_ready.connect(self.display_result)
        self.worker.progress_update.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        self.clear_btn.setEnabled(False)

    def display_result(self, result):
        self.result_area.append(result)

    def update_progress(self, current, total):
        self.progress.setValue(int((current / total) * 100))
        self.progress_label.setText(f"{current}/{total}")

    def on_finished(self):
        self.save_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.status_bar.showMessage(translations[self.current_language]['search_completed'])

    def save_results(self):
        results = self.result_area.toPlainText()
        if not results.strip():
            self.show_message(translations[self.current_language]['warning'], translations[self.current_language]['no_results_save'], QMessageBox.Warning)
            return

        if self.timestamp_checkbox.isChecked():
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            results = f"{timestamp}\n{results}"

        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(self, translations[self.current_language]['save_button'], "", "Text Files (*.txt);;All Files (*)", options=options)
        if file_name:
            try:
                with open(file_name, 'w') as f:
                    f.write(results)
                self.show_message(translations[self.current_language]['save_button'], translations[self.current_language]['saved_to_file'].format(file_name), QMessageBox.Information)
            except Exception as e:
                self.show_message(translations[self.current_language]['error'], translations[self.current_language]['save_error'].format(e), QMessageBox.Critical)
                logging.error(f"Error saving file {file_name}: {str(e)}")

    def copy_to_clipboard(self):
        results = self.result_area.toPlainText()
        if not results.strip():
            self.show_message(translations[self.current_language]['warning'], translations[self.current_language]['no_results_copy'], QMessageBox.Warning)
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(results)
        self.show_message(translations[self.current_language]['save_button'], translations[self.current_language]['copied_to_clipboard'], QMessageBox.Information)

    def clear_results(self):
        self.result_area.clear()
        self.progress.setValue(0)
        self.progress_label.setText("0/0")
        self.save_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.status_bar.showMessage(translations[self.current_language]['ready_status'])

    def show_message(self, title, message, icon):
        msg_box = QMessageBox()
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec_()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = OSINTApp()
    window.show()
    sys.exit(app.exec_())
