"""Thin P3-WP04 desktop viewer and validated experiment editor.

Qt imports stay in GUI modules so non-GUI BioMesh processes do not load Qt's
bundled graphics libraries. Editor draft state is separate from immutable
validated biological-parameter documents.
"""

from __future__ import annotations

import os

# BioMesh supports PySide6 explicitly. Pin pyqtgraph's binding choice before
# either library loads so an unrelated PyQt installation cannot mix Qt ABIs.
os.environ["PYQTGRAPH_QT_LIB"] = "PySide6"
