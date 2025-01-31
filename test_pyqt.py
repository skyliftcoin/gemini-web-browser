import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel

def main():
    print("Creating application...")
    app = QApplication(sys.argv)
    print("Application created")
    
    print("Creating window...")
    window = QMainWindow()
    print("Window created")
    
    print("Creating label...")
    label = QLabel("Hello, PyQt6!")
    print("Label created")
    
    window.setCentralWidget(label)
    window.show()
    
    print("Running application...")
    return app.exec()
