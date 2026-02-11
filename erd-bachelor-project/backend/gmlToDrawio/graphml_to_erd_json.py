#!/usr/bin/env python3
"""
Convert GraphML directly to ERD JSON format
Bypasses Draw.io conversion - extracts ERD data directly from GraphML
"""

from .graphml_parser import GraphMLParser


def graphml_to_erd_json(graphml_path_or_content):
    """
    Convert GraphML file/content directly to ERD JSON format

    Args:
        graphml_path_or_content: Path to GraphML file or XML string content

    Returns:
        dict: ERD data in the same format as SVG parser output
    """
    try:
        # Parse GraphML
        parser = GraphMLParser(graphml_path_or_content)
        erd_data = parser.parse()

        # Convert to ERD JSON format (same structure as SVG parsing)
        result = {
            'entities': [],
            'relationships': [],
            'attributes': [],
            'connections': [],
            'inheritances': []
        }

        # Add entities with attributes
        for entity_name, entity_data in erd_data['entities'].items():
            entity_attributes = []

            for attr in entity_data['attributes']:
                attr_type = 'simple'
                if attr['is_primary_key']:
                    attr_type = 'key'
                elif attr['is_dashed']:
                    attr_type = 'derived'

                entity_attributes.append({
                    'name': attr['name'],
                    'x': 0,  # Not needed for grading
                    'y': 0,
                    'type': attr_type,
                    'cell_id': f"attr_{attr['name']}"
                })

            result['entities'].append({
                'name': entity_name,
                'x': entity_data['x'],
                'y': entity_data['y'],
                'width': entity_data['width'],
                'height': entity_data['height'],
                'is_weak': False,  # GraphML doesn't explicitly mark weak entities in this format
                'is_associative': False,
                'cell_id': entity_data['id'],
                'attributes': entity_attributes
            })

        # Add relationships with participants and cardinality
        for rel_key, rel_data in erd_data['relationship_types'].items():
            # Find the relationship node
            rel_node = next((r for r in erd_data['relationships'] if r['label'] == rel_data['relationship_node']), None)

            if not rel_node:
                continue

            # Create participants list
            participants = [
                {
                    'name': rel_data['entity1_label'],
                    'cardinality': rel_data['entity1_cardinality'],
                    'cell_id': f"entity_{rel_data['entity1_label']}"
                },
                {
                    'name': rel_data['entity2_label'],
                    'cardinality': rel_data['entity2_cardinality'],
                    'cell_id': f"entity_{rel_data['entity2_label']}"
                }
            ]

            # Create connection summary
            connection_summary = f"**{rel_data['entity1_label']}** [{rel_data['entity1_cardinality']}] has a {rel_data['type'].replace('-', ' ')} relationship with **{rel_data['entity2_label']}** [{rel_data['entity2_cardinality']}]"

            result['relationships'].append({
                'name': rel_data['relationship_node'],
                'x': rel_node['x'],
                'y': rel_node['y'],
                'width': rel_node['width'],
                'height': rel_node['height'],
                'is_identifying': False,  # GraphML doesn't explicitly mark identifying relationships
                'cell_id': rel_node['id'],
                'relationship_type': 'binary',
                'participants': participants,
                'attributes': [],
                'connection_summary': connection_summary
            })

        # Add inheritances
        for inh in erd_data.get('inheritances', []):
            result['inheritances'].append({
                'parent_entity': inh['parent_entity'],
                'parent_id': inh['parent_id'],
                'child_entities': inh['child_entities'],
                'inheritance_type': inh['inheritance_type'],
                'symbol': inh['symbol'],
                'x': inh['x'],
                'y': inh['y'],
                'cell_id': inh['cell_id']
            })

        # Generate ERD description
        result['erd_description'] = _generate_erd_description(result)

        print(f"Successfully parsed GraphML:")
        print(f"  - {len(result['entities'])} entities")
        print(f"  - {len(result['relationships'])} relationships")
        print(f"  - {len(result['inheritances'])} inheritances")
        print(f"  - Total attributes: {sum(len(e['attributes']) for e in result['entities'])}")

        return result

    except Exception as e:
        print(f"Error parsing GraphML: {e}")
        import traceback
        traceback.print_exc()
        return None


def _generate_erd_description(erd_data):
    """Generate markdown ERD description"""
    description = "## Entity-Relationship Diagram (ERD)\n\n"

    description += "### 1. Entities\n\n"
    for entity in erd_data['entities']:
        entity_type = ""
        if entity.get('is_weak'):
            entity_type = " (Weak Entity)"
        elif entity.get('is_associative'):
            entity_type = " (Associative Entity)"

        description += f"* **{entity['name']}**{entity_type}\n"
        if entity['attributes']:
            description += "  * **Attributes:**\n"
            sorted_attrs = sorted(entity['attributes'], key=lambda a: (a['type'] != 'key', a['name']))
            for attr in sorted_attrs:
                attr_info = f"`{attr['name']}`"
                if attr['type'] == "key":
                    attr_info += " **[PRIMARY KEY]**"
                elif attr['type'] == "multivalued":
                    attr_info += " (Multivalued)"
                elif attr['type'] == "derived":
                    attr_info += " (Derived)"
                elif attr['type'] == "composite":
                    attr_info += " (Composite)"
                description += f"    * {attr_info}\n"
        description += "\n"

    if erd_data['relationships']:
        description += "### 2. Relationships\n\n"
        for rel in erd_data['relationships']:
            rel_type = " (Identifying)" if rel.get('is_identifying') else ""
            description += f"* **{rel['name']}**{rel_type}\n"

            if rel.get('connection_summary'):
                # Clean up markdown for display
                summary = rel['connection_summary'].replace('**', '')
                description += f"  * {summary}\n"

            if rel.get('attributes'):
                description += "  * **Attributes:**\n"
                for attr in rel['attributes']:
                    description += f"    * `{attr['name']}`\n"
            description += "\n"

    if erd_data.get('inheritances'):
        description += "### 3. Inheritance/Specialization\n\n"
        type_descriptions = {
            'disjoint': 'Disjoint (d) - Entity belongs to one subtype only',
            'overlapping': 'Overlapping (o) - Entity can belong to multiple subtypes',
            'union': 'Union/Total (u) - Every parent MUST belong to at least one subtype'
        }
        for inh in erd_data['inheritances']:
            symbol = inh.get('symbol', '?')
            inh_type = inh.get('inheritance_type', 'unknown')
            type_desc = type_descriptions.get(inh_type, inh_type)
            parent = inh.get('parent_entity', 'Unknown')
            children = ', '.join([child['name'] for child in inh.get('child_entities', [])])

            description += f"* **[{symbol}] {parent}** → {type_desc}\n"
            description += f"  * **Subtypes:** {children}\n\n"

    return description
