from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QPixmap, QPainterPath
from PyQt6.QtCore import QObject, QEvent, Qt

class BackgroundScaler(QObject):
    def __init__(self, target_widget: QWidget, image_path: str, opacity: float=0.15, corner_radius: int=0, halign_center: bool=False):
        super().__init__(target_widget)
        self.target = target_widget
        self.bg_pixmap = QPixmap(image_path)
        self.opacity = opacity
        self.corner_radius = corner_radius
        self.halign_center = halign_center
        
        # Install this object as an event filter on the existing widget
        self.target.installEventFilter(self)
        
        ## repaint the target
        self.target.update()

    def eventFilter(self, watched, event):
        if watched == self.target and event.type() == QEvent.Type.Paint:
            if not self.bg_pixmap.isNull():
                painter = QPainter(self.target)
                
                if self.corner_radius > 0:
                    ## Turn on Antialiasing so the rounded edges are smooth, not jagged
                    #painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    
                    ## Create a clipping mask with rounded corners matching the widget dimensions
                    path = QPainterPath()
                    ## Create a rounded rect matching the widget's current bounding rectangle
                    path.addRoundedRect(
                        0, 0, 
                        float(self.target.width()), float(self.target.height()), 
                        float(self.corner_radius), float(self.corner_radius)
                    )
                    painter.setClipPath(path)
                
                if self.opacity < 1 and self.opacity > 0:
                    ## Apply the transparency layer
                    painter.setOpacity(self.opacity)
                
                ## Scale the image to match the current widget width
                scaled_pixmap = self.bg_pixmap.scaledToWidth(
                    self.target.width(), 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                if self.halign_center == True:
                    ## Calculate the vertical offset to center the image
                    ## (Widget Height - Scaled Image Height) / 2
                    #x_offset = int((self.target.width() - scaled_pixmap.width()) / 2)
                    x_offset = 0
                    y_offset = int((self.target.height() - scaled_pixmap.height()) / 2)
                else:
                    x_offset = 0
                    y_offset = 0
                    ## Draw the pixmap starting from X=0, Y=y_offset to center vertically
                    painter.drawPixmap(x_offset, y_offset, scaled_pixmap)
                    painter.end()
                
        # Return False to let the target widget paint its own text/buttons over the image
        return False