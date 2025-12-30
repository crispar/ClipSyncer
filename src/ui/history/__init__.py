"""History viewer interface"""

# Use the modern Fluent Design viewer with QMainWindow
from .history_viewer_modern import ModernHistoryViewer as HistoryViewer

__all__ = ['HistoryViewer']