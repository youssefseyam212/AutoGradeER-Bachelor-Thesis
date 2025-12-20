#!/usr/bin/env python3
"""
Quick script to fix XML files with unescaped HTML entities in attribute values.
Usage: python fix_xml.py <input_file> [output_file]
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from convertion import convert_txt_to_xml, fix_xml_entities
import xml.etree.ElementTree as ET
from xml.dom import minidom

def fix_existing_xml(input_file, output_file=None):
    """
    Fixes an existing XML file by escaping HTML entities in attribute values.
    """
    if not output_file:
        # Create output filename by adding _fixed before extension
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_fixed{ext}"

    print(f"Reading: {input_file}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Remove BOM if present
            if content.startswith('\ufeff'):
                content = content[1:]

        print("Fixing HTML entities in attribute values...")
        # Fix HTML entities in attribute values
        fixed_content = fix_xml_entities(content)

        print("Validating XML...")
        # Parse and validate the XML
        root = ET.fromstring(fixed_content)

        print("Formatting XML...")
        # Write the properly formatted XML
        xml_str = ET.tostring(root, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')

        # Remove extra blank lines
        pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)

        print(f"✓ Successfully fixed XML!")
        print(f"✓ Output saved to: {output_file}")
        return output_file

    except Exception as e:
        print(f"✗ Error fixing XML: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_xml.py <input_file> [output_file]")
        print("\nExample:")
        print("  python fix_xml.py Database1_converted_raw.xml")
        print("  python fix_xml.py Database1_converted_raw.xml Database1_fixed.xml")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found!")
        sys.exit(1)

    # Detect file type
    file_ext = os.path.splitext(input_file)[1].lower()

    if file_ext == '.txt':
        print("Detected .txt file - using txt-to-xml conversion...")
        if not output_file:
            output_file = input_file.replace('.txt', '_fixed.xml')
        convert_txt_to_xml(input_file, output_file)
    else:
        print("Detected .xml file - fixing in place...")
        fix_existing_xml(input_file, output_file)
