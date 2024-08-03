from PIL import Image, ImageGrab
import cv2
import numpy as np
import pyautogui
import keyboard

from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtGui import QImage

class Drawer(QThread):
    data_signal = pyqtSignal(str)  # Define a signal that sends a string
    preview_signal = pyqtSignal(QImage)
    drawing_started = pyqtSignal(str)
    drawing_stopped = pyqtSignal(str)
    canvas_not_detected = pyqtSignal(str)

    def __init__(self):
        super().__init__()


    def start_draw(self, file_path, speed, mode, crop, cancel):
        self.stop = False
        keyboard.add_hotkey('ctrl+q', lambda: self.stop_function())

        self.padding = 10

        if cancel == True:
            self.canvas_width = 1650
            self.canvas_height = 1230
            self.start_x = 517
            self.start_y = 595
        else:
            canvas = self.detect_canvas_area()

            self.canvas_width = canvas['width']
            self.canvas_height = canvas['height']
            self.start_x = canvas['start_x']
            self.start_y = canvas['start_y']

            if self.canvas_height <= 200 or self.canvas_width <= 200:
                return self.canvas_not_detected.emit('could not detect')
        # Load the image
        image = Image.open(file_path)

        if crop:
            crop_pixels = 20

            # Get the dimensions of the image
            width, height = image.size

            # Calculate the new height after cropping
            new_height = height - crop_pixels

            # Crop the image
            image = image.crop((0, 0, width, new_height))


        # Calculate the new size maintaining the aspect ratio
        aspect_ratio = image.width / image.height
        if (self.canvas_width - 2 * self.padding) / (self.canvas_height - 2 * self.padding) > aspect_ratio:
            new_height = self.canvas_height - 2 * self.padding
            new_width = int(new_height * aspect_ratio)
        else:
            new_width = self.canvas_width - 2 * self.padding
            new_height = int(new_width / aspect_ratio)

        # Resize the image
        resized_image = image.resize((new_width, new_height))

        # Calculate the starting coordinates to center the image
        centered_start_x = self.start_x + (self.canvas_width - new_width) // 2
        centered_start_y = self.start_y + (self.canvas_height - new_height) // 2

        # Convert the resized image to grayscale for edge detection
        resized_image_cv = np.array(resized_image)
        gray_image = cv2.cvtColor(resized_image_cv, cv2.COLOR_BGR2GRAY)

        # Apply edge detection using Canny
        edges = cv2.Canny(gray_image, threshold1=30, threshold2=100)

        # Find contours from the edges including inner details
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)


        def simplify_contour(contour):
            epsilon = self.dynamic_epsilon(contour, speed) * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            return approx

        # Function to reduce redundant points
        def reduce_redundant_points(contour, min_distance=5):
            filtered_points = [contour[0]]
            for point in contour[1:]:
                x, y = point[0]
                last_x, last_y = filtered_points[-1][0]
                if np.hypot(x - last_x, y - last_y) > min_distance:
                    filtered_points.append(point)
            return np.array(filtered_points)

        # Simplify and reduce redundant points for each contour
        simplified_contours = [simplify_contour(contour) for contour in contours]
        filtered_contours = [reduce_redundant_points(contour) for contour in simplified_contours]

        total_length = sum(cv2.arcLength(contour, False) for contour in filtered_contours)
        drawing_speed = 200  # pixels per second (adjust based on your system performance)

        estimated_time = total_length / drawing_speed

        self.data_signal.emit(f'{round(estimated_time)}')

        preview_image = self.generate_preview_image(filtered_contours, self.canvas_width, self.canvas_height, speed)

        # Emit the preview image
        self.preview_signal.emit(preview_image)


        if cancel == True:
            return

        # Draw the simplified contours using pyautogui
        self.drawing_started.emit('started')
        for contour in filtered_contours:
            if len(contour) < 2:
                    continue
            x, y = contour[0][0]
            pyautogui.moveTo(centered_start_x + x, centered_start_y + y)
            if mode != 'Sketchful' and mode != 'Scribble':
                for point in contour[1:]:
                    x, y = point[0]
                    pyautogui.dragTo(centered_start_x + x, centered_start_y + y, button='left')
            else:
                pyautogui.mouseDown()  # Start drawing
                for point in contour[1:]:
                    x, y = point[0]
                    pyautogui.moveTo(centered_start_x + x, centered_start_y + y)
                # End drawing
                pyautogui.mouseUp()

            if self.stop == True:
                return
        self.drawing_stopped.emit('stopped')

        # Function to simplify contours with dynamic epsilon
    def dynamic_epsilon(self, contour, speed):
        # Estimate curvature: if contour is more circular, use a larger epsilon
        if len(contour) > 30:  # Arbitrary threshold; adjust based on your data
            return 0.01 + speed  # Larger epsilon for smoother curves
        else:
            return 0.025 + speed # Smaller epsilon for more detailed contours

    def generate_preview_image(self, contours, canvas_width, canvas_height, speed):
        # Create a blank white image
        preview_image = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255

        # Draw each contour
        for contour in contours:
            # Calculate epsilon using dynamic_epsilon function
            epsilon_value = self.dynamic_epsilon(contour, speed) * cv2.arcLength(contour, True)
            approx_contour = cv2.approxPolyDP(contour, epsilon_value, True)

            # Draw lines connecting the points in the approximated contour
            if len(approx_contour) > 1:
                for i in range(len(approx_contour) - 1):
                    pt1 = tuple(approx_contour[i][0])
                    pt2 = tuple(approx_contour[i + 1][0])
                    cv2.line(preview_image, pt1, pt2, (0, 0, 0), 1)  # Draw line with 1 pixel thickness

            # Optionally, draw a closed contour (loop) if the contour is closed
            if len(approx_contour) > 1 and np.array_equal(approx_contour[0], approx_contour[-1]):
                pt1 = tuple(approx_contour[-1][0])
                pt2 = tuple(approx_contour[0][0])
                cv2.line(preview_image, pt1, pt2, (0, 0, 0), 1)  # Draw line with 1 pixel thickness

        # Convert numpy array to QImage
        return QImage(preview_image.data, preview_image.shape[1], preview_image.shape[0], preview_image.strides[0], QImage.Format_RGB888)

    def detect_canvas_area(self):
        # Capture the screenshot
        screen = ImageGrab.grab()
        
        # Convert the image to a format suitable for OpenCV
        open_cv_image = np.array(screen)
        
        # Convert the image to grayscale
        gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
        
        # Get the center of the image
        height, width = gray.shape
        center_x, center_y = width // 2, height // 2
        
        # Initialize measurements
        left, right, top, bottom = 0, 0, 0, 0
        
        # Measure white area extent from the center
        for x in range(center_x, width):
            if gray[center_y, x] < 240:  # Assuming white is near 255 in grayscale
                right = x - center_x
                break
        
        for x in range(center_x, -1, -1):
            if gray[center_y, x] < 240:
                left = center_x - x
                break
        
        for y in range(center_y, height):
            if gray[y, center_x] < 240:
                bottom = y - center_y
                break
        
        for y in range(center_y, -1, -1):
            if gray[y, center_x] < 240:
                top = center_y - y
                break
        
        # Calculate width and height of the detected canvas
        canvas_width = left + right
        canvas_height = top + bottom
        
        # Define the starting point of the canvas
        start_x = center_x - left
        start_y = center_y - top
        
        # Draw a rectangle on the image to visualize the canvas
        canvas_image = open_cv_image.copy()
        cv2.rectangle(canvas_image, (start_x, start_y), (start_x + canvas_width, start_y + canvas_height), (0, 255, 0), 2)
        

        # Return the properties of the detected canvas
        return {
            'width': canvas_width,
            'height': canvas_height,
            'start_x': start_x,
            'start_y': start_y,
            'canvas_image': canvas_image
        }


    def stop_function(self):
        self.stop = True
        self.drawing_stopped.emit('stopped')

