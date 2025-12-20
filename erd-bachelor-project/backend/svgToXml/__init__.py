# svgToXml package
"""
SVG to ERD conversion and parsing utilities.
"""

from .convertion import svg_to_drawio_erd
from .test import ERDParser

__all__ = ['svg_to_drawio_erd', 'ERDParser']
