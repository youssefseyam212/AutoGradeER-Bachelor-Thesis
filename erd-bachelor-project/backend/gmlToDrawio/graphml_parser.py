#!/usr/bin/env python3
"""
GraphML to ERD Parser
Extracts entities, attributes, relationships, and cardinalities from yEd GraphML files
"""

import xml.etree.ElementTree as ET


class GraphMLParser:
    """Parse yEd GraphML files and extract ERD components"""

    def __init__(self, graphml_content):
        """
        Initialize parser with GraphML content

        Args:
            graphml_content: String content of GraphML file or file path
        """
        if graphml_content.startswith('<?xml'):
            # It's XML content
            self.root = ET.fromstring(graphml_content)
        else:
            # It's a file path
            tree = ET.parse(graphml_content)
            self.root = tree.getroot()

        self.entities = {}
        self.attributes = []
        self.relationships = []
        self.edges = []
        self.nodes = {}
        self.relationship_types = {}
        self.inheritances = []  # Store inheritance/specialization hierarchies

    def parse(self):
        """Parse the GraphML and extract ERD components"""
        # Find the graph element
        graph = self.root.find('.//{http://graphml.graphdrawing.org/xmlns}graph')
        if graph is None:
            graph = self.root.find('.//graph')

        if graph is None:
            raise ValueError("Could not find graph element in GraphML")

        # Parse nodes first
        self._parse_nodes(graph)

        # Parse edges
        self._parse_edges(graph)

        # Analyze relationship types
        self._analyze_relationship_types()

        # Analyze inheritance hierarchies
        self._analyze_inheritances()

        return {
            'entities': self.entities,
            'attributes': self.attributes,
            'relationships': self.relationships,
            'edges': self.edges,
            'relationship_types': self.relationship_types,
            'inheritances': self.inheritances
        }

    def _parse_nodes(self, graph):
        """Parse all nodes from the graph"""
        for node in graph.findall('.//{http://graphml.graphdrawing.org/xmlns}node'):
            node_id = node.get('id')

            # Get label
            label_element = node.find('.//{http://www.yworks.com/xml/graphml}NodeLabel')
            label = label_element.text.strip() if label_element is not None and label_element.text else 'Unknown'

            # Get configuration type from GenericNode or check for UMLClassNode/ShapeNode
            generic_node = node.find('.//{http://www.yworks.com/xml/graphml}GenericNode')
            uml_class_node = node.find('.//{http://www.yworks.com/xml/graphml}UMLClassNode')
            shape_node = node.find('.//{http://www.yworks.com/xml/graphml}ShapeNode')

            if generic_node is not None:
                config = generic_node.get('configuration', '')
            elif uml_class_node is not None:
                config = 'com.yworks.entityRelationship.small_entity'  # Treat UMLClassNode as entity
            elif shape_node is not None:
                # Determine based on shape type
                shape_elem = shape_node.find('.//{http://www.yworks.com/xml/graphml}Shape')
                if shape_elem is not None:
                    shape_type = shape_elem.get('type', 'rectangle')
                    if shape_type == 'ellipse':
                        config = 'com.yworks.entityRelationship.attribute'
                    elif shape_type == 'diamond':
                        config = 'com.yworks.entityRelationship.relationship'
                    else:
                        config = 'com.yworks.entityRelationship.small_entity'
                else:
                    config = ''
            else:
                config = ''

            # Check if underlined (primary key)
            is_underlined = label_element.get('underlinedText', 'false') == 'true' if label_element is not None else False

            # Get geometry
            geometry = node.find('.//{http://www.yworks.com/xml/graphml}Geometry')
            x = float(geometry.get('x', 0)) if geometry is not None else 0
            y = float(geometry.get('y', 0)) if geometry is not None else 0
            width = float(geometry.get('width', 100)) if geometry is not None else 100
            height = float(geometry.get('height', 50)) if geometry is not None else 50

            # Get border style (for dashed lines - derived attributes)
            border = node.find('.//{http://www.yworks.com/xml/graphml}BorderStyle')
            is_dashed = border.get('type', 'line') in ['dashed', 'dotted'] if border is not None else False

            # Get actual shape type if available
            actual_shape_type = None
            if shape_node is not None:
                shape_elem = shape_node.find('.//{http://www.yworks.com/xml/graphml}Shape')
                if shape_elem is not None:
                    actual_shape_type = shape_elem.get('type', 'rectangle')

            node_data = {
                'id': node_id,
                'label': label,
                'config': config,
                'is_primary_key': is_underlined,
                'is_dashed': is_dashed,
                'x': x,
                'y': y,
                'width': width,
                'height': height,
                'shape_type': actual_shape_type  # Store actual shape type
            }

            self.nodes[node_id] = node_data

            # Classify node type based on configuration
            if 'small_entity' in config:
                # Entity
                if label not in self.entities:
                    self.entities[label] = {
                        'id': node_id,
                        'attributes': [],
                        'x': x,
                        'y': y,
                        'width': width,
                        'height': height
                    }
            elif 'attribute' in config:
                # Attribute
                self.attributes.append(node_data)
            elif 'relationship' in config:
                # Relationship
                self.relationships.append(node_data)

    def _parse_edges(self, graph):
        """Parse all edges from the graph"""
        for edge in graph.findall('.//{http://graphml.graphdrawing.org/xmlns}edge'):
            source = edge.get('source')
            target = edge.get('target')

            # Get arrow types for cardinality
            arrows = edge.find('.//{http://www.yworks.com/xml/graphml}Arrows')
            source_arrow = arrows.get('source', 'none') if arrows is not None else 'none'
            target_arrow = arrows.get('target', 'none') if arrows is not None else 'none'

            edge_data = {
                'source': source,
                'target': target,
                'source_arrow': source_arrow,
                'target_arrow': target_arrow
            }

            self.edges.append(edge_data)

            # Connect attributes to entities
            source_node = self.nodes.get(source)
            target_node = self.nodes.get(target)

            if source_node and target_node:
                # Entity -> Attribute
                if 'small_entity' in source_node['config'] and 'attribute' in target_node['config']:
                    entity_name = source_node['label']
                    if entity_name in self.entities:
                        self.entities[entity_name]['attributes'].append({
                            'name': target_node['label'],
                            'is_primary_key': target_node['is_primary_key'],
                            'is_dashed': target_node['is_dashed']
                        })

                # Attribute -> Entity
                elif 'attribute' in source_node['config'] and 'small_entity' in target_node['config']:
                    entity_name = target_node['label']
                    if entity_name in self.entities:
                        self.entities[entity_name]['attributes'].append({
                            'name': source_node['label'],
                            'is_primary_key': source_node['is_primary_key'],
                            'is_dashed': source_node['is_dashed']
                        })

    def _get_cardinality_from_arrow(self, arrow_type):
        """Convert yEd arrow type to cardinality"""
        if 'crows_foot_many' in arrow_type:
            return 'many'
        if 'crows_foot_one' in arrow_type:
            return 'one'
        return 'one'  # Default

    def _analyze_relationship_types(self):
        """Analyze relationships to determine their types (1:1, 1:N, M:N)"""
        for relationship_node in self.relationships:
            # Find edges connected to this relationship
            connected_edges = [
                edge for edge in self.edges
                if edge['source'] == relationship_node['id'] or edge['target'] == relationship_node['id']
            ]

            # Find entities connected to this relationship
            connected_entities = []

            for edge in connected_edges:
                node_id = edge['target'] if edge['source'] == relationship_node['id'] else edge['source']
                node = self.nodes.get(node_id)

                if node and 'small_entity' in node['config']:
                    is_relationship_source = edge['source'] == relationship_node['id']
                    connected_entities.append({
                        'entity': node,
                        'edge': edge,
                        'is_relationship_source': is_relationship_source
                    })

            # Should have exactly 2 entities for binary relationship
            if len(connected_entities) == 2:
                entity1 = connected_entities[0]
                entity2 = connected_entities[1]

                # Determine cardinality for entity1
                if entity1['is_relationship_source']:
                    cardinality1 = self._get_cardinality_from_arrow(entity1['edge']['target_arrow'])
                else:
                    cardinality1 = self._get_cardinality_from_arrow(entity1['edge']['source_arrow'])

                # Determine cardinality for entity2
                if entity2['is_relationship_source']:
                    cardinality2 = self._get_cardinality_from_arrow(entity2['edge']['target_arrow'])
                else:
                    cardinality2 = self._get_cardinality_from_arrow(entity2['edge']['source_arrow'])

                # Determine relationship type
                rel_type = 'unknown'
                cardinality = 'unknown'

                if cardinality1 == 'one' and cardinality2 == 'one':
                    rel_type = 'one-to-one'
                    cardinality = '1:1'
                elif cardinality1 == 'one' and cardinality2 == 'many':
                    rel_type = 'one-to-many'
                    cardinality = '1:N'
                elif cardinality1 == 'many' and cardinality2 == 'one':
                    rel_type = 'one-to-many'
                    cardinality = 'N:1'
                elif cardinality1 == 'many' and cardinality2 == 'many':
                    rel_type = 'many-to-many'
                    cardinality = 'M:N'

                # Store relationship type
                relationship_key = f"{entity1['entity']['label']}-{entity2['entity']['label']}-{relationship_node['label']}"

                self.relationship_types[relationship_key] = {
                    'type': rel_type,
                    'cardinality': cardinality,
                    'relationship_node': relationship_node['label'],
                    'entity1_label': entity1['entity']['label'],
                    'entity2_label': entity2['entity']['label'],
                    'entity1_cardinality': cardinality1,
                    'entity2_cardinality': cardinality2
                }

    def _analyze_inheritances(self):
        """Analyze inheritance/specialization hierarchies (D, O, U symbols - case insensitive)"""
        # Find all nodes that might be inheritance symbols (small circles with D, O, or U)
        inheritance_symbols = []

        for node_id, node_data in self.nodes.items():
            # Case-insensitive check for D, O, or U
            label = node_data['label'].strip().upper()

            # Check if it's a single character D, O, or U (case insensitive)
            if label in ['D', 'O', 'U']:
                # Check if it's an ellipse (circle) - inheritance symbols are typically circles
                if node_data.get('shape_type') == 'ellipse' or 'attribute' in node_data.get('config', ''):
                    inheritance_symbols.append({
                        'id': node_id,
                        'symbol': label,  # Store uppercase for consistency
                        'x': node_data['x'],
                        'y': node_data['y']
                    })

        # For each inheritance symbol, find parent and child entities
        for symbol_data in inheritance_symbols:
            symbol_id = symbol_data['id']
            symbol = symbol_data['symbol']

            # Determine inheritance type (case insensitive)
            if symbol == 'D':
                inheritance_type = 'disjoint'
            elif symbol == 'O':
                inheritance_type = 'overlapping'
            elif symbol == 'U':
                inheritance_type = 'union'
            else:
                inheritance_type = 'unknown'

            # Find connected entities
            parent_entity = None
            child_entities = []

            for edge in self.edges:
                # Check if symbol is involved in this edge
                if edge['source'] == symbol_id or edge['target'] == symbol_id:
                    # Get the other node
                    other_id = edge['target'] if edge['source'] == symbol_id else edge['source']
                    other_node = self.nodes.get(other_id)

                    if other_node and 'small_entity' in other_node.get('config', ''):
                        entity_name = other_node['label']

                        # Determine if this is parent or child based on edge direction
                        # Typically: parent -> symbol -> children
                        if edge['target'] == symbol_id:
                            # Entity pointing TO symbol = parent
                            parent_entity = {
                                'name': entity_name,
                                'id': other_id
                            }
                        else:
                            # Symbol pointing TO entity = child
                            child_entities.append({
                                'name': entity_name,
                                'id': other_id
                            })

            # Only create inheritance if we have at least a parent and one child
            if parent_entity and len(child_entities) > 0:
                self.inheritances.append({
                    'parent_entity': parent_entity['name'],
                    'parent_id': parent_entity['id'],
                    'child_entities': child_entities,
                    'inheritance_type': inheritance_type,
                    'symbol': symbol,
                    'x': symbol_data['x'],
                    'y': symbol_data['y'],
                    'cell_id': symbol_id
                })
