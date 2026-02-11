#!/usr/bin/env python3
"""
Alternative AI Grading Approach:
Only analyze MISSING components and check if student has valid alternatives.
"""
import json
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


def find_missing_components(rule_based_result):
    """
    Extract all missing components from rule-based grading.
    Returns a structured list of missing items.
    """
    missing_components = {
        'entities': [],
        'relationships': [],
        'inheritance': [],
        'weak_entities': [],
        'ternary': []
    }

    # Check entities section
    if 'entities' in rule_based_result.get('breakdown', {}):
        for item in rule_based_result['breakdown']['entities']['items']:
            if not item['found']:
                missing_components['entities'].append({
                    'name': item['name'],
                    'points': item['points_possible'],
                    'note': item.get('note', '')
                })

    # Check relationships section
    if 'relations' in rule_based_result.get('breakdown', {}):
        for item in rule_based_result['breakdown']['relations']['items']:
            if not item['found']:
                # Categorize by type
                if 'inheritance' in item.get('note', '').lower():
                    missing_components['inheritance'].append({
                        'name': item['name'],
                        'points': item['points_possible'],
                        'note': item.get('note', '')
                    })
                else:
                    missing_components['relationships'].append({
                        'name': item['name'],
                        'points': item['points_possible'],
                        'note': item.get('note', '')
                    })

    # Check schema sections
    for section_name in ['schema_entities', 'schema_relationships', 'ternary', 'inheritance']:
        if section_name in rule_based_result.get('breakdown', {}):
            for item in rule_based_result['breakdown'][section_name]['items']:
                if not item['found']:
                    item_type = item.get('type', 'unknown')

                    if item_type == 'weak_entity':
                        missing_components['weak_entities'].append({
                            'name': item['name'],
                            'points': item['points_possible'],
                            'note': item.get('note', '')
                        })
                    elif item_type == 'ternary':
                        missing_components['ternary'].append({
                            'name': item['name'],
                            'points': item['points_possible'],
                            'note': item.get('note', '')
                        })
                    elif item_type == 'inheritance':
                        missing_components['inheritance'].append({
                            'name': item['name'],
                            'points': item['points_possible'],
                            'note': item.get('note', '')
                        })
                    elif item_type == 'entity':
                        missing_components['entities'].append({
                            'name': item['name'],
                            'points': item['points_possible'],
                            'note': item.get('note', '')
                        })
                    elif item_type == 'relationship':
                        missing_components['relationships'].append({
                            'name': item['name'],
                            'points': item['points_possible'],
                            'note': item.get('note', '')
                        })

    return missing_components


def ai_evaluate_missing_components(student_erd, missing_components, evaluation_schema):
    """
    Use AI to evaluate if student has valid alternatives for missing components.
    """
    # Prepare summary of student's ERD
    total_entities = len(student_erd.get('entities', []))
    total_relationships = len(student_erd.get('relationships', []))
    total_inheritances = len(student_erd.get('inheritances', []))

    # Create detailed student ERD summary
    student_summary = {
        'entities': [e.get('name', '') for e in student_erd.get('entities', [])],
        'relationships': [
            {
                'name': r.get('name', ''),
                'type': r.get('relationship_type', 'binary'),
                'participants': [p.get('name', p.get('entity', '')) for p in r.get('participants', [])]
            }
            for r in student_erd.get('relationships', [])
        ],
        'inheritances': [
            {
                'parent': inh.get('parent_entity', ''),
                'children': [c.get('name', '') for c in inh.get('child_entities', [])],
                'type': inh.get('inheritance_type', '')
            }
            for inh in student_erd.get('inheritances', [])
        ]
    }

    # Build the prompt
    prompt = f"""You are evaluating a student's ERD (Entity-Relationship Diagram) for a database design course.

**Your Task:**
The student's ERD was compared against a reference schema, and several components were found to be MISSING.
However, the student may have implemented VALID ALTERNATIVE modeling approaches that fulfill the same conceptual purpose.

**For each missing component below:**
1. Analyze if the student implemented a valid alternative approach
2. If a valid alternative exists, mark it as "SATISFIED" and award the full points
3. If no valid alternative exists, mark it as "MISSING" and deduct the points

**Valid Alternatives Include:**
- Using parent entity instead of child entities (e.g., "Leave" instead of "Vacation Leave", "Sick Leave")
- Using separate entities instead of inheritance (e.g., separate "Manager" entity instead of Employee→Manager inheritance)
- Using binary relationships instead of ternary (e.g., three binary relationships instead of one ternary)
- Using attributes instead of entities (e.g., "leave_type" attribute instead of separate Leave entities)
- Using different relationship types that achieve the same purpose
- Using weak entities vs strong entities with dependencies
- Any other semantically equivalent design choice

**Student's ERD Summary:**
- Total Entities: {total_entities}
- Total Relationships: {total_relationships}
- Total Inheritances: {total_inheritances}

**Entities:** {', '.join(student_summary['entities'][:50])}...

**Relationships:**
{json.dumps(student_summary['relationships'][:30], indent=2)}

**Inheritances:**
{json.dumps(student_summary['inheritances'], indent=2)}

**MISSING COMPONENTS TO EVALUATE:**

**Missing Entities ({len(missing_components['entities'])}):**
{json.dumps(missing_components['entities'], indent=2)}

**Missing Relationships ({len(missing_components['relationships'])}):**
{json.dumps(missing_components['relationships'], indent=2)}

**Missing Inheritance ({len(missing_components['inheritance'])}):**
{json.dumps(missing_components['inheritance'], indent=2)}

**Missing Weak Entities ({len(missing_components['weak_entities'])}):**
{json.dumps(missing_components['weak_entities'], indent=2)}

**Missing Ternary Relationships ({len(missing_components['ternary'])}):**
{json.dumps(missing_components['ternary'], indent=2)}

**INSTRUCTIONS:**
For EACH missing component, respond with a JSON object in this exact format:

{{
  "evaluations": [
    {{
      "component_name": "Vacation Leave",
      "component_type": "entity",
      "status": "SATISFIED",
      "reasoning": "Student has parent entity 'Leave' which can represent all leave types through attributes or inheritance. This is a valid alternative design.",
      "points_awarded": 1.0,
      "points_possible": 1.0,
      "alternative_found": "Parent entity 'Leave' exists"
    }},
    {{
      "component_name": "Employee - Skill M:N",
      "component_type": "relationship",
      "status": "MISSING",
      "reasoning": "No relationship exists between Employee and Skill entities. This is a critical missing relationship.",
      "points_awarded": 0.0,
      "points_possible": 1.0,
      "alternative_found": null
    }}
  ],
  "summary": {{
    "total_missing": 15,
    "satisfied_by_alternatives": 8,
    "truly_missing": 7,
    "total_points_recovered": 8.5,
    "total_points_lost": 6.5
  }}
}}

**IMPORTANT:**
- Be LENIENT when recognizing alternatives
- Different designs can be equally valid
- Focus on whether the student captured the CONCEPT, not the exact structure
- Award full points if a valid alternative exists
- Use temperature=0.0 for consistent grading
- Respond ONLY with valid JSON, no additional text

Now evaluate:
"""

    try:
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        generation_config = genai.types.GenerationConfig(
            temperature=0.0,  # Deterministic
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )

        # Parse JSON response
        response_text = response.text.strip()

        # Extract JSON if wrapped in markdown
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0].strip()
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0].strip()

        result = json.loads(response_text)

        return result

    except Exception as e:
        print(f"AI evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def grade_with_alternative_approach(student_erd, evaluation_schema, rule_based_result):
    """
    Main function: Grade using the alternative approach.

    1. Get missing components from rule-based grading
    2. Use AI to check if student has valid alternatives
    3. Award points for valid alternatives
    4. Calculate final score
    """
    print("\n" + "="*80)
    print("ALTERNATIVE GRADING APPROACH: Missing Component Analysis")
    print("="*80)

    # Step 1: Extract missing components
    missing_components = find_missing_components(rule_based_result)

    total_missing = (
        len(missing_components['entities']) +
        len(missing_components['relationships']) +
        len(missing_components['inheritance']) +
        len(missing_components['weak_entities']) +
        len(missing_components['ternary'])
    )

    print(f"\nMissing Components Detected:")
    print(f"  - Entities: {len(missing_components['entities'])}")
    print(f"  - Relationships: {len(missing_components['relationships'])}")
    print(f"  - Inheritance: {len(missing_components['inheritance'])}")
    print(f"  - Weak Entities: {len(missing_components['weak_entities'])}")
    print(f"  - Ternary: {len(missing_components['ternary'])}")
    print(f"  - TOTAL: {total_missing}")

    if total_missing == 0:
        print("\n✅ No missing components - student has everything!")
        return {
            'approach': 'alternative_missing_component_analysis',
            'missing_components': missing_components,
            'ai_evaluation': None,
            'points_recovered': 0,
            'points_lost': 0,
            'final_score': rule_based_result['total_score'],
            'final_possible': rule_based_result['total_possible']
        }

    # Step 2: AI evaluates missing components
    print(f"\n🤖 Sending {total_missing} missing components to AI for alternative analysis...")

    ai_evaluation = ai_evaluate_missing_components(student_erd, missing_components, evaluation_schema)

    if not ai_evaluation:
        print("⚠️ AI evaluation failed - using rule-based score")
        return {
            'approach': 'alternative_missing_component_analysis',
            'missing_components': missing_components,
            'ai_evaluation': None,
            'points_recovered': 0,
            'points_lost': 0,
            'final_score': rule_based_result['total_score'],
            'final_possible': rule_based_result['total_possible']
        }

    # Step 3: Calculate final score
    points_recovered = ai_evaluation['summary']['total_points_recovered']
    points_lost = ai_evaluation['summary']['total_points_lost']

    final_score = rule_based_result['total_score'] + points_recovered

    print(f"\n✅ AI Analysis Complete:")
    print(f"  - Valid alternatives found: {ai_evaluation['summary']['satisfied_by_alternatives']}/{total_missing}")
    print(f"  - Truly missing: {ai_evaluation['summary']['truly_missing']}/{total_missing}")
    print(f"  - Points recovered: +{points_recovered}")
    print(f"  - Points lost: -{points_lost}")
    print(f"  - Rule-based score: {rule_based_result['total_score']}/{rule_based_result['total_possible']}")
    print(f"  - Final score: {final_score}/{rule_based_result['total_possible']}")

    return {
        'approach': 'alternative_missing_component_analysis',
        'missing_components': missing_components,
        'ai_evaluation': ai_evaluation,
        'points_recovered': points_recovered,
        'points_lost': points_lost,
        'rule_based_score': rule_based_result['total_score'],
        'final_score': final_score,
        'final_possible': rule_based_result['total_possible'],
        'final_percentage': round((final_score / rule_based_result['total_possible'] * 100) if rule_based_result['total_possible'] > 0 else 0, 2)
    }
