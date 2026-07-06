"""History viewer interface"""

# Use the modern Fluent Design viewer with QMainWindow
from .history_viewer_modern import ModernHistoryViewer as HistoryViewer
from .filters import HistoryFilter, CATEGORY_LABELS, CATEGORY_LABEL_TO_INTERNAL, FAVORITES_LABEL
from .formatters import HistoryItemFormatter

__all__ = [
    'HistoryViewer',
    'HistoryFilter',
    'HistoryItemFormatter',
    'CATEGORY_LABELS',
    'CATEGORY_LABEL_TO_INTERNAL',
    'FAVORITES_LABEL',
]