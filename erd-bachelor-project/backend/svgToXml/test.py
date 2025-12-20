import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import re
import html
import sys
import os

@dataclass
class Attribute:
    name: str
    x: float
    y: float
    cell_id: str
    type: str = "simple"

@dataclass
class Entity:
    name: str
    x: float
    y: float
    width: float
    height: float
    attributes: List[Attribute]
    cell_id: str
    is_weak: bool = False
    is_associative: bool = False

@dataclass
class Relationship:
    name: str
    x: float
    y: float
    width: float
    height: float
    cell_id: str
    is_identifying: bool = False
    attributes: List[Attribute] = field(default_factory=list)

@dataclass
class Connection:
    source: str
    target: str
    label: str
    cardinality: str = ""

@dataclass
class Inheritance:
    """Represents an inheritance/specialization relationship (ISA hierarchy)"""
    inheritance_type: str  # "disjoint", "union", "overlapping"
    parent_entity: str  # Name of the parent/supertype entity
    parent_id: str  # Cell ID of the parent entity
    child_entities: List[Dict[str, str]]  # List of child/subtype entities with their IDs
    cell_id: str  # Cell ID of the inheritance node itself
    x: float
    y: float

    def get_type_symbol(self):
        """Returns the symbol representation (d, U, o)"""
        symbols = {
            "disjoint": "d",
            "union": "U",
            "overlapping": "o"
        }
        return symbols.get(self.inheritance_type, "?")

class ERDParser:
    def __init__(self, xml_content):
        self.root = ET.fromstring(xml_content)
        self.entities = []
        self.relationships = []
        self.attributes = []
        self.connections = []
        self.inheritances = []  # Store inheritance/specialization relationships
        self.cell_map = {}
        self.inheritance_nodes = {}  # Map of inheritance node IDs to their types
        self.edge_labels = {}  # Map of edge IDs to their label text (for cardinalities)

    def _clean_value(self, value):
        """
        Cleans HTML tags and entities from a cell value.
        Returns a tuple: (cleaned_text, is_key)
        """
        # Check for key attribute tag *before* stripping
        is_key = '<u>' in value
        
        # Decode HTML entities like &nbsp;
        value = html.unescape(value)
        
        # Remove all HTML tags
        value = re.sub(r'<[^>]+>', '', value)
        
        return value.strip(), is_key

    def parse(self):
        # First pass: collect all edge IDs so we can identify edge labels in second pass
        edge_ids = set()
        for cell in self.root.findall('.//mxCell'):
            if cell.get('edge') == '1':
                cell_id = cell.get('id')
                if cell_id:
                    edge_ids.add(cell_id)

        # Second pass: collect edge labels (cells with parent pointing to an actual edge)
        for cell in self.root.findall('.//mxCell'):
            parent = cell.get('parent')
            value = cell.get('value', '')
            vertex = cell.get('vertex')
            edge = cell.get('edge')

            # Check if this is a label for an edge (has parent that is an actual edge, is a vertex itself)
            if parent and parent in edge_ids and vertex == '1' and value and not edge:
                cleaned_value, _ = self._clean_value(value)
                # Store edge label
                if parent not in self.edge_labels:
                    self.edge_labels[parent] = []
                self.edge_labels[parent].append(cleaned_value)

        # Third pass: process all cells normally (entities, relationships, attributes)
        for cell in self.root.findall('.//mxCell'):
            cell_id = cell.get('id')
            value = cell.get('value', '')
            style = cell.get('style', '')
            vertex = cell.get('vertex')
            edge = cell.get('edge')
            parent = cell.get('parent')

            geometry = cell.find('mxGeometry')
            if geometry is not None:
                x = float(geometry.get('x', 0))
                y = float(geometry.get('y', 0))
                width = float(geometry.get('width', 0))
                height = float(geometry.get('height', 0))

                cell_data = {
                    'id': cell_id,
                    'value': value, # Store raw value for cell_map
                    'style': style,
                    'x': x,
                    'y': y,
                    'width': width,
                    'height': height,
                    'vertex': vertex,
                    'edge': edge,
                    'source': cell.get('source'),
                    'target': cell.get('target')
                }
                
                # Clean the value for processing
                cleaned_value, is_key_from_tag = self._clean_value(value)
                # Store cleaned value in cell_data for later lookups
                cell_data['cleaned_value'] = cleaned_value
                
                self.cell_map[cell_id] = cell_data

                if vertex == '1' and cleaned_value:
                    # Skip cells that are edge labels (they have a parent that is an edge and the value matches a stored label)
                    if parent and parent in self.edge_labels and cleaned_value in self.edge_labels.get(parent, []):
                        continue
                    # Check for key attribute status (tag or style)
                    is_key_attribute = is_key_from_tag or 'fontStyle=4' in style

                    # Also detect common ID naming patterns as primary keys
                    # Common patterns: id, ID, *_id, *_ID, *ID, *_key, identifier
                    if not is_key_attribute:
                        cleaned_lower = cleaned_value.lower()
                        # Exact matches
                        if cleaned_lower in ['id', 'identifier']:
                            is_key_attribute = True
                        # Suffix patterns
                        elif cleaned_lower.endswith('_id') or cleaned_lower.endswith('_key') or cleaned_lower.endswith('id'):
                            is_key_attribute = True

                    if 'shape=rhombus' in style or 'rhombus' in style.lower():
                        is_identifying = 'double=1' in style
                        self.relationships.append(Relationship(cleaned_value, x, y, width, height, cell_id, is_identifying))

                    elif 'ellipse' in style.lower():
                        # Check if this is an inheritance node (d, U, o)
                        if cleaned_value in ['d', 'U', 'o'] and 'aspect=fixed' in style:
                            inheritance_type_map = {
                                'd': 'disjoint',
                                'U': 'union',
                                'o': 'overlapping'
                            }
                            self.inheritance_nodes[cell_id] = {
                                'type': inheritance_type_map[cleaned_value],
                                'symbol': cleaned_value,
                                'x': x,
                                'y': y,
                                'cell_id': cell_id
                            }
                        else:
                            # Regular attribute
                            attr_type = "simple"

                            if 'doubleEllipse' in style or 'shape=doubleEllipse' in style:
                                attr_type = "multivalued"
                            elif 'dashed=1' in style:
                                attr_type = "derived"

                            # Use the combined key check
                            if is_key_attribute:
                                attr_type = "key"

                            self.attributes.append(Attribute(cleaned_value, x, y, cell_id, attr_type))

                    elif 'shape=ext' in style and 'double=1' in style:
                        self.entities.append(Entity(cleaned_value, x, y, width, height, [], cell_id, is_weak=True))

                    elif 'shape=associativeEntity' in style:
                        self.entities.append(Entity(cleaned_value, x, y, width, height, [], cell_id, is_weak=False, is_associative=True))

                    elif 'whiteSpace=wrap' in style or ('html=1' in style and 'align=center' in style and 'ellipse' not in style.lower() and 'rhombus' not in style.lower()):
                        self.entities.append(Entity(cleaned_value, x, y, width, height, [], cell_id))

            if edge == '1':
                source = cell.get('source')
                target = cell.get('target')
                if source and target:
                    # Extract cardinalities from BOTH ends of the edge
                    source_card, target_card = self._extract_both_cardinalities(style, cell_id, value)

                    # Format as "source:target" if we have both, otherwise use what we have
                    if source_card and target_card:
                        cardinality = f"{source_card}:{target_card}"
                        cardinality_label = cardinality
                    elif target_card:
                        cardinality = target_card
                        cardinality_label = target_card
                    elif source_card:
                        cardinality = source_card
                        cardinality_label = source_card
                    else:
                        # Fallback to old method
                        cardinality_label, _ = self._clean_value(value)
                        if not cardinality_label and cell_id in self.edge_labels:
                            edge_label_texts = self.edge_labels[cell_id]
                            if edge_label_texts:
                                cardinality_label = ':'.join(edge_label_texts[:2]) if len(edge_label_texts) >= 2 else edge_label_texts[0]
                        cardinality = self._extract_cardinality(style, cardinality_label)

                    self.connections.append(Connection(source, target, cardinality_label, cardinality))

        self._associate_attributes_via_connections()
        self._process_inheritance_relationships()

    def _extract_both_cardinalities(self, style, edge_id, edge_value):
        """
        Extract cardinalities from BOTH ends of an edge.
        Returns (source_cardinality, target_cardinality)

        Combines information from:
        1. Visual symbols (startArrow, endArrow in style)
        2. Text labels (edge labels stored in self.edge_labels)
        """
        source_card = None
        target_card = None

        # Extract from visual symbols in style
        # Source end (startArrow) - check longer patterns first to avoid false matches
        if 'startArrow=ERoneToMany' in style:
            source_card = '1..*'
        elif 'startArrow=ERzeroToMany' in style:
            source_card = '0..*'
        elif 'startArrow=ERzeroToOne' in style:
            source_card = '0..1'
        elif 'startArrow=ERmandOne' in style or 'startArrow=ERone' in style:
            source_card = '1'
        elif 'startArrow=ERmany' in style:
            source_card = '*'

        # Target end (endArrow) - check longer patterns first to avoid false matches
        if 'endArrow=ERoneToMany' in style:
            target_card = '1..*'
        elif 'endArrow=ERzeroToMany' in style:
            target_card = '0..*'
        elif 'endArrow=ERzeroToOne' in style:
            target_card = '0..1'
        elif 'endArrow=ERmandOne' in style or 'endArrow=ERone' in style:
            target_card = '1'
        elif 'endArrow=ERmany' in style:
            target_card = '*'

        # Extract from text labels (if available)
        text_labels = []

        # Check edge's own value
        if edge_value:
            label, _ = self._clean_value(edge_value)
            if label:
                text_labels.append(label)

        # Check child text labels
        if edge_id in self.edge_labels:
            text_labels.extend(self.edge_labels[edge_id])

        # Process text labels - normalize them
        normalized_labels = []
        for label in text_labels:
            normalized = self._normalize_cardinality_text(label.strip().upper())
            if normalized:
                normalized_labels.append(normalized)
            elif label.strip():  # Keep original if not normalized
                normalized_labels.append(label.strip())

        # If we have text labels, prefer them over visual symbols (text is more explicit)
        if normalized_labels:
            if len(normalized_labels) >= 2:
                # Two labels: assume first is source, second is target
                source_card = normalized_labels[0]
                target_card = normalized_labels[1]
            elif len(normalized_labels) == 1:
                # One label: use for target end (most common convention)
                if not target_card:  # Only if we didn't get it from visual symbol
                    target_card = normalized_labels[0]

        return (source_card, target_card)

    def _extract_cardinality(self, style, label):
        cardinality_map = {
            'ERmandOne': '1',
            'ERone': '1',
            'ERzeroToOne': '0..1',
            'ERmany': '*',
            'ERzeroToMany': '0..*',
            'ERoneToMany': '1..*',
        }

        for key, value in cardinality_map.items():
            if key in style:
                return value

        # Check endArrow for simple cardinalities
        if 'endArrow=ERone' in style: return '1'
        if 'endArrow=ERmany' in style: return '*'
        if 'endArrow=ERoneToMany' in style: return '1..*'
        if 'endArrow=ERzeroToOne' in style: return '0..1'
        if 'endArrow=ERzeroToMany' in style: return '0..*'

        # Check if label is a direct cardinality value
        if label:
            label = label.strip()
            label_upper = label.upper()

            # Handle "X:Y" format (e.g., "1:M", "M:N", "one:Many")
            if ':' in label:
                parts = label.split(':')
                if len(parts) == 2:
                    left = parts[0].strip().upper()
                    right = parts[1].strip().upper()

                    # Normalize text cardinalities to symbols
                    left = self._normalize_cardinality_text(left)
                    right = self._normalize_cardinality_text(right)

                    return f"{left}:{right}"

            # Single cardinality value - check for text labels like "one", "Many", "E O"
            normalized = self._normalize_cardinality_text(label_upper)
            if normalized:
                return normalized

            # Fallback: exact match patterns
            if label in ['M', 'N', '1', '0..1', '0..*', '1..*', '*', 'm', 'n']:
                # Normalize M/N to standard notation
                if label.upper() in ['M', 'N']:
                    return '*'  # M and N typically mean "many"
                return label

        return ""

    def _normalize_cardinality_text(self, text):
        """
        Normalize text-based cardinality labels to standard notation.
        Handles cases like: "one", "Many", "E O" (Exactly One), etc.
        """
        if not text:
            return None

        text = text.strip().upper()

        # Map text variations to standard cardinality
        text_to_cardinality = {
            # "One" variations
            'ONE': '1',
            'E O': '1',  # Exactly One
            'EO': '1',
            'EXACTLY ONE': '1',
            '1': '1',

            # "Many" variations
            'MANY': '*',
            'M': '*',
            'N': '*',
            '*': '*',
            'MULTIPLE': '*',

            # Other standard notations
            '0..1': '0..1',
            '0..*': '0..*',
            '1..*': '1..*',
        }

        return text_to_cardinality.get(text, None)

    def _associate_attributes_via_connections(self):
        for connection in self.connections:
            source_id = connection.source
            target_id = connection.target

            source_cell = self.cell_map.get(source_id)
            target_cell = self.cell_map.get(target_id)

            if source_cell and target_cell:
                source_is_attr = any(attr.cell_id == source_id for attr in self.attributes)
                target_is_entity = any(entity.cell_id == target_id for entity in self.entities)
                target_is_relationship = any(rel.cell_id == target_id for rel in self.relationships)

                if source_is_attr and (target_is_entity or target_is_relationship):
                    attribute = next((attr for attr in self.attributes if attr.cell_id == source_id), None)
                    if not attribute: continue
                    
                    if target_is_entity:
                        entity = next(entity for entity in self.entities if entity.cell_id == target_id)
                        if attribute not in entity.attributes:
                            entity.attributes.append(attribute)
                    elif target_is_relationship:
                        relationship = next(rel for rel in self.relationships if rel.cell_id == target_id)
                        if attribute not in relationship.attributes:
                            relationship.attributes.append(attribute)

                target_is_attr = any(attr.cell_id == target_id for attr in self.attributes)
                source_is_entity = any(entity.cell_id == source_id for entity in self.entities)
                source_is_relationship = any(rel.cell_id == source_id for rel in self.relationships)

                if target_is_attr and (source_is_entity or source_is_relationship):
                    attribute = next((attr for attr in self.attributes if attr.cell_id == target_id), None)
                    if not attribute: continue
                    
                    if source_is_entity:
                        entity = next(entity for entity in self.entities if entity.cell_id == source_id)
                        if attribute not in entity.attributes:
                            entity.attributes.append(attribute)
                    elif source_is_relationship:
                        relationship = next(rel for rel in self.relationships if rel.cell_id == source_id)
                        if attribute not in relationship.attributes:
                            relationship.attributes.append(attribute)

    def _process_inheritance_relationships(self):
        """Process inheritance/specialization nodes (d, U, o) and create Inheritance objects"""
        for inh_id, inh_data in self.inheritance_nodes.items():
            parent_entity = None
            parent_entity_id = None
            child_entities = []

            # Find connections related to this inheritance node
            for connection in self.connections:
                # Parent entity connects TO the inheritance node
                if connection.target == inh_id:
                    parent_cell = self.cell_map.get(connection.source)
                    if parent_cell:
                        entity = next((e for e in self.entities if e.cell_id == connection.source), None)
                        if entity:
                            parent_entity = entity.name
                            parent_entity_id = entity.cell_id

                # Child entities are connected FROM the inheritance node
                elif connection.source == inh_id:
                    child_cell = self.cell_map.get(connection.target)
                    if child_cell:
                        entity = next((e for e in self.entities if e.cell_id == connection.target), None)
                        if entity:
                            child_entities.append({
                                'name': entity.name,
                                'id': entity.cell_id
                            })

            if parent_entity and child_entities:
                inheritance = Inheritance(
                    inheritance_type=inh_data['type'],
                    parent_entity=parent_entity,
                    parent_id=parent_entity_id,
                    child_entities=child_entities,
                    cell_id=inh_data['cell_id'],
                    x=inh_data['x'],
                    y=inh_data['y']
                )
                self.inheritances.append(inheritance)

    def generate_erd_description(self):
        description = "## Entity-Relationship Diagram (ERD)\n\n"

        description += "### 1. Entities\n\n"
        for entity in self.entities:
            entity_type = ""
            if entity.is_weak:
                entity_type = " (Weak Entity)"
            elif entity.is_associative:
                entity_type = " (Associative Entity)"

            description += f"* **{entity.name}**{entity_type}\n"
            if entity.attributes:
                description += "  * **Attributes:**\n"
                # Sort attributes to put key first
                sorted_attrs = sorted(entity.attributes, key=lambda a: (a.type != 'key', a.name))
                for attr in sorted_attrs:
                    attr_info = f"`{attr.name}`"
                    if attr.type == "key":
                        attr_info += " **[PRIMARY KEY]**"
                    elif attr.type == "multivalued":
                        attr_info += " (Multivalued)"
                    elif attr.type == "derived":
                        attr_info += " (Derived)"
                    elif attr.type == "composite":
                        attr_info += " (Composite)"
                    description += f"    * {attr_info}\n"
            description += "\n"

        if self.relationships:
            description += "### 2. Relationships\n\n"
            for rel in self.relationships:
                rel_type = " (Identifying)" if rel.is_identifying else ""
                description += f"* **{rel.name}**{rel_type}\n"

                connected_entities = []
                for conn in self.connections:
                    if conn.source == rel.cell_id:
                        target_cell = self.cell_map.get(conn.target)
                        if target_cell and any(e.cell_id == conn.target for e in self.entities):
                            cardinality = f" [{conn.cardinality}]" if conn.cardinality else ""
                            connected_entities.append(f"{target_cell.get('cleaned_value', '')}{cardinality}")
                    elif conn.target == rel.cell_id:
                        source_cell = self.cell_map.get(conn.source)
                        if source_cell and any(e.cell_id == conn.source for e in self.entities):
                            cardinality = f" [{conn.cardinality}]" if conn.cardinality else ""
                            connected_entities.append(f"{source_cell.get('cleaned_value', '')}{cardinality}")

                if connected_entities:
                    description += f"  * **Connects:** {' - '.join(connected_entities)}\n"

                if rel.attributes:
                    description += "  * **Attributes:**\n"
                    for attr in rel.attributes:
                        attr_info = f"`{attr.name}`"
                        if attr.type == "key":
                            attr_info += " **[PRIMARY KEY]**"
                        description += f"    * {attr_info}\n"
                description += "\n"

        if self.inheritances:
            description += "### 3. Inheritance/Specialization (ISA Hierarchies)\n\n"
            for inh in self.inheritances:
                type_descriptions = {
                    "disjoint": "Disjoint (XOR)",
                    "union": "Union (Total)",
                    "overlapping": "Overlapping (OR)"
                }
                type_desc = type_descriptions.get(inh.inheritance_type, inh.inheritance_type)

                child_names = ', '.join([f"`{child['name']}`" for child in inh.child_entities])

                description += f"* **{inh.parent_entity}** → [{inh.get_type_symbol()}] ({type_desc})\n"
                description += f"  * **Subtypes:** {child_names}\n"
                description += "\n"

        # Optional: Hide this section as it's very noisy and redundant
        # description += "### 4. All Connections (Debug)\n\n"
        # for connection in self.connections:
        #     source_cell = self.cell_map.get(connection.source)
        #     target_cell = self.cell_map.get(connection.target)

        #     if source_cell and target_cell:
        #         source_name = source_cell.get('cleaned_value', connection.source)
        #         target_name = target_cell.get('cleaned_value', connection.target)

        #         cardinality_info = f" [{connection.cardinality}]" if connection.cardinality else ""
        #         label_info = f" ({connection.label})" if connection.label and connection.label != connection.cardinality else ""

        #         description += f"* {source_name} → {target_name}{cardinality_info}{label_info}\n"

        return description

    def print_detailed_analysis(self):
        print("=" * 60)
        print("            ERD ANALYSIS REPORT")
        print("=" * 60)
        print()

        print("ENTITIES FOUND:")
        print("-" * 40)
        if not self.entities:
            print("(No entities detected)")
        for entity in self.entities:
            entity_type = ""
            if entity.is_weak:
                entity_type = " [WEAK ENTITY]"
            elif entity.is_associative:
                entity_type = " [ASSOCIATIVE ENTITY]"

            print(f"Entity: {entity.name}{entity_type} (id: {entity.cell_id})")
            print(f"Position: ({entity.x}, {entity.y})")
            print("Attributes:")
            if not entity.attributes:
                print("  (No attributes)")
            # Sort attributes to put key first
            sorted_attrs = sorted(entity.attributes, key=lambda a: (a.type != 'key', a.name))
            for attr in sorted_attrs:
                attr_info = f"{attr.name}"
                if attr.type == "key":
                    attr_info += " [PRIMARY KEY]"
                elif attr.type == "multivalued":
                    attr_info += " [MULTIVALUED]"
                elif attr.type == "derived":
                    attr_info += " [DERIVED]"
                elif attr.type == "composite":
                    attr_info += " [COMPOSITE]"
                print(f"  - {attr_info} (id: {attr.cell_id})")
            print()

        if self.relationships:
            print("RELATIONSHIPS FOUND:")
            print("-" * 40)
            for rel in self.relationships:
                rel_type = " [IDENTIFYING]" if rel.is_identifying else ""
                print(f"Relationship: {rel.name}{rel_type} (id: {rel.cell_id})")
                print(f"Position: ({rel.x}, {rel.y})")
                if rel.attributes:
                    print("Attributes:")
                    for attr in rel.attributes:
                        attr_info = f"{attr.name}"
                        if attr.type == "key":
                            attr_info += " [PRIMARY KEY]"
                        print(f"  - {attr_info} (id: {attr.cell_id})")
                print()

        if self.inheritances:
            print("INHERITANCE/SPECIALIZATION HIERARCHIES:")
            print("-" * 40)
            for inh in self.inheritances:
                type_desc = {
                    "disjoint": "Disjoint (XOR)",
                    "union": "Union (Total)",
                    "overlapping": "Overlapping (OR)"
                }.get(inh.inheritance_type, inh.inheritance_type)

                print(f"Type: [{inh.get_type_symbol()}] {type_desc} (id: {inh.cell_id})")
                print(f"Parent: {inh.parent_entity} (id: {inh.parent_id})")
                child_names = ', '.join([f"{child['name']} (id: {child['id']})" for child in inh.child_entities])
                print(f"Children: {child_names}")
                print()

        print("CONNECTIONS (DEBUG):")
        print("-" * 40)
        for conn in self.connections:
            source_cell = self.cell_map.get(conn.source, {})
            target_cell = self.cell_map.get(conn.target, {})
            cardinality_info = f" [Cardinality: {conn.cardinality}]" if conn.cardinality else ""
            print(f"From: {source_cell.get('cleaned_value', conn.source)} → To: {target_cell.get('cleaned_value', conn.target)}{cardinality_info} (Label: {conn.label})")

        print("=" * 60)

def main(xml_file_path=None):
    if not xml_file_path:
        print("Usage: python erd_parser_fixed.py <xml_file_path>")
        sys.exit(1)

    if not os.path.exists(xml_file_path):
        print(f"Error: File '{xml_file_path}' not found!")
        sys.exit(1)

    # Check if file is .txt and convert to .xml first
    file_ext = os.path.splitext(xml_file_path)[1].lower()

    if file_ext == '.txt':
        print(f"Detected .txt file. Converting to XML format...")
        # Import conversion function
        try:
            from convertion import convert_txt_to_xml
        except ImportError:
            # Try alternative import path
            try:
                from svgToXml.convertion import convert_txt_to_xml
            except ImportError:
                print("Error: Could not import conversion module. Make sure convertion.py is in the correct location.")
                sys.exit(1)

        # Generate output XML filename
        converted_xml_path = xml_file_path.replace('.txt', '_fixed.xml')
        result = convert_txt_to_xml(xml_file_path, converted_xml_path)

        if not result:
            print("Failed to convert .txt to .xml")
            sys.exit(1)

        # Use the converted file for parsing
        xml_file_path = converted_xml_path
        print(f"Using converted file: {xml_file_path}\n")

    try:
        with open(xml_file_path, 'r', encoding='utf-8') as file:
            xml_content = file.read().strip()
            # Remove BOM if present (often at start of files)
            if xml_content.startswith('\ufeff'):
                xml_content = xml_content[1:]
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    if not xml_content:
        print("Error: File is empty.")
        sys.exit(1)

    try:
        parser = ERDParser(xml_content)
        parser.parse()
    except ET.ParseError as e:
        print(f"Error: Failed to parse XML. The file might be corrupt or not valid XML.")
        print(f"Details: {e}")
        print(f"\nTip: If this is a .txt file with raw XML, the script will auto-convert it.")
        print(f"     If it's an .xml file with errors, try converting it from .txt first.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during parsing: {e}")
        sys.exit(1)

    print("--- Generating Friendly Description ---")
    print(parser.generate_erd_description())

    print("\n--- Detailed Parsing Results (for debugging) ---")
    parser.print_detailed_analysis()

if __name__ == "__main__":
    # Get file path from command-line arguments
    xml_file_path = sys.argv[1] if len(sys.argv) > 1 else "test.output.xml"
    main(xml_file_path)