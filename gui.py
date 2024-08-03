from PyQt5.QtGui import QPixmap, QIcon, QFont, QPainter, QColor, QDropEvent, QDragEnterEvent, QGuiApplication, QImage
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QPushButton, QApplication, QWidget, QButtonGroup, QRadioButton, QHBoxLayout, QSlider
from PyQt5.QtCore import Qt, QTimer, QSize, QRect, QEvent
import requests
import os
import threading
from scribble import Drawer
import keyboard
import base64

class ImageDisplay(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.initClipboardMonitor()

        self.original_pixmap = None
        self.preview_image = None
        self.max_height = self.photoViewer.geometry().height() - 10
        self.max_width = self.photoViewer.geometry().width() - 10

        self.speed = 0

        self.draw_path = self.get_absolute_path('References/draw.png')
        self.preview_path = self.get_absolute_path('References/preview.png')

        self.setAcceptDrops(True)

        self.setFixedSize(self.size())  

        self.draw = Drawer()
        self.draw.drawing_started.connect(self.drawing_started)
        self.draw.drawing_stopped.connect(self.drawing_stopped)
        self.draw.preview_signal.connect(self.show_preview_image)
        self.draw.data_signal.connect(self.estimate_time)
        self.draw.canvas_not_detected.connect(self.canvas_not_detected)

        self.delete_file(self.draw_path)
        self.delete_file(self.preview_path)
        self.checkClipboard()


        keyboard.add_hotkey('ctrl+shift+s', self.start_drawing)
        keyboard.add_hotkey('ctrl+shift+f', self.toggle_radio_button)
        keyboard.add_hotkey('ctrl+shift+x', self.crop_image)

    def event(self, event):
        if event.type() == QEvent.KeyPress:
            key_event = event
            if key_event.key() == Qt.Key_Shift:
                self.speed_slider.setValue(0)
                self.sliderChange(0)  # Set value to 0 if Shift is pressed
                return True
        return super().event(event)

    def initUI(self):
        screen = QGuiApplication.primaryScreen()
        screen_size = screen.availableGeometry()
        x_pos = int(screen_size.width() - 408)
        y_pos = int(screen_size.height() * 0.25)
        self.setGeometry(x_pos, y_pos, int(screen_size.width() * 0.12), int(screen_size.height() * 0.18))
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: #202020; color: white")
        self.setWindowTitle("Scribbl Drawer")
        self.setWindowIcon(QIcon(self.get_absolute_path('Assets/windowicon.png')))
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

    
        self.photoViewer = QLabel(self)
        self.photoViewer.setAlignment(Qt.AlignCenter)
        self.photoViewer.setText('Copy or Drag Image')
        ProductSans = QFont("Product Sans", 10)
        QApplication.setFont(ProductSans)
        self.photoViewer.setStyleSheet('''
            QLabel{
                border: 4px dashed #aaa;
                border-radius: 15px;
            }
        ''')
        self.photoViewer.setFixedHeight(int(screen_size.width() * 0.09))
        self.layout.addWidget(self.photoViewer)

         # Layout for the toggle buttons
        self.toggle_layout = QHBoxLayout()
        self.button_group = QButtonGroup(self)
        self.scribble_button = QRadioButton('Skribbl', self)
        self.sketchful_button = QRadioButton('Sketchful', self)
        self.paint_button = QRadioButton('Paint', self)
        
        self.scribble_button.setToolTip('<font color="black">Change application. Ctrl + Shift + F</font>')
        self.sketchful_button.setToolTip('<font color="black">Change application. Ctrl + Shift + F</font>')
        self.paint_button.setToolTip('<font color="black">Change application. Ctrl + Shift + F</font>')


        self.scribble_button.setStyleSheet("""color: white; font-size: 20px;""")
        self.sketchful_button.setStyleSheet("""color: white; font-size: 20px;""")
        self.paint_button.setStyleSheet("""color: white; font-size: 20px;""")

        self.button_group.addButton(self.scribble_button)
        self.button_group.addButton(self.sketchful_button)
        self.button_group.addButton(self.paint_button)

        self.sketchful_button.setChecked(True)

        self.toggle_layout.addWidget(self.scribble_button)
        self.toggle_layout.addWidget(self.sketchful_button)
        self.toggle_layout.addWidget(self.paint_button)

        self.layout.addLayout(self.toggle_layout)

        self.crop_button = QPushButton(self)
        self.crop_button.setIcon(QIcon(self.get_absolute_path('Assets/crop.png')))
        self.crop_button.setIconSize(QSize(30, 30))
        self.crop_button.setCursor(Qt.PointingHandCursor)
        self.crop_button.setStyleSheet("""
            QPushButton {
                background-color: #959595;
                color: white;
                border-radius: 8px;
                border: 2px solid #3a3a3a;
                padding: 8px 10px;
            }
            QPushButton:hover {
                background-color: #a5a5a5;   
            }
            QPushButton:checked {
                background-color: #65c057;
            }
        """)
        self.crop_button.setCheckable(True)
        self.crop_button.toggled.connect(self.updateImagePreview)
        self.crop_button.setToolTip('''
            <style>
                /* Set background color and padding */
                .tooltip {
                    color: black; /* Text color */
                    border-radius: 15px; /* Rounded corners */
                    padding: 5px; /* Padding around text */
                    font-size: 20px; /* Smaller text size */
                }
            </style>
            <div class="tooltip">
                Crop the bottom 20 pixels of image. Ctrl + Shift + X
            </div>
        ''')

        self.preview_button = QPushButton(self)
        self.preview_button.setIcon(QIcon(self.get_absolute_path('Assets/preview.png')))
        self.preview_button.setIconSize(QSize(30, 30))
        self.preview_button.setCursor(Qt.PointingHandCursor)
        self.preview_button.setStyleSheet("""
            QPushButton {
                background-color: #959595;
                color: white;
                border-radius: 8px;
                border: 2px solid #3a3a3a;
                padding: 8px 10px;
            }
            QPushButton:hover {
                background-color: #a5a5a5;   
            }
            QPushButton:checked {
                background-color: #65c057;  /* Color when checked */
            }
        """)
        self.preview_button.setCheckable(True)
        self.preview_button.toggled.connect(lambda: self.show_preview_image(None))
        self.preview_button.setToolTip('<font color="black">Preview Sketch</font>')

        self.crop_button.hide()
        self.preview_button.hide()

        self.speed_layout = QHBoxLayout()

        self.speed_icon = QLabel()
        self.speed_pixmap = QPixmap(self.get_absolute_path('Assets/speed.png'))
        self.speed_icon.setPixmap(self.speed_pixmap)
        self.speed_layout.addWidget(self.speed_icon)

        # Speed Slider
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setMinimum(-9)
        self.speed_slider.setMaximum(400)
        self.speed_slider.setSingleStep(1)
        self.speed_slider.setPageStep(1)
        self.speed_slider.setTickPosition(QSlider.TicksBelow)
        self.speed_slider.setToolTip('<font color="black">Change the speed of the drawing. The greater the speed, the less detailed the drawing will be</font>')
        self.speed_slider.sliderReleased.connect(lambda: self.sliderChange(self.speed_slider.value()))
        self.speed_slider.setStyleSheet("QSlider::groove:horizontal {height: 10px;border-radius: 5px;background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #bbb, stop:1 #ccc);}QSlider::handle:horizontal {width: 20px;margin: -8px 0 -8px 0;border-radius: 5px;background-color: #49c3ff;}QSlider::handle:horizontal:hover {background-color: #49b6ff;}QSlider::handle:horizontal:pressed {background-color: #49aaff;border-radius: 7px;}QSlider::groove:horizontal:pressed {background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b0b0b0, stop:1 #bbb);}")
        self.speed_layout.addWidget(self.speed_slider)

        self.layout.addLayout(self.speed_layout)
        
        # Start button
        self.start_button = QPushButton('Start Drawing', self)
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #80b275;
                color: white;
                border-radius: 8px;
                border: 2px solid #3a3a3a;
                padding: 10px 20px;
                margin-bottom: 6px;
            }
            
            /* Hover effect */
            QPushButton:hover {
                background-color: #76a65a; /* Slightly darker green */
            }
            
            /* Disabled state */
            QPushButton:disabled {
                background-color: #a5a5a5; /* Gray background */
                color: #6c6c6c; /* Darker gray text */
                border: 2px solid #9e9e9e; /* Light gray border */
            }
        """)
        self.start_button.clicked.connect(self.start_drawing)
        self.start_button.setToolTip('<font color="black">Ctrl + Shift + S</font>')

        self.layout.addWidget(self.start_button)

        self.estimate = QLabel('', self)
        self.estimate.setStyleSheet('font-size: 18px; background-color: transparent; color: gray')
        self.estimate.adjustSize()
        self.center_x(self.estimate)


        self.show() # show the gui
        self.crop_button.setGeometry(self.photoViewer.geometry().right() - 58, 30, 50, 50)
        self.preview_button.setGeometry(self.photoViewer.geometry().right() - 58, 85, 50, 50)
        self.estimate.move(self.estimate.pos().x(), self.start_button.pos().y() + round(self.start_button.height()) - 2)


    def center_x(self, element):
        # Calculate the center position
        window_width = self.width()
        label_width = element.width()
        center_x = (window_width - label_width) // 2

        # Move the label to the center position
        element.move(center_x, element.pos().y())

    def initClipboardMonitor(self):
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self.checkClipboard)

    def checkClipboard(self):
        clipboard_text = self.clipboard.text()
        if self.isValidURL(clipboard_text):
            self.fetch_image(clipboard_text)
        elif 'data:image/' in clipboard_text:
            try:
                base64_str = clipboard_text.split(',')[1]
                image_data = base64.b64decode(base64_str)
                image = QImage()
                image.loadFromData(image_data)
                pixmap = QPixmap.fromImage(image)
                self.fetch_image('', datapixmap=pixmap)
            except Exception as e:
                print(e)


    def isValidURL(self, url):
        return url.startswith('http://') or url.startswith('https://')
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasImage:
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasImage:
            event.setDropAction(Qt.CopyAction)
            file_path = event.mimeData().urls()[0].toLocalFile()
            self.dropped_image_path = file_path
            pixmap = QPixmap(file_path)
            self.fetch_image('None', datapixmap=pixmap)

    def fetch_image(self, url, datapixmap=None):
        try:
            if not datapixmap:
                response = requests.get(url)
                response.raise_for_status()
                image = QPixmap()
                image.loadFromData(response.content)
            else:
                image = datapixmap
            if image:
                scaled_pixmap = image.scaled(QSize(self.max_width, self.max_height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.photoViewer.setPixmap(scaled_pixmap)
                self.original_pixmap = scaled_pixmap
                if self.crop_button.isChecked():
                    crop = True
                else:
                    crop = False

                pixmap = self.photoViewer.pixmap()
                pixmap.save(self.draw_path, 'PNG')
                self.crop_button.show()
                self.preview_button.show()
            else:
                self.photoViewer.setText('Invalid Image URL')
            
            
            self.draw.start_draw(self.draw_path, self.speed, 'Paint', crop, True)

        except Exception as e:
            print(e)
            self.estimate.setText('')
            self.photoViewer.setText(f'Failed to fetch image')

    def updateImagePreview(self, toggled):
        if toggled:
            # Extract QPixmap from photoViewer
            pixmap = self.photoViewer.pixmap()
            if pixmap:
                # Convert QPixmap to QImage for painting
                image = pixmap.toImage()
                
                # Create a QPainter object for drawing on the image
                painter = QPainter(image)
                
                # Set up the brush for dimming
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(0, 0, 0, 128))  # Semi-transparent black
                
                # Define the rectangle to dim (bottom 20 pixels)
                rect = QRect(0, image.height() - 20, image.width(), 20)
                painter.drawRect(rect)
                
                # End the painting operation
                painter.end()
                
                # Convert QImage back to QPixmap for displaying
                self.photoViewer.setPixmap(QPixmap.fromImage(image))
        else:
            if self.preview_button.isChecked():
                path = self.preview_path
            else:
                path = self.draw_path
            pixmap = QPixmap()
            if pixmap.load(path):
                scaled_pixmap = pixmap.scaled(QSize(self.max_width, self.max_height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.photoViewer.setPixmap(scaled_pixmap)

    def crop_image(self):
        if not self.crop_button.isChecked():
            self.crop_button.setChecked(True)
        else:
            self.crop_button.setChecked(False)

    def start_drawing(self):
        if os.path.exists(self.draw_path):
            mode = self.get_selected_mode()
            
            if self.crop_button.isChecked():
                crop = True
            else:
                crop = False

            self.draw_thread = threading.Thread(target=self.draw.start_draw, args=(self.draw_path, self.speed, mode, crop, False))
            self.draw_thread.start()

        else:
            print('No image to draw')

    def canvas_not_detected(self):
       self.estimate.setStyleSheet('font-size: 18px; background-color: transparent; color: #e87347')
       self.estimate.setText('Drawing area not detected')
       self.estimate.adjustSize()
       self.center_x(self.estimate)

    def sliderChange(self, value):
        self.speed = value/1000

        if os.path.exists(self.draw_path):
            if self.crop_button.isChecked():
                crop = True
            else:
                crop = False
            self.draw.preview_signal.connect(self.show_preview_image)
            self.draw.data_signal.connect(self.estimate_time)
            self.draw.start_draw(self.draw_path, self.speed, 'Paint', crop, True)

    def estimate_time(self, data):
        self.estimate.setStyleSheet('font-size: 18px; background-color: transparent; color: gray')
        self.estimate.setText(f'Estimated time: {data} seconds')
        self.estimate.adjustSize()
        self.center_x(self.estimate)
        self.estimate.move(self.estimate.pos().x(), self.start_button.pos().y() + round(self.start_button.height()) - 2)

    def drawing_started(self):
        self.start_button.setDisabled(True)
        self.start_button.setText('Stop: Ctrl + Q')

    def drawing_stopped(self):
        self.start_button.setDisabled(False)
        self.start_button.setText('Start Drawing')
        

    def get_selected_mode(self):
        if self.scribble_button.isChecked():
            return 'Scribble'
        elif self.sketchful_button.isChecked():
            return 'Sketchful'
        elif self.paint_button.isChecked():
            return 'Paint'
        else:
            return None
        
    def toggle_radio_button(self):
        # Logic to toggle radio buttons
        if self.scribble_button.isChecked():
            self.sketchful_button.setChecked(True)
        elif self.sketchful_button.isChecked():
            self.paint_button.setChecked(True)
        else:
            self.scribble_button.setChecked(True)

    def show_preview_image(self, image):
        if image:
            pixmap = QPixmap.fromImage(image)
            pixmap.save(self.preview_path, 'PNG')
    
        if self.preview_button.isChecked():
            pixmap = QPixmap()
            if pixmap.load(self.preview_path):
                scaled_pixmap = pixmap.scaled(QSize(self.max_width, self.max_height), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.photoViewer.setPixmap(scaled_pixmap)
            else:
                return print(f"Failed to load image from {self.preview_path}")
        elif not image:
            pixmap = QPixmap()
            if pixmap.load(self.draw_path):
                self.photoViewer.setPixmap(pixmap)
            else:
                return print(f"Failed to load image from {self.preview_path}")

        if self.crop_button.isChecked():
            self.updateImagePreview(True) 

    def delete_file(self, file_path):
        try:
            # Check if the file exists
            if os.path.exists(file_path):
                os.remove(file_path)  # Remove the file
            else:
                print(f"File '{file_path}' does not exist.")
        except Exception as e:
            print(f"An error occurred while trying to delete the file: {e}")

    def get_absolute_path(self, file_name):
        script_dir = os.path.dirname(os.path.abspath(__file__))  # Absolute path of the script
        return os.path.join(script_dir, file_name)




if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    window = ImageDisplay()
    sys.exit(app.exec_())
