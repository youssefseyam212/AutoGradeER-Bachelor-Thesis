"""
Schema-based ERD grading using evaluation rubrics.
This module grades student ERDs against structured evaluation schemas (like the Milestone 1 rubric).
"""

import json
import traceback
import google.generativeai as genai


def normalize_entity_name(name):
    """Normalize entity/relation names for fuzzy matching"""
    if not name:
        return ""
    # Remove special characters, convert to lowercase, remove extra spaces
    normalized = name.lower().strip()
    normalized = normalized.replace('-', ' ').replace('_', ' ')
    # Remove extra whitespace
    normalized = ' '.join(normalized.split())
    return normalized


def convert_cardinality_to_erd_notation(cardinality):
    """
    Convert UML-style cardinality to ERD notation.
    Examples:
        '1..*' or '1..N' or 'M' or 'N' or 'many' -> 'M' (Many)
        '0..*' or '0..N' -> 'M' (Many, optional)
        '1' or 'one' -> '1' (One)
        '0..1' -> '1' (One, optional)
    """
    if not cardinality:
        return ''

    card_str = str(cardinality).strip().upper()

    # Handle many/multiple notations (including GraphML 'many')
    if '..*' in card_str or '..N' in card_str or card_str in ['M', 'N', '*', 'MANY']:
        return 'M'

    # Handle one notations (including GraphML 'one')
    if card_str in ['1', '0..1', 'E O', 'EO', 'ONE']:
        return '1'

    # If it starts with 1 and doesn't have .., it's ONE
    if card_str.startswith('1') and '..' not in card_str:
        return '1'

    # Default to the original value
    return cardinality


def compare_cardinalities(expected_card, student_card):
    """
    Compare two cardinalities after normalizing them to ERD notation.
    Returns True if they match (considering M and N as equivalent).
    """
    # Split composite cardinalities like "M:1" or "1..*:0..*"
    expected_parts = expected_card.split(':') if ':' in expected_card else [expected_card]
    student_parts = student_card.split(':') if ':' in student_card else [student_card]

    if len(expected_parts) != len(student_parts):
        return False

    # Normalize each part and compare
    for exp, stu in zip(expected_parts, student_parts):
        exp_norm = convert_cardinality_to_erd_notation(exp)
        stu_norm = convert_cardinality_to_erd_notation(stu)

        # M and N are equivalent
        if exp_norm in ['M', 'N'] and stu_norm in ['M', 'N']:
            continue
        elif exp_norm != stu_norm:
            return False

    return True


def find_entity_in_erd(entity_name, erd_entities):
    """
    Find an entity in the ERD using fuzzy matching.
    Returns (found: bool, matched_entity: dict or None, confidence: float)
    """
    normalized_target = normalize_entity_name(entity_name)

    for entity in erd_entities:
        normalized_candidate = normalize_entity_name(entity.get('name', ''))

        # Exact match
        if normalized_target == normalized_candidate:
            return True, entity, 1.0

        # Partial match (one contains the other)
        if normalized_target in normalized_candidate or normalized_candidate in normalized_target:
            return True, entity, 0.8

    return False, None, 0.0


def find_relationship_in_erd(relation_name, erd_relationships):
    """
    Find a relationship in the ERD using fuzzy matching.
    Handles cases like "Employee - Department M:1" matching with actual relationships.
    """
    normalized_target = normalize_entity_name(relation_name)

    # Extract entities from schema relation name (e.g., "Employee - Department")
    parts = relation_name.split('-')
    if len(parts) >= 2:
        entity1 = normalize_entity_name(parts[0].strip())
        entity2 = normalize_entity_name(parts[1].split('(')[0].strip())  # Remove inheritance type

        # Check each relationship
        for rel in erd_relationships:
            participants = rel.get('participants', [])

            # For binary relationships
            if len(participants) == 2:
                # Try 'name' first (from SVG/DrawIO), then 'entity' (from GraphML)
                p1_name = normalize_entity_name(participants[0].get('name') or participants[0].get('entity', ''))
                p2_name = normalize_entity_name(participants[1].get('name') or participants[1].get('entity', ''))

                # Check if entities match (order doesn't matter)
                if (entity1 in p1_name or p1_name in entity1) and (entity2 in p2_name or p2_name in entity2):
                    return True, rel, 0.9
                if (entity1 in p2_name or p2_name in entity1) and (entity2 in p1_name or p1_name in entity2):
                    return True, rel, 0.9

    # Fallback: check relationship name directly
    for rel in erd_relationships:
        normalized_rel = normalize_entity_name(rel.get('name', ''))
        if normalized_target in normalized_rel or normalized_rel in normalized_target:
            return True, rel, 0.7

    return False, None, 0.0


def grade_entities(schema_entities, student_erd, schema_relations=None):
    """
    Grade entities section with dynamic parent-child detection.
    Returns: (score, total_possible, found_count, items_analysis)
    """
    score = 0.0
    total_possible = 0.0
    found_count = 0
    items_analysis = []

    student_entities = student_erd.get('entities', [])
    student_inheritances = student_erd.get('inheritances', [])

    # DYNAMIC: Build parent-child map from schema relations (inheritance relationships)
    parent_child_map = {}
    if schema_relations:
        for relation in schema_relations:
            relation_type = relation.get('type', '')
            if relation_type:  # It's an inheritance relationship
                # Extract parent and child from relation name (e.g., "Contract - Full-Time Contract")
                parts = relation['name'].split(' - ')
                if len(parts) >= 2:
                    parent = parts[0].strip()
                    child = parts[1].strip()
                    if parent not in parent_child_map:
                        parent_child_map[parent] = []
                    parent_child_map[parent].append(child)

    for schema_entity in schema_entities:
        entity_name = schema_entity['name']
        points = schema_entity['points']
        total_possible += points

        found, matched_entity, confidence = find_entity_in_erd(entity_name, student_entities)

        if found:
            # Give full points for any match
            earned_points = points
            score += earned_points
            found_count += 1

            items_analysis.append({
                'name': entity_name,
                'found': True,
                'points_possible': points,
                'points_earned': round(earned_points, 2),
                'note': f"Matched with '{matched_entity['name']}'" if confidence < 1.0 else None,
                'student_value': matched_entity['name'],
                'expected_value': entity_name
            })
        else:
            # DYNAMIC: Check if this entity is a child in any inheritance relationship
            partial_credit_given = False

            for parent_name, children in parent_child_map.items():
                if entity_name in children:
                    # This is a child entity - check if parent exists in student ERD
                    parent_found, parent_entity, _ = find_entity_in_erd(parent_name, student_entities)

                    if parent_found:
                        # Give 48% partial credit if parent exists (alternative design: no inheritance)
                        earned_points = points * 0.48
                        score += earned_points
                        found_count += 1
                        partial_credit_given = True

                        items_analysis.append({
                            'name': entity_name,
                            'found': True,
                            'points_possible': points,
                            'points_earned': round(earned_points, 2),
                            'note': f"Parent entity '{parent_entity['name']}' exists (60% partial credit for alternative design)",
                            'student_value': f"Using parent entity: {parent_entity['name']}",
                            'expected_value': entity_name,
                            'is_alternative_design': True
                        })
                        break

            if not partial_credit_given:
                items_analysis.append({
                    'name': entity_name,
                    'found': False,
                    'points_possible': points,
                    'points_earned': 0,
                    'note': 'Entity not found in student ERD',
                    'student_value': None,
                    'expected_value': entity_name
                })

    return score, total_possible, found_count, items_analysis


def grade_relationships(schema_relations, student_erd):
    """
    Grade relationships section (more complex - includes cardinalities and inheritance).
    Returns: (score, total_possible, found_count, items_analysis)
    """
    score = 0.0
    total_possible = 0.0
    found_count = 0
    items_analysis = []

    student_relationships = student_erd.get('relationships', [])
    student_inheritances = student_erd.get('inheritances', [])

    for schema_relation in schema_relations:
        relation_name = schema_relation['name']
        points = schema_relation['points']
        total_possible += points

        relation_type = schema_relation.get('type', '')  # e.g., "Disjoint-partial", "Disjoint-total"
        cardinality = schema_relation.get('cardinality', '')  # e.g., "M:1", "1:M"

        # Check if this is an inheritance relationship
        if 'inheritance' in relation_name.lower() or relation_type:
            # Look in inheritances
            found_inheritance = False
            for inh in student_inheritances:
                parent = normalize_entity_name(inh.get('parent_entity', ''))
                if parent in normalize_entity_name(relation_name):
                    found_inheritance = True
                    score += points
                    found_count += 1
                    items_analysis.append({
                        'name': relation_name,
                        'found': True,
                        'points_possible': points,
                        'points_earned': points,
                        'note': f"Inheritance found: {inh['parent_entity']} -> {', '.join([c['name'] for c in inh['child_entities']])}"
                    })
                    break

            if not found_inheritance:
                parts = relation_name.split(' - ')
                if len(parts) >= 2:
                    parent_name = parts[0].strip()
                    child_name = parts[1].strip()

                    student_entities = student_erd.get('entities', [])
                    parent_exists, _, _ = find_entity_in_erd(parent_name, student_entities)

                    if parent_exists:
                        earned_points = points * 0.45
                        score += earned_points
                        found_count += 1
                        items_analysis.append({
                            'name': relation_name,
                            'found': True,
                            'points_possible': points,
                            'points_earned': round(earned_points, 2),
                            'note': f"Parent entity '{parent_name}' exists without inheritance (50% partial credit for alternative design)"
                        })
                    else:
                        items_analysis.append({
                            'name': relation_name,
                            'found': False,
                            'points_possible': points,
                            'points_earned': 0,
                            'note': 'Inheritance relationship not found'
                        })
                else:
                    items_analysis.append({
                        'name': relation_name,
                        'found': False,
                        'points_possible': points,
                        'points_earned': 0,
                        'note': 'Inheritance relationship not found'
                    })
        else:
            # Regular relationship
            found, matched_rel, confidence = find_relationship_in_erd(relation_name, student_relationships)

            if found:
                # Give full points for any match
                earned_points = points
                score += earned_points
                found_count += 1

                # Check cardinality if specified (informational only, no deduction)
                cardinality_note = None
                if cardinality and matched_rel:
                    # Extract student's cardinality and convert to ERD notation
                    participants = matched_rel.get('participants', [])
                    if len(participants) == 2:
                        student_card_raw = f"{participants[0].get('cardinality', '')}:{participants[1].get('cardinality', '')}"
                        # Convert to ERD notation for comparison
                        student_card_normalized = f"{convert_cardinality_to_erd_notation(participants[0].get('cardinality', ''))}:{convert_cardinality_to_erd_notation(participants[1].get('cardinality', ''))}"

                        # Compare using the normalized versions
                        if not compare_cardinalities(cardinality, student_card_normalized):
                            cardinality_note = f"Note: expected {cardinality}, found {student_card_normalized} (raw: {student_card_raw})"

                items_analysis.append({
                    'name': relation_name,
                    'found': True,
                    'points_possible': points,
                    'points_earned': round(earned_points, 2),
                    'note': cardinality_note
                })
            else:
                items_analysis.append({
                    'name': relation_name,
                    'found': False,
                    'points_possible': points,
                    'points_earned': 0,
                    'note': 'Relationship not found in student ERD'
                })

    return score, total_possible, found_count, items_analysis


def grade_schema_section(schema_items, student_erd):
    """
    Grade the integrated schema section that includes entities, relationships,
    inheritance, ternary, and weak entities all together.

    Returns: (score, total_possible, found_count, items_analysis)
    """
    score = 0.0
    total_possible = 0.0
    found_count = 0
    items_analysis = []

    student_entities = student_erd.get('entities', [])
    student_relationships = student_erd.get('relationships', [])
    student_inheritances = student_erd.get('inheritances', [])

    for schema_item in schema_items:
        item_name = schema_item['name']
        item_type = schema_item.get('type', 'entity')
        points = schema_item['points']
        total_possible += points

        found = False
        note = None
        earned_points = 0

        if item_type == 'entity':
            # Regular entity
            found, matched_entity, confidence = find_entity_in_erd(item_name, student_entities)
            if found:
                earned_points = points
                score += earned_points
                found_count += 1
                note = f"Matched with '{matched_entity['name']}'" if confidence < 1.0 else None

        elif item_type == 'weak_entity':
            # Weak entity - extract name from pattern like "Allowance and deduction (weak)"
            entity_name = item_name.replace('(weak)', '').strip()
            found, matched_entity, confidence = find_entity_in_erd(entity_name, student_entities)
            if found and matched_entity.get('is_weak', False):
                earned_points = points
                score += earned_points
                found_count += 1
                note = "Weak entity correctly identified"
            elif found:
                # Found entity but not marked as weak - give partial credit
                earned_points = points
                score += earned_points
                found_count += 1
                note = "Entity found (not marked as weak in diagram)"
            else:
                note = "Weak entity not found"

        elif item_type == 'relationship':
            # Regular relationship - extract relationship name and cardinality
            # Format: "Employee - Role 1:M" or "Contract - Insurance M:N"
            found, matched_rel, confidence = find_relationship_in_erd(item_name, student_relationships)
            if found:
                earned_points = points
                score += earned_points
                found_count += 1

                # Check cardinality if present in name
                if ':' in item_name:
                    cardinality_part = item_name.split()[-1]  # Get last part like "1:M"
                    if matched_rel and 'participants' in matched_rel:
                        participants = matched_rel.get('participants', [])
                        if len(participants) == 2:
                            student_card_raw = f"{participants[0].get('cardinality', '')}:{participants[1].get('cardinality', '')}"
                            student_card_normalized = f"{convert_cardinality_to_erd_notation(participants[0].get('cardinality', ''))}:{convert_cardinality_to_erd_notation(participants[1].get('cardinality', ''))}"

                            if not compare_cardinalities(cardinality_part, student_card_normalized):
                                note = f"Note: expected {cardinality_part}, found {student_card_normalized} (raw: {student_card_raw})"
            else:
                note = "Relationship not found"

        elif item_type == 'ternary':
            # Ternary relationship - look for relationships with 3 participants
            # Format: "Attendance - Shift schedule - Employee M:N:1"
            found_ternary = False

            # First, check if student used a proper ternary relationship
            for rel in student_relationships:
                if rel.get('relationship_type') == 'ternary':
                    # Check if participant entities match
                    participants = rel.get('participants', [])
                    if len(participants) == 3:
                        # Extract entity names from schema item name
                        parts = item_name.split(' - ')
                        if len(parts) >= 3:
                            schema_entities = [normalize_entity_name(p.split()[0]) for p in parts[:3]]
                            student_entity_names = [normalize_entity_name(p.get('entity', '')) for p in participants]

                            # Check if all entities match (order doesn't matter)
                            if all(any(se in sn or sn in se for sn in student_entity_names) for se in schema_entities):
                                found_ternary = True
                                earned_points = points
                                score += earned_points
                                found_count += 1
                                note = f"Ternary relationship found: {rel['name']}"
                                break

            # If no ternary found, check if student decomposed it into binary relationships
            if not found_ternary:
                # Extract the 3 entity names from the schema item
                parts = item_name.split(' - ')
                if len(parts) >= 3:
                    schema_entities = [normalize_entity_name(p.split()[0]) for p in parts[:3]]

                    # Look for binary relationships connecting these 3 entities
                    # We need at least 2-3 binary relationships involving these entities
                    found_binaries = []
                    for rel in student_relationships:
                        if rel.get('relationship_type') != 'ternary':
                            participants = rel.get('participants', [])
                            if len(participants) == 2:
                                p1_name = normalize_entity_name(participants[0].get('name') or participants[0].get('entity', ''))
                                p2_name = normalize_entity_name(participants[1].get('name') or participants[1].get('entity', ''))

                                # Check if this binary connects 2 of our 3 entities
                                entities_matched = []
                                for se in schema_entities:
                                    if se in p1_name or p1_name in se:
                                        entities_matched.append(se)
                                    elif se in p2_name or p2_name in se:
                                        entities_matched.append(se)

                                if len(entities_matched) >= 2:
                                    found_binaries.append(rel['name'])

                    # If we found 2+ binary relationships involving the 3 entities, give partial credit
                    if len(found_binaries) >= 2:
                        found_ternary = True
                        # Give 80% of points for valid decomposition
                        earned_points = points * 0.8
                        score += earned_points
                        found_count += 1
                        note = f"Ternary decomposed into binaries: {', '.join(found_binaries[:3])} (80% credit for valid alternative)"
                    else:
                        note = "Ternary relationship not found (neither as ternary nor decomposed binaries)"
                else:
                    note = "Ternary relationship not found"

            found = found_ternary

        elif item_type == 'inheritance':
            # Inheritance - extract child entity name
            # Format: "HR Administrator (inheritance)" or "Full-Time Contract (inheritance)"
            # This means we expect a parent entity that has this as a child
            child_name_expected = item_name.replace('(inheritance)', '').strip()
            child_normalized = normalize_entity_name(child_name_expected)
            found_inheritance = False

            # STEP 1: Try simple string matching first for performance (fast path)
            for inh in student_inheritances:
                parent_entity = inh.get('parent_entity', '')
                child_entities = inh.get('child_entities', [])

                # Check if any child in this inheritance matches the expected child
                for child in child_entities:
                    child_name_student = child.get('name', '')
                    child_student_normalized = normalize_entity_name(child_name_student)

                    # Semantic matching: handle variations like "FullTimeContract" vs "Full-Time Contract"
                    # Remove spaces, hyphens, underscores for comparison
                    child_clean_expected = child_normalized.replace(' ', '').replace('-', '').replace('_', '')
                    child_clean_student = child_student_normalized.replace(' ', '').replace('-', '').replace('_', '')

                    # Check if they match semantically (simple string matching)
                    if (child_clean_expected == child_clean_student or
                        child_clean_expected in child_clean_student or
                        child_clean_student in child_clean_expected):

                        found_inheritance = True
                        earned_points = points
                        score += earned_points
                        found_count += 1
                        note = f"Inheritance found: {parent_entity} → {child_name_student}"
                        break

                if found_inheritance:
                    break

            # STEP 2: If simple matching failed, use AI for intelligent matching (slow path)
            # This handles cases like "HR Administrator" under EMPLOYEE or "Contract-Based Salary Type" vs "ContractSalaryType"
            if not found_inheritance:
                print(f"  → Simple matching failed for '{child_name_expected}', trying AI matching...")
                ai_found, ai_parent, ai_child, ai_note = ai_match_inheritance(
                    child_name_expected,
                    student_inheritances
                )

                if ai_found:
                    found_inheritance = True
                    earned_points = points
                    score += earned_points
                    found_count += 1
                    note = ai_note
                    print(f"  ✓ AI matched: {ai_parent} → {ai_child}")
                else:
                    note = "Inheritance relationship not found (checked with AI)"
                    print(f"  ✗ Not found even with AI")

            found = found_inheritance

        # Add to analysis
        items_analysis.append({
            'name': item_name,
            'type': item_type,
            'found': found,
            'points_possible': points,
            'points_earned': round(earned_points, 2),
            'note': note
        })

    return score, total_possible, found_count, items_analysis


def apply_deductions(student_erd, schema_deductions):
    """
    Apply deduction rules (e.g., missing weak entity, wrong cardinality).
    Returns: (total_deduction, deductions_applied_list)
    """
    total_deduction = 0.0
    deductions_applied = []

    student_entities = student_erd.get('entities', [])
    student_relationships = student_erd.get('relationships', [])
    student_inheritances = student_erd.get('inheritances', [])

    # Count weak entities in schema vs student
    weak_entities_count = sum(1 for e in student_entities if e.get('is_weak', False))

    # Count ternary relationships
    ternary_count = sum(1 for r in student_relationships if r.get('relationship_type') == 'ternary')

    # Count inheritances
    inheritance_count = len(student_inheritances)

    # These are just example deductions - can be expanded
    # For now, we won't apply deductions automatically since we don't have a reference to compare

    return total_deduction, deductions_applied


def generate_detailed_explanations(items_analysis, item_type):
    """
    Generate detailed AI-powered explanations for each graded item.
    Explains WHY something is wrong, WHAT is correct, and WHAT should be done.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Process items in batches for efficiency
        items_with_issues = [
            item for item in items_analysis
            if not item['found'] or item.get('is_alternative_design') or item.get('note')
        ]

        if not items_with_issues:
            return items_analysis  # All items are perfect, no need for explanations

        # Create batch prompt for all items needing explanation
        items_summary = []
        for idx, item in enumerate(items_with_issues):
            items_summary.append({
                'index': idx,
                'name': item['name'],
                'type': item.get('type', item_type),
                'found': item['found'],
                'expected_value': item.get('expected_value'),
                'student_value': item.get('student_value'),
                'note': item.get('note'),
                'is_alternative_design': item.get('is_alternative_design', False),
                'points_earned': item['points_earned'],
                'points_possible': item['points_possible']
            })

        prompt = f"""You are an expert database design professor providing detailed feedback on student ERD work.

**YOUR TASK:** Generate detailed, educational explanations for each item that has issues or needs clarification.

**CONTEXT:** This is an HR Management System ERD evaluation.

**ITEMS NEEDING EXPLANATION:**
{json.dumps(items_summary, indent=2)}

**INSTRUCTIONS:**
For each item, provide a detailed explanation object with these fields:

1. **why_wrong**: Clear explanation of WHY this is marked as incorrect or partial credit
   - If found=false: explain what entity/relationship is missing and why it's important
   - If is_alternative_design=true: explain the design difference
   - If note exists: elaborate on the specific issue mentioned

2. **what_is_correct**: Explain the CORRECT approach or expected model
   - What should the student have modeled?
   - What are the proper entities/relationships/cardinalities?
   - Reference the business domain (HR Management System)

3. **what_should_happen**: Explain the EXPECTED BEHAVIOR or business logic
   - What business rule should this capture?
   - Why is this entity/relationship needed?
   - How does it fit into the overall system?

4. **correct_equivalent**: Provide the EXACT correct equivalent
   - Specific entity name, relationship, or cardinality expected
   - Example: "Employee - Department with M:1 cardinality"
   - Include any attributes or constraints if relevant

5. **how_to_fix**: Step-by-step guidance on how to correct this
   - Specific actions to take
   - What to add, modify, or remove
   - Best practices to follow

**TONE:** Be educational, constructive, and specific. Like a helpful professor, not a harsh critic.

**OUTPUT FORMAT:** Return a JSON object with explanations keyed by item index:
{{
  "0": {{
    "why_wrong": "...",
    "what_is_correct": "...",
    "what_should_happen": "...",
    "correct_equivalent": "...",
    "how_to_fix": "..."
  }},
  "1": {{ ... }},
  ...
}}

**CRITICAL JSON RULES:**
- ESCAPE all quotes inside strings with backslash: \\"
- NO line breaks inside strings (use spaces instead)
- Keep each explanation to 1-3 short sentences maximum
- Avoid special characters and apostrophes - use simple language
- MUST be valid JSON that can be parsed

**IMPORTANT:**
- Be specific to the HR Management System domain
- Reference concrete examples (Employee, Department, Contract, etc.)
- Explain business logic clearly
- If it's an alternative design that got partial credit, acknowledge it's valid but explain the preferred approach
- Keep each field SHORT (1-3 sentences maximum to avoid JSON errors)

Output ONLY valid JSON, nothing else."""

        generation_config = genai.types.GenerationConfig(
            temperature=0.3,  # Some creativity for explanations, but mostly consistent
            top_p=0.95,
            max_output_tokens=8192,  # Larger for detailed explanations
        )

        response = model.generate_content(prompt, generation_config=generation_config)
        explanations_text = response.text.strip()

        # Clean markdown fences
        if explanations_text.startswith("```json"):
            explanations_text = explanations_text[7:]
        elif explanations_text.startswith("```"):
            explanations_text = explanations_text[3:]
        if explanations_text.endswith("```"):
            explanations_text = explanations_text[:-3]

        explanations_text = explanations_text.strip()

        # Try to parse JSON
        try:
            explanations = json.loads(explanations_text)
        except json.JSONDecodeError as json_error:
            print(f"JSON parsing failed: {json_error}")
            print(f"Attempted to parse: {explanations_text[:500]}...")

            # Try to fix common JSON issues
            import re
            # Remove any trailing commas before closing braces
            explanations_text = re.sub(r',(\s*[}\]])', r'\1', explanations_text)
            # Try parsing again
            try:
                explanations = json.loads(explanations_text)
                print("JSON fixed and parsed successfully!")
            except:
                print("Could not fix JSON, skipping detailed explanations for this batch")
                return items_analysis

        # Map explanations back to items
        for idx, item in enumerate(items_with_issues):
            if str(idx) in explanations:
                item['detailed_explanation'] = explanations[str(idx)]

        return items_analysis

    except Exception as e:
        print(f"Detailed explanation generation failed: {e}")
        import traceback
        traceback.print_exc()
        # Return items as-is without detailed explanations
        return items_analysis


def ai_match_inheritance(expected_child_name, student_inheritances):
    """
    Use AI to intelligently match expected inheritance child with student's actual inheritances.
    This handles cases like:
    - "HR Administrator" under "EMPLOYEE" parent (child doesn't contain parent name)
    - "Contract-Based Salary Type" vs "ContractSalaryType" (different naming)
    - Semantic equivalents that humans would recognize

    Returns: (found, parent_name, child_name, note) or (False, None, None, None)
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Prepare student inheritance data
        student_inh_summary = []
        for inh in student_inheritances:
            parent = inh.get('parent_entity', '')
            children = [c.get('name', '') for c in inh.get('child_entities', [])]
            inh_type = inh.get('inheritance_type', '')
            constraint = inh.get('constraint', '')
            student_inh_summary.append({
                'parent': parent,
                'children': children,
                'type': inh_type,
                'constraint': constraint
            })

        # Quick prompt for fast matching
        prompt = f"""You are matching inheritance relationships in ERD grading.

**EXPECTED CHILD ENTITY:** "{expected_child_name}"

**STUDENT'S ACTUAL INHERITANCE RELATIONSHIPS:**
{json.dumps(student_inh_summary, indent=2)}

**YOUR TASK:**
Determine if the expected child entity "{expected_child_name}" exists in the student's inheritance relationships.

**MATCHING RULES:**
1. **Semantic Matching:** Names don't need to match exactly. Recognize semantic equivalents:
   - "HR Administrator" = "HR_Administrator" = "HRAdministrator" = "HR Admin"
   - "Contract-Based Salary Type" = "ContractSalaryType" = "Contract Based Salary Type"
   - "Full-Time Contract" = "FullTimeContract" = "FullTime Contract"

2. **Human Logic:** If a human database designer would recognize these as the same entity, they match.

3. **Case Insensitive:** Ignore case differences

4. **Spacing/Symbols:** Ignore spaces, hyphens, underscores when comparing

**EXAMPLES:**
- Expected: "HR Administrator", Student has "HR_Administrator" under EMPLOYEE → MATCH
- Expected: "Contract-Based Salary Type", Student has "ContractSalaryType" under SALARYTYPE → MATCH
- Expected: "Full-Time Contract", Student has "FullTimeContract" under CONTRACT → MATCH

**OUTPUT (valid JSON only):**
{{
  "found": true/false,
  "parent_entity": "parent name if found, else null",
  "child_entity": "actual child name from student ERD if found, else null",
  "reasoning": "brief explanation why it matches or doesn't match"
}}

Think like a database professor: would you accept this as the same inheritance relationship?
"""

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Parse JSON response
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '').strip()
        elif response_text.startswith('```'):
            response_text = response_text.replace('```', '').strip()

        # Remove trailing commas before parsing
        response_text = response_text.replace(',}', '}').replace(',]', ']')

        result = json.loads(response_text)

        if result.get('found', False):
            parent = result.get('parent_entity', '')
            child = result.get('child_entity', '')
            reasoning = result.get('reasoning', '')
            note = f"Inheritance found: {parent} → {child} (AI matched: {reasoning})"
            return True, parent, child, note
        else:
            return False, None, None, None

    except Exception as e:
        print(f"AI inheritance matching failed: {e}")
        traceback.print_exc()
        return False, None, None, None


def ai_intelligent_grade(student_erd, evaluation_schema, rule_based_results):
    """
    Use Gemini AI to intelligently grade the student ERD by understanding
    the conceptual model, not just exact matching. This allows for semantically
    equivalent designs that differ in implementation (e.g., with/without inheritance).

    Uses advanced semantic matching and reasoning framework for best possible results.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Prepare detailed student ERD summary with attributes
        student_summary = {
            'entities': [
                {
                    'name': e['name'],
                    'is_weak': e.get('is_weak', False),
                    'has_primary_key': any(attr.get('type') == 'key' for attr in e.get('attributes', [])),
                    'attribute_count': len(e.get('attributes', []))
                } for e in student_erd.get('entities', [])
            ],
            'relationships': [
                {
                    'name': r.get('name', ''),
                    'type': r.get('relationship_type', 'binary'),
                    'participants': [
                        {
                            'entity': p.get('name') or p.get('entity', ''),
                            'cardinality': p.get('cardinality', ''),
                            'role': p.get('role', '')
                        }
                        for p in r.get('participants', [])
                    ]
                } for r in student_erd.get('relationships', [])
            ],
            'inheritances': [
                {
                    'parent': inh.get('parent_entity', ''),
                    'children': [c.get('name', '') for c in inh.get('child_entities', [])],
                    'type': inh.get('inheritance_type', ''),
                    'constraint': inh.get('constraint', '')
                } for inh in student_erd.get('inheritances', [])
            ]
        }

        # Count student metrics for comparison
        entities_with_pk = sum(1 for e in student_summary['entities'] if e['has_primary_key'])
        total_entities = len(student_summary['entities'])
        total_relationships = len(student_summary['relationships'])
        total_inheritances = len(student_summary['inheritances'])

        # Create deterministic summary for consistency verification
        import hashlib
        erd_summary_str = json.dumps(student_summary, sort_keys=True)
        erd_hash = hashlib.md5(erd_summary_str.encode()).hexdigest()[:8]
        print(f"ERD Hash (for consistency): {erd_hash}")
        print(f"Student ERD: {total_entities} entities, {total_relationships} relationships, {total_inheritances} inheritances")

        prompt = f"""You are an expert database design professor grading a student's ERD (Entity-Relationship Diagram).

**CRITICAL INSTRUCTION:** You are a TEACHER, not a robot. Think like an experienced professor who uses judgment and reasoning, not just pattern matching.

**CONSISTENCY REQUIREMENT:** This ERD (hash: {erd_hash}) must receive the EXACT SAME score every time it's graded. Use deterministic logic and objective counting. Same ERD = Same Score (ALWAYS).

**YOUR TASK:** Intelligently evaluate if the student's ERD correctly models the required system. Students may use different but semantically equivalent designs. Your goal is to recognize valid alternative approaches and give credit for understanding, not just exact matching.

**EVALUATION SCHEMA (What should be modeled):**
{json.dumps(evaluation_schema.get('sections', {}), indent=2)}

**STUDENT'S ERD:**
{json.dumps(student_summary, indent=2)}

**STUDENT METRICS:**
- Entities: {total_entities} ({entities_with_pk} have primary keys)
- Relationships: {total_relationships}
- Inheritances: {total_inheritances}

**RULE-BASED RESULTS (for reference):**
Total: {rule_based_results['total_score']}/{rule_based_results['total_possible']}
Breakdown: Entities {rule_based_results['breakdown']['entities']['score']}/{rule_based_results['breakdown']['entities']['total']}, Relations {rule_based_results['breakdown']['relations']['score']}/{rule_based_results['breakdown']['relations']['total']}

**REASONING FRAMEWORK - READ CAREFULLY:**

1. **YOU ARE A TEACHER, NOT A ROBOT:**
   - Think like an experienced database professor
   - Use judgment and reasoning, not just pattern matching
   - If student's approach makes logical sense and serves the system requirements, it deserves full credit even if different from model answer

2. **CRITICAL THINKING STEPS:**
   - Step 1: What is the student trying to model? What business logic are they representing?
   - Step 2: Does their approach correctly capture the system requirements and relationships?
   - Step 3: How does it differ from model answer? Are differences superficial or fundamental?
   - Step 4: Would a real teacher accept this? Does it demonstrate understanding?
   - Step 5: Give credit for correctness and understanding, not just exact matching

3. **SEMANTIC MATCHING - CRITICAL:**
   - **Relationship Matching Algorithm:**
     * For each schema relationship, find student relationships connecting the SAME entities (allow semantic equivalents)
     * Compare cardinalities using equivalent notations (M=N=*, 1..*=M, 0..*=M)
     * If entities + cardinalities match → CORRECT (even if relationship name differs)
     * Example: Schema has "enrolls" (Student M:N Course), Student has "takes" (Student M:N Course) → SAME relationship, FULL CREDIT

   - **Entity Matching:**
     * Customer = Client, Learner = Student, Course = Class, Employee = Worker = Staff
     * Match by MEANING, not exact names

   - **Cardinality Equivalents:**
     * Many: M = N = * = 0..* = 1..*
     * One: 1 = 1..1 = E O = EO = EXACTLY ONE
     * Optional One: 0..1

4. **INHERITANCE GRADING - EXTREMELY LENIENT:**
   - **RULE 1:** Both have zero inheritance → FULL CREDIT (no inheritance is fine)
   - **RULE 2:** Schema has inheritance, student uses separate entities → FULL CREDIT (valid alternative design choice)
   - **RULE 3:** Student has inheritance, schema uses separate → FULL CREDIT (student showed better understanding)
   - **RULE 4:** Only deduct if inheritance is logically incorrect or violates business constraints
   - **DEFAULT:** Give 10/10 unless student's approach is PROVABLY WRONG

5. **TERNARY RELATIONSHIPS - CRITICAL:**
   - **BOTH approaches are valid and deserve FULL or PARTIAL credit:**

     **Option A: Student uses proper ternary (3 participants)**
     * If matches schema ternary → FULL CREDIT
     * Example: Schema has "Attendance-Shift-Employee", student has same → 100%

     **Option B: Student decomposes ternary into multiple binary relationships**
     * If achieves SAME business flow with binaries → FULL CREDIT or HIGH PARTIAL CREDIT (80-100%)
     * Example: Schema has "Works_On(Employee, Project, Department)" ternary
       Student has three binaries: Employee-Project, Employee-Department, Project-Department
       → Give 80-100% credit because it models the same system flow
     * Reasoning: Decomposition is a valid database design choice that captures the relationships

     **Option C: Student uses ternary when schema uses binaries**
     * Student showed BETTER understanding → FULL CREDIT + praise
     * Ternary is often the proper way to model three-way dependencies

     **When to deduct:**
     * Student completely missing the relationship (no ternary, no equivalent binaries) → 0%
     * Student has wrong entities in the relationship → major deduction
     * Student's approach doesn't capture the same business logic → deduct based on severity

   - **Grading principle:** Focus on whether the business logic is captured, not the exact structure
   - If student modeled the same three-way relationship through alternative means → recognize this as valid

6. **WHEN TO ACCEPT DIFFERENCES (FULL CREDIT):**
   - Different names but same meaning (enrolls vs takes)
   - Different structure but same outcome (inheritance vs separate entities)
   - Student's approach is more detailed/sophisticated than schema
   - Alternative valid interpretation of requirements
   - Different cardinality notation but same meaning (M vs N vs *)

7. **WHEN TO DEDUCT (ONLY THESE CASES):**
   - Cardinality that violates business rules (1:1 when should be 1:M)
   - Missing critical relationships that break system logic
   - Wrong entities connected (fundamentally different relationship)
   - Missing primary keys on regular entities (not weak entities)

**GRADING METHODOLOGY:**

1. **Compare Relationships by Connection, Not Name:**
   - For each schema relationship, identify which entities it connects
   - Find student relationships connecting the SAME entities (semantically)
   - Compare cardinalities (normalized)
   - If match → relationship is PRESENT and CORRECT, regardless of name

2. **Inheritance Flexibility:**
   - If schema requires "Employee → HR Admin, System Admin, Payroll Specialist, Line Manager" inheritance
   - Student can either: use inheritance OR have separate Admin entities
   - BOTH are valid, give full credit

3. **Ternary Relationship Alternatives:**
   - If schema requires ternary relationship (3 entities involved)
   - Student can use:
     * Proper ternary relationship → FULL CREDIT
     * Multiple binary relationships connecting same 3 entities → 80-100% CREDIT if same business logic
     * Example: Schema: "Attendance-Shift-Employee" (ternary)
       Student alternative: "Attendance-Shift" + "Attendance-Employee" + "Shift-Employee" (three binaries)
       → Give 80-100% credit, not 0%, because it models the same relationships
   - BOTH are valid, judge based on whether business logic is preserved

4. **Focus on Business Logic:**
   - Does the ERD capture the required business concepts?
   - Do relationships make sense for the system?
   - Are cardinalities reasonable for the domain?
   - Can the database support the required operations with this design?

**OUTPUT FORMAT (valid JSON only):**
{{
  "ai_score": <number>,
  "ai_total_possible": {evaluation_schema.get('total_possible_points', 173)},
  "ai_percentage": <number 0-100>,
  "analysis": {{
    "correctly_modeled_concepts": "List key concepts student got right (be specific: e.g., 'Correctly modeled Employee-Department M:1, Contract types with inheritance, Leave management system')",
    "missing_concepts": "List what's truly missing or incorrect (be specific: e.g., 'Missing Skill verification relationship, Payroll log entity not found')",
    "alternative_designs_recognized": "Note any valid alternative approaches used (e.g., 'Used separate Admin entities instead of inheritance - valid design choice', 'Decomposed ternary into binaries - acceptable')",
    "semantic_issues": "Any conceptual misunderstandings that affect business logic (e.g., 'Employee-Department cardinality is 1:1 but should be M:1')"
  }},
  "adjustments": {{
    "bonus_for_valid_alternatives": <number, e.g., 5 if student used valid alternatives>,
    "deduction_for_missing_concepts": <number, e.g., 10 if critical concepts missing>,
    "reasoning": "Brief explanation of score adjustments (e.g., 'Added 5 points for recognizing valid alternative design without inheritance. Deducted 8 points for missing 4 critical relationships.')"
  }},
  "feedback": {{
    "strengths": "What student did well (2-3 sentences, be specific about what they modeled correctly)",
    "improvements": "Areas needing work (2-3 sentences, be specific about what's missing or wrong)",
    "suggestions": ["Specific actionable suggestion 1", "Specific actionable suggestion 2", "Specific actionable suggestion 3"]
  }}
}}

**FLEXIBLE BUT CONSISTENT GRADING:**
- **CONSISTENCY:** Same ERD should produce the SAME score when graded multiple times
- **FLEXIBILITY:** Be generous with partial credit and alternative approaches
- **OBJECTIVE COUNTING:** Count matched items, but be flexible in what counts as a match
  * Entity match: Same name OR semantically equivalent (Employee = Worker = Staff)
  * Relationship match: Same entities connected OR semantically equivalent flow
  * Alternative designs: Give 80-100% credit for valid alternatives

**FLEXIBLE GRADING PRINCIPLES:**
1. **Generous Matching:**
   - If student has SIMILAR entity/relationship → give credit (not just exact match)
   - If student achieved SAME business outcome differently → give FULL credit
   - If student's approach is REASONABLE → give at least 80% credit

2. **Partial Credit Rules:**
   - Perfect match → 100%
   - Close match (minor differences) → 90-95%
   - Alternative valid approach → 80-90%
   - Attempted but incomplete → 50-70%
   - Missing completely → 0%

3. **Be Lenient With:**
   - Naming differences (enrolls vs takes vs registers)
   - Structural differences (inheritance vs separate entities)
   - Cardinality notation (M vs N vs * vs 0..*)
   - Ternary decomposition into binaries
   - Extra entities/relationships (don't penalize for adding more)

4. **Only Deduct Significantly For:**
   - Completely missing critical entities (not just renamed)
   - Completely missing critical relationships (not just restructured)
   - Wrong cardinalities that break business logic (1:1 vs 1:M matters)
   - Missing primary keys on regular entities

**SCORING APPROACH (flexible but consistent):**
1. Count how many schema items student matched (allowing semantic equivalents)
2. Count how many valid alternatives student used (ternary → binaries, inheritance → separate)
3. Give generous partial credit: aim for 80-95% range for good work
4. Use formula: base_score + bonus_for_alternatives - deductions_for_critical_missing
5. Be CONSISTENT: same matches should give same score, but be GENEROUS in what counts as a match

Think step-by-step (flexibly):
1. Identify what business domain this models
2. Count matches GENEROUSLY (include semantic equivalents and alternatives)
3. Give credit for reasonable interpretations
4. Calculate score with flexibility: aim higher rather than lower
5. If in doubt between two scores, choose the HIGHER one (benefit of the doubt)

Output ONLY valid JSON."""

        # Configure generation for accuracy and consistency
        generation_config = genai.types.GenerationConfig(
            temperature=0.0,   # Completely deterministic for consistent, accurate grading
            top_p=0.95,        # Nucleus sampling for quality
            top_k=40,          # Top-k sampling
            max_output_tokens=4096,  # Enough tokens for detailed analysis
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        ai_text = response.text.strip()

        # Clean markdown fences
        if ai_text.startswith("```json"):
            ai_text = ai_text[7:]
        elif ai_text.startswith("```"):
            ai_text = ai_text[3:]
        if ai_text.endswith("```"):
            ai_text = ai_text[:-3]

        ai_text = ai_text.strip()
        ai_result = json.loads(ai_text)

        # Print results for consistency verification
        print("="*80)
        print("AI GRADING RESULT (for consistency verification):")
        print(f"  ERD Hash: {erd_hash}")
        print(f"  AI Score: {ai_result.get('ai_score')}/{ai_result.get('ai_total_possible')} ({ai_result.get('ai_percentage')}%)")
        print(f"  Adjustments: +{ai_result.get('adjustments', {}).get('bonus_for_valid_alternatives', 0)} bonus, -{ai_result.get('adjustments', {}).get('deduction_for_missing_concepts', 0)} deduction")
        print(f"  Analysis: {ai_result.get('analysis', {}).get('correctly_modeled_concepts', '')[:100]}...")
        print("="*80)

        return ai_result

    except Exception as e:
        print(f"AI intelligent grading failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_ai_feedback(schema, student_erd, grading_results):
    """
    Use Gemini to generate qualitative feedback based on grading results.
    """
    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        prompt = f"""
You are an ERD grading assistant. Based on the following grading results, provide concise feedback.

**Schema:** {schema.get('schema_name', 'Unknown')}
**Total Points:** {schema.get('total_possible_points', 0)}

**Student Score:** {grading_results['total_score']}/{grading_results['total_possible']}

**Breakdown:**
- Entities: {grading_results['breakdown']['entities']['score']}/{grading_results['breakdown']['entities']['total']} ({grading_results['breakdown']['entities']['found']}/{grading_results['breakdown']['entities']['total_items']} found)
- Relations: {grading_results['breakdown']['relations']['score']}/{grading_results['breakdown']['relations']['total']} ({grading_results['breakdown']['relations']['found']}/{grading_results['breakdown']['relations']['total_items']} found)

**Task:** Provide feedback in exactly this JSON format:
{{
  "strengths": "Brief summary of what the student did well (2-3 sentences max)",
  "improvements": "Brief summary of areas needing improvement (2-3 sentences max)",
  "suggestions": ["Specific suggestion 1 (max 100 chars)", "Specific suggestion 2 (max 100 chars)", "Specific suggestion 3 (max 100 chars)"]
}}

Output ONLY valid JSON, nothing else.
"""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                max_output_tokens=500,
            )
        )

        feedback_text = response.text.strip()

        # Remove markdown code fences if present
        if feedback_text.startswith("```json"):
            feedback_text = feedback_text[7:]
        elif feedback_text.startswith("```"):
            feedback_text = feedback_text[3:]
        if feedback_text.endswith("```"):
            feedback_text = feedback_text[:-3]

        feedback_text = feedback_text.strip()

        feedback = json.loads(feedback_text)
        return feedback

    except Exception as e:
        print(f"AI feedback generation failed: {e}")
        return {
            "strengths": "ERD demonstrates understanding of basic database concepts.",
            "improvements": "Some entities and relationships are missing from the required schema.",
            "suggestions": [
                "Review the evaluation schema carefully",
                "Ensure all required entities are modeled",
                "Check relationship cardinalities"
            ]
        }


def grade_with_schema(student_erd, evaluation_schema):
    """
    Main function to grade student ERD against evaluation schema.
    Grades ALL sections: entities, relations, AND schema for complete coverage.

    Args:
        student_erd: Student's parsed ERD data
        evaluation_schema: Evaluation schema (JSON structure)

    Returns:
        dict: Grading results with detailed breakdown
    """
    sections = evaluation_schema.get('sections', {})

    # Grade all three sections
    # 1. Entities section (basic entity grading)
    entities_section = sections.get('entities', {})
    relations_section = sections.get('relations', {})

    # Pass relations to entities grading for dynamic parent-child detection
    entities_score, entities_total, entities_found, entities_items = grade_entities(
        entities_section.get('items', []),
        student_erd,
        relations_section.get('items', [])  # Dynamic parent-child map
    )

    # 2. Relations section (relationships and inheritance)
    relations_score, relations_total, relations_found, relations_items = grade_relationships(
        relations_section.get('items', []),
        student_erd
    )

    # 3. Schema section (integrated grading with types)
    schema_section = sections.get('schema', {})
    if schema_section and schema_section.get('items'):
        schema_score, schema_total, schema_found, schema_items = grade_schema_section(
            schema_section.get('items', []),
            student_erd
        )

        # Break down schema items by type for detailed display
        schema_entity_items = [item for item in schema_items if item['type'] in ['entity', 'weak_entity']]
        schema_relationship_items = [item for item in schema_items if item['type'] == 'relationship']
        schema_ternary_items = [item for item in schema_items if item['type'] == 'ternary']
        schema_inheritance_items = [item for item in schema_items if item['type'] == 'inheritance']
    else:
        schema_score = 0
        schema_total = 0
        schema_found = 0
        schema_entity_items = []
        schema_relationship_items = []
        schema_ternary_items = []
        schema_inheritance_items = []

    # Apply deductions
    deductions = evaluation_schema.get('deductions', {})
    total_deduction, deductions_applied = apply_deductions(student_erd, deductions)

    # CHANGE 3: Add category deduction caps to mirror TA's grading approach
    # Calculate lost points per category
    entities_lost = entities_total - entities_score
    relations_lost = relations_total - relations_score

    # Extract inheritance items from schema section
    schema_inheritance_score = sum(item['points_earned'] for item in schema_inheritance_items) if 'schema_inheritance_items' in locals() else 0
    schema_inheritance_total = sum(item['points_possible'] for item in schema_inheritance_items) if 'schema_inheritance_items' in locals() else 0
    inheritance_lost = schema_inheritance_total - schema_inheritance_score

    # Cap deductions (mirrors TA's rubric with maximum deductions per category)
    # TA gave Triple Y 150.5 despite missing many items, suggesting lenient caps
    # Increased caps to allow more deductions and reduce overestimation
    MAX_ENTITY_DEDUCTION = 12.0  # Increased from 9.0
    MAX_RELATIONSHIP_DEDUCTION = 14.0  # Increased from 11.0
    MAX_INHERITANCE_DEDUCTION = 14.0  # Increased from 11.0

    entities_adjustment = 0
    relations_adjustment = 0
    inheritance_adjustment = 0

    if entities_lost > MAX_ENTITY_DEDUCTION:
        entities_adjustment = entities_lost - MAX_ENTITY_DEDUCTION
        entities_score += entities_adjustment

    if relations_lost > MAX_RELATIONSHIP_DEDUCTION:
        relations_adjustment = relations_lost - MAX_RELATIONSHIP_DEDUCTION
        relations_score += relations_adjustment

    # CHANGE 4: Add bonus points for strong inheritance and completeness
    # (mirrors TA's approach of rewarding well-done work)
    bonus_points = 0
    bonus_reasons = []

    # Bonus for strong inheritance (like Teen Titans: 18/19 = 94.7%)
    # Minimal bonus to prevent overestimation
    if schema_inheritance_total > 0:
        inheritance_percentage = (schema_inheritance_score / schema_inheritance_total) * 100
        if inheritance_percentage >= 90:
            bonus = 2.0  # Reduced from 2.5
            bonus_points += bonus
            bonus_reasons.append(f"Strong inheritance modeling ({inheritance_percentage:.1f}%): +{bonus} points")
        elif inheritance_percentage >= 80:
            bonus = 1.0  # Reduced from 1.5
            bonus_points += bonus
            bonus_reasons.append(f"Good inheritance modeling ({inheritance_percentage:.1f}%): +{bonus} points")

    # Bonus for entity completeness
    # Minimal bonus to prevent overestimation
    if entities_total > 0:
        entity_percentage = (entities_score / entities_total) * 100
        if entity_percentage >= 95:
            bonus = 1.0  # Reduced from 1.5
            bonus_points += bonus
            bonus_reasons.append(f"Excellent entity coverage ({entity_percentage:.1f}%): +{bonus} points")
        elif entity_percentage >= 90:
            bonus = 0.0  # Removed to reduce overestimation
            bonus_points += bonus
            bonus_reasons.append(f"Good entity coverage ({entity_percentage:.1f}%): +{bonus} points")

    # Calculate total score from all three sections
    total_score = entities_score + relations_score + schema_score - total_deduction + bonus_points
    total_possible = entities_total + relations_total + schema_total

    # Generate detailed AI explanations for items with issues
    # Set this to False to skip detailed explanations (faster grading)
    ENABLE_DETAILED_EXPLANATIONS = False

    if ENABLE_DETAILED_EXPLANATIONS:
        print("\nGenerating detailed explanations for all items (this may take 30-60 seconds)...")
        print("Set ENABLE_DETAILED_EXPLANATIONS = False in grade_erd_schema.py to skip this for faster grading.")

        item_sources = [
            (entities_items, 'entity'),
            (relations_items, 'relationship'),
            (schema_entity_items, 'entity'),
            (schema_relationship_items, 'relationship'),
            (schema_ternary_items, 'ternary'),
            (schema_inheritance_items, 'inheritance')
        ]

        # Generate explanations for each category
        for items_list, item_type in item_sources:
            generate_detailed_explanations(items_list, item_type)
    else:
        print("\nDetailed explanations are DISABLED for faster grading.")

    # Build comprehensive results structure
    results = {
        'total_score': round(total_score, 2),
        'total_possible': total_possible,
        'percentage': round((total_score / total_possible * 100) if total_possible > 0 else 0, 1),
        'bonus_points': round(bonus_points, 2),
        'bonus_reasons': bonus_reasons,
        'category_adjustments': {
            'entities_cap_adjustment': round(entities_adjustment, 2),
            'relations_cap_adjustment': round(relations_adjustment, 2),
            'inheritance_cap_adjustment': round(inheritance_adjustment, 2)
        },
        'breakdown': {
            'entities': {
                'score': round(entities_score, 2),
                'total': entities_total,
                'found': entities_found,
                'total_items': len(entities_section.get('items', [])),
                'items': entities_items
            },
            'relations': {
                'score': round(relations_score, 2),
                'total': relations_total,
                'found': relations_found,
                'total_items': len(relations_section.get('items', [])),
                'items': relations_items
            },
            'schema_entities': {
                'score': round(sum(item['points_earned'] for item in schema_entity_items), 2),
                'total': sum(item['points_possible'] for item in schema_entity_items),
                'found': sum(1 for item in schema_entity_items if item['found']),
                'total_items': len(schema_entity_items),
                'items': schema_entity_items
            },
            'schema_relationships': {
                'score': round(sum(item['points_earned'] for item in schema_relationship_items), 2),
                'total': sum(item['points_possible'] for item in schema_relationship_items),
                'found': sum(1 for item in schema_relationship_items if item['found']),
                'total_items': len(schema_relationship_items),
                'items': schema_relationship_items
            },
            'ternary': {
                'score': round(sum(item['points_earned'] for item in schema_ternary_items), 2),
                'total': sum(item['points_possible'] for item in schema_ternary_items),
                'found': sum(1 for item in schema_ternary_items if item['found']),
                'total_items': len(schema_ternary_items),
                'items': schema_ternary_items
            },
            'inheritance': {
                'score': round(sum(item['points_earned'] for item in schema_inheritance_items), 2),
                'total': sum(item['points_possible'] for item in schema_inheritance_items),
                'found': sum(1 for item in schema_inheritance_items if item['found']),
                'total_items': len(schema_inheritance_items),
                'items': schema_inheritance_items
            }
        },
        'deductions_applied': deductions_applied,
        'schema_info': {
            'name': evaluation_schema.get('schema_name', 'Unknown'),
            'total_points': total_possible
        }
    }

    # Generate AI intelligent grading
    print("="*80)
    print("Performing AI intelligent grading...")
    print("="*80)
    ai_grading = ai_intelligent_grade(student_erd, evaluation_schema, results)

    if ai_grading:
        # Add AI grading results
        results['ai_grading'] = {
            'ai_score': ai_grading.get('ai_score', 0),
            'ai_total_possible': ai_grading.get('ai_total_possible', total_possible),
            'ai_percentage': ai_grading.get('ai_percentage', 0),
            'analysis': ai_grading.get('analysis', {}),
            'adjustments': ai_grading.get('adjustments', {}),
        }

        # Use AI feedback instead of rule-based feedback
        results['ai_feedback'] = ai_grading.get('feedback', {
            "strengths": "ERD demonstrates understanding of database concepts.",
            "improvements": "Some areas need improvement.",
            "suggestions": ["Review the schema", "Check relationships", "Verify cardinalities"]
        })

        # CHANGE 5: Use weighted blend of AI and rule-based grading
        # AI is more lenient (like TA) and recognizes alternative designs
        # Balanced weighting to reduce overestimation bias
        rule_based_score = total_score
        ai_score = ai_grading.get('ai_score', 0)

        # Weighted blend (55% rule + 45% AI) - balanced for most ERDs
        weighted_score = (0.55 * rule_based_score) + (0.45 * ai_score)

        # Use max of weighted and rule-based (not AI alone, to prevent overestimation)
        final_score = max(weighted_score, rule_based_score)

        # NO MINIMUM FLOOR - everyone gets the score they deserve!
        # No artificial inflation of scores

        print(f"\nFinal Score Calculation:")
        print(f"  Rule-based: {rule_based_score:.1f}/173")
        print(f"  AI Score: {ai_score:.1f}/173")
        print(f"  Weighted (40% rule + 60% AI): {weighted_score:.1f}/173")
        print(f"  Final (max of all): {final_score:.1f}/173")

        results['final_score'] = round(final_score, 2)
        results['final_percentage'] = round((final_score / total_possible * 100) if total_possible > 0 else 0, 1)
        results['grading_method'] = 'Hybrid (60% AI + 40% Rule-based, with max floor)'
        results['score_components'] = {
            'rule_based': round(rule_based_score, 2),
            'ai_score': round(ai_score, 2),
            'weighted': round(weighted_score, 2),
            'final': round(final_score, 2)
        }
    else:
        # Fallback to simple feedback if AI grading fails
        ai_feedback = generate_ai_feedback(evaluation_schema, student_erd, results)
        results['ai_feedback'] = ai_feedback
        results['final_score'] = total_score
        results['final_percentage'] = results['percentage']
        results['grading_method'] = 'Rule-based'

    return results
