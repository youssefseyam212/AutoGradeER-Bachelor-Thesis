import xml.etree.ElementTree as ET
from xml.dom import minidom
import base64
import zlib
import urllib.parse
import html
import re

def fix_xml_entities(xml_string):
    """
    Fixes XML by ensuring HTML tags inside attribute values are properly escaped.
    This prevents XML parsing errors when attributes contain HTML like <u>text</u>
    or <font style="...">text</font> with nested quotes.
    """
    result = []
    i = 0

    while i < len(xml_string):
        # Look for value=" pattern
        if xml_string[i:i+7] == 'value="':
            result.append('value="')
            i += 7

            # Now parse the attribute value content until we find the closing quote
            # We need to handle HTML tags with their own quoted attributes
            in_html_tag = False
            value_chars = []

            while i < len(xml_string):
                char = xml_string[i]

                if char == '<' and not in_html_tag:
                    # Entering an HTML tag
                    in_html_tag = True
                    value_chars.append('&lt;')
                    i += 1
                elif char == '>' and in_html_tag:
                    # Exiting an HTML tag
                    in_html_tag = False
                    value_chars.append('&gt;')
                    i += 1
                elif char == '"' and not in_html_tag:
                    # This is the closing quote of the XML value attribute
                    result.append(''.join(value_chars))
                    result.append('"')
                    i += 1
                    break
                elif char == '<':
                    # Already in HTML tag, still escape
                    value_chars.append('&lt;')
                    i += 1
                elif char == '>':
                    # Shouldn't happen but handle it
                    value_chars.append('&gt;')
                    i += 1
                else:
                    # Regular character or quote inside HTML tag
                    value_chars.append(char)
                    i += 1
            else:
                # Reached end without finding closing quote - shouldn't happen but handle it
                result.append(''.join(value_chars))
        else:
            result.append(xml_string[i])
            i += 1

    return ''.join(result)

def convert_txt_to_xml(txt_file_path, output_file_path):
    """
    Converts a .txt file (raw XML content) to properly formatted and escaped XML.
    This fixes any HTML entity issues in the process.
    """
    try:
        with open(txt_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            # Remove BOM if present
            if content.startswith('\ufeff'):
                content = content[1:]

        # Fix HTML entities in attribute values
        fixed_content = fix_xml_entities(content)

        # Parse and validate the XML
        root = ET.fromstring(fixed_content)

        # Write the properly formatted XML
        xml_str = ET.tostring(root, encoding='utf-8')
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent='  ')

        # Remove extra blank lines
        pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])

        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write(pretty_xml)

        print(f"✓ Successfully converted {txt_file_path} to {output_file_path}")
        print(f"✓ HTML entities properly escaped")
        return output_file_path

    except Exception as e:
        print(f"Error converting .txt to .xml: {e}")
        import traceback
        traceback.print_exc()
        return None

def svg_to_drawio_erd(svg_file_path, output_file_path):
    """
    Converts a Draw.io exported SVG file back to Draw.io XML format.
    This version handles SVG files that have embedded Draw.io data in the 'content' attribute.
    """
    tree = ET.parse(svg_file_path)
    root = tree.getroot()
    
    # Check if there's a 'content' attribute in the SVG root
    content_attr = root.get('content')
    
    if content_attr:
        print("Found embedded Draw.io content in SVG")

        # The content is URL-encoded and possibly compressed
        # First, URL decode it
        decoded_content = urllib.parse.unquote(content_attr)

        # Replace only safe HTML entities (not < and > in attribute values)
        # Only replace newlines and quotes that are safe to replace
        decoded_content = decoded_content.replace('&#10;', '\n')

        # Fix any unescaped HTML tags in attribute values
        decoded_content = fix_xml_entities(decoded_content)

        try:
            # Try to parse as XML directly
            embedded_root = ET.fromstring(decoded_content)
            
            # Write the embedded content to the output file
            xml_str = ET.tostring(embedded_root, encoding='utf-8')
            dom = minidom.parseString(xml_str)
            pretty_xml = dom.toprettyxml(indent='  ')
            
            # Remove extra blank lines
            pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(pretty_xml)
            
            print(f"Successfully extracted Draw.io content!")
            print(f"Output saved to: {output_file_path}")
            return output_file_path
            
        except ET.ParseError as e:
            print(f"Failed to parse embedded content as XML: {e}")
            print("The content might be compressed or in a different format.")
            
            # Try to handle compressed content (some Draw.io exports use deflate)
            try:
                # Try base64 decoding first
                try:
                    compressed_data = base64.b64decode(content_attr)
                    decompressed = zlib.decompress(compressed_data, -zlib.MAX_WBITS)
                    decompressed_str = decompressed.decode('utf-8')
                    
                    embedded_root = ET.fromstring(decompressed_str)
                    xml_str = ET.tostring(embedded_root, encoding='utf-8')
                    dom = minidom.parseString(xml_str)
                    pretty_xml = dom.toprettyxml(indent='  ')
                    pretty_xml = '\n'.join([line for line in pretty_xml.split('\n') if line.strip()])
                    
                    with open(output_file_path, 'w', encoding='utf-8') as f:
                        f.write(pretty_xml)
                    
                    print(f"Successfully extracted compressed Draw.io content!")
                    print(f"Output saved to: {output_file_path}")
                    return output_file_path
                    
                except Exception as base64_err:
                    print(f"Base64/compression attempt failed: {base64_err}")
                    
            except Exception as comp_err:
                print(f"Compression handling failed: {comp_err}")
            
            # Last resort: save the raw decoded content for inspection
            print("\nSaving raw decoded content for inspection...")
            raw_output = output_file_path.replace('.xml', '_raw.txt')
            with open(raw_output, 'w', encoding='utf-8') as f:
                f.write(decoded_content)
            print(f"Raw content saved to: {raw_output}")
            
    else:
        print("No embedded Draw.io content found in SVG 'content' attribute")
        print("This SVG might be a plain export without embedded Draw.io data")
        return None

def extract_from_svg(svg_file_path, output_file_path):
    """
    Main extraction function with better error handling
    """
    try:
        result = svg_to_drawio_erd(svg_file_path, output_file_path)
        
        if result:
            print("\n" + "="*60)
            print("✓ Conversion successful!")
            print("="*60)
            return result
        else:
            print("\n" + "="*60)
            print("✗ Could not extract Draw.io content")
            print("="*60)
            return None
            
    except Exception as e:
        print(f"Error during conversion: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    import sys
    import os
    
    # You can modify these paths
    svg_input_file = "erd-bachelor-project/frontend/imageSvg/Database1.drawio.svg"
    xml_output_file = "test.output.xml"
    
    if not os.path.exists(svg_input_file):
        print(f"Error: SVG file '{svg_input_file}' not found!")
        exit(1)
    
    extract_from_svg(svg_input_file, xml_output_file)