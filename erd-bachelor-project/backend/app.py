import os
import tempfile
import json
from flask import Flask, request, jsonify, send_file, render_template_string
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv
from flask_cors import CORS  # <--- CHANGE 1: Import CORS

from svgToXml.convertion import svg_to_drawio_erd
from svgToXml.test import ERDParser
from gmlToDrawio import graphml_to_erd_json
from grade_erd_schema import grade_with_schema

load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY) 

app = Flask(__name__)

# --- CHANGE 2: Allow ANY frontend (Wildcard *) ---
CORS(app, resources={r"/*": {"origins": "*"}}) 

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB uploads
ALLOWED_EXT = {'svg', 'graphml', 'xml'}

# --- helpers ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def is_graphml_file(filename):
    """Check if file is a GraphML file"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'graphml', 'xml'}

def get_cardinality_type(card_str):
    """Helper to determine cardinality type from a label string."""
    if not card_str:
        return 'UNKNOWN'

    # Normalize the string
    card_upper = card_str.upper().strip()

    # Check for asterisk (*) which means many
    if '*' in card_upper:
        return 'MANY'

    # Check for 'M' or 'N' (Many)
    if card_upper in ['M', 'N'] or card_upper.startswith('M') or card_upper.startswith('N'):
        return 'MANY'

    # Check for patterns like "0..*", "1..*" (Many)
    if '..*' in card_upper:
        return 'MANY'

    # Check for '1' or patterns like "0..1" (One)
    if card_upper == '1' or card_upper == '0..1':
        return 'ONE'

    # Fallback: if contains 1, assume ONE; if contains M/N/*, assume MANY
    if '1' in card_upper:
        return 'ONE'
    if any(x in card_upper for x in ['M', 'N', '*']):
        return 'MANY'

    return 'UNKNOWN'

def serialize_parser(parser: ERDParser):
    """Convert parser objects into serializable dict for JSON / UI."""
    entities = []
    for e in parser.entities:
        entities.append({
            'name': e.name,
            'x': e.x,
            'y': e.y,
            'width': e.width,
            'height': e.height,
            'is_weak': e.is_weak,
            'is_associative': e.is_associative,
            'cell_id': e.cell_id,
            'attributes': [
                {
                    'name': a.name,
                    'x': a.x,
                    'y': a.y,
                    'type': a.type,
                    'cell_id': a.cell_id
                } for a in e.attributes
            ]
        })
    import re
    from html import unescape

    def clean_html(text):
        """Remove HTML tags and decode HTML entities from text"""
        if not text:
            return text
        clean = re.sub(r'<[^>]+>', '', str(text))
        clean = unescape(clean)
        return clean.strip()

    attribute_cell_ids = set(a.cell_id for a in parser.attributes)
    relationships = []
    for r in parser.relationships:
        participants = []
        for conn in parser.connections:
            if conn.source in attribute_cell_ids or conn.target in attribute_cell_ids:
                continue

            cardinality_str = conn.cardinality or ""
            source_cardinality = cardinality_str
            target_cardinality = cardinality_str

            if ':' in cardinality_str:
                parts = cardinality_str.split(':', 1)
                source_cardinality = parts[0].strip()
                target_cardinality = parts[1].strip() if len(parts) > 1 else ""

            if conn.source == r.cell_id:
                target_cell = parser.cell_map.get(conn.target)
                if target_cell:
                    participants.append({
                        'name': clean_html(target_cell.get('value', conn.target)),
                        'cardinality': target_cardinality,
                        'cell_id': conn.target
                    })
            elif conn.target == r.cell_id:
                source_cell = parser.cell_map.get(conn.source)
                if source_cell:
                    participants.append({
                        'name': clean_html(source_cell.get('value', conn.source)),
                        'cardinality': source_cardinality,
                        'cell_id': conn.source
                    })

        # Handle different numbers of participants
        if len(participants) == 1:
            # Unary relationship (self-referencing)
            p1 = participants[0]
            summary = f"**{p1['name']}** [{p1['cardinality']}] has a self-referencing relationship"

            relationships.append({
                'name': r.name,
                'x': r.x,
                'y': r.y,
                'width': r.width,
                'height': r.height,
                'is_identifying': r.is_identifying,
                'cell_id': r.cell_id,
                'relationship_type': 'unary',
                'participants': participants,
                'attributes': [
                    {'name': a.name, 'x': a.x, 'y': a.y, 'type': a.type, 'cell_id': a.cell_id} for a in r.attributes
                ],
                'connection_summary': summary
            })

        elif len(participants) == 2:
            # Binary relationship (normal case)
            p1 = participants[0]
            p2 = participants[1]
            type1 = get_cardinality_type(p1['cardinality'])
            type2 = get_cardinality_type(p2['cardinality'])
            rel_type = "relationship"
            if type1 == 'ONE' and type2 == 'ONE':
                rel_type = "One-to-One"
            elif type1 == 'ONE' and type2 == 'MANY':
                rel_type = "One-to-Many"
            elif type1 == 'MANY' and type2 == 'ONE':
                rel_type = "Many-to-One"
            elif type1 == 'MANY' and type2 == 'MANY':
                rel_type = "Many-to-Many"

            summary = f"**{p1['name']}** [{p1['cardinality']}] has a {rel_type} relationship with **{p2['name']}** [{p2['cardinality']}]"

            relationships.append({
                'name': r.name,
                'x': r.x,
                'y': r.y,
                'width': r.width,
                'height': r.height,
                'is_identifying': r.is_identifying,
                'cell_id': r.cell_id,
                'relationship_type': 'binary',
                'participants': participants,
                'attributes': [
                    {'name': a.name, 'x': a.x, 'y': a.y, 'type': a.type, 'cell_id': a.cell_id} for a in r.attributes
                ],
                'connection_summary': summary
            })

        elif len(participants) == 3:
            # Ternary relationship - keep as-is (no splitting)
            # Build entity list with arrows showing three-way connection
            entity1 = f"**{participants[0]['name']}** [{participants[0]['cardinality']}]"
            entity2 = f"**{participants[1]['name']}** [{participants[1]['cardinality']}]"
            entity3 = f"**{participants[2]['name']}** [{participants[2]['cardinality']}]"

            # Create visual representation of ternary relationship
            summary = f"3-way relationship:\n  • {entity1}\n  • {entity2}\n  • {entity3}"

            relationships.append({
                'name': r.name,
                'x': r.x,
                'y': r.y,
                'width': r.width,
                'height': r.height,
                'is_identifying': r.is_identifying,
                'cell_id': r.cell_id,
                'relationship_type': 'ternary',
                'participants': participants,
                'attributes': [
                    {'name': a.name, 'x': a.x, 'y': a.y, 'type': a.type, 'cell_id': a.cell_id} for a in r.attributes
                ],
                'connection_summary': summary
            })

        elif len(participants) > 3:
            # N-ary relationship (more than 3 participants)
            participant_parts = []
            for p in participants:
                participant_parts.append(f"**{p['name']}** [{p['cardinality']}]")

            # Create a clearer summary showing all participants
            summary = f"{len(participants)}-ary relationship connecting: {' ↔ '.join(participant_parts)}"

            relationships.append({
                'name': r.name,
                'x': r.x,
                'y': r.y,
                'width': r.width,
                'height': r.height,
                'is_identifying': r.is_identifying,
                'cell_id': r.cell_id,
                'relationship_type': 'n-ary',
                'participant_count': len(participants),
                'participants': participants,
                'attributes': [
                    {'name': a.name, 'x': a.x, 'y': a.y, 'type': a.type, 'cell_id': a.cell_id} for a in r.attributes
                ],
                'connection_summary': summary
            })

        else:
            # No participants found
            summary = "No entity connections found."
            relationships.append({
                'name': r.name,
                'x': r.x,
                'y': r.y,
                'width': r.width,
                'height': r.height,
                'is_identifying': r.is_identifying,
                'cell_id': r.cell_id,
                'attributes': [
                    {'name': a.name, 'x': a.x, 'y': a.y, 'type': a.type, 'cell_id': a.cell_id} for a in r.attributes
                ],
                'connection_summary': summary
            })
    attributes = []
    for a in parser.attributes:
        attributes.append({
            'name': a.name,
            'x': a.x,
            'y': a.y,
            'cell_id': a.cell_id,
            'type': a.type
        })
    connections = [] # Return empty list
    # Serialize inheritance/specialization data
    inheritances = []
    for inh in parser.inheritances:
        inheritances.append({
            'inheritance_type': inh.inheritance_type,
            'symbol': inh.get_type_symbol(),
            'parent_entity': inh.parent_entity,
            'parent_id': inh.parent_id,
            'child_entities': inh.child_entities,
            'x': inh.x,
            'y': inh.y,
            'cell_id': inh.cell_id
        })
    return {
        'entities': entities,
        'relationships': relationships,
        'attributes': attributes,
        'connections': connections,
        'inheritances': inheritances,
        'erd_description': parser.generate_erd_description()
    }

@app.route('/')
def index():
    client_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'client.html')
    if os.path.exists(client_path):
        return render_template_string(open(client_path, 'r', encoding='utf-8').read())
    return render_template_string("""
    <!doctype html><title>Upload SVG</title>
    <h3>Put client.html in the same folder to get the nicer UI — fallback here.</h3>
    <form method=post enctype=multipart/form-data action="/convert">
      <input type=file name=file accept=".svg">
      <input type=submit value=Upload>
    </form>
    """)

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part "file" in request'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(f.filename):
        return jsonify({'error': 'Only SVG files allowed (.svg)'}), 400
    filename = secure_filename(f.filename)
    tmp_dir = tempfile.mkdtemp(prefix='svg_convert_')
    svg_path = os.path.join(tmp_dir, filename)
    f.save(svg_path)
    xml_out = os.path.join(tmp_dir, filename.rsplit('.', 1)[0] + '.xml')
    try:
        result = svg_to_drawio_erd(svg_path, xml_out)
        if result is None:
            return jsonify({
                'error': 'No Draw.io data found',
                'message': 'This SVG file does not contain embedded Draw.io data. Please export your diagram from Draw.io with "Include a copy of my diagram" option enabled.'
            }), 400
    except Exception as e:
        return jsonify({'error': 'conversion error', 'message': str(e)}), 500

    try:
        with open(xml_out, 'r', encoding='utf-8') as fh:
            xml_content = fh.read()
    except FileNotFoundError:
        found = None
        for fentry in os.listdir(tmp_dir):
            if fentry.lower().endswith('.xml'):
                found = os.path.join(tmp_dir, fentry)
                break
        if not found:
            return jsonify({'error': 'Converted XML not found'}), 500
        with open(found, 'r', encoding='utf-8') as fh:
            xml_content = fh.read()
        xml_out = found

    try:
        parser = ERDParser(xml_content)
        parser.parse()
    except Exception as e:
        return jsonify({'error': 'parsing error', 'message': str(e)}), 500
    erd_json = serialize_parser(parser)
    with open(os.path.join(tmp_dir, 'erd.json'), 'w', encoding='utf-8') as jf:
        json.dump(erd_json, jf, indent=2, ensure_ascii=False)

    html = render_template_string("""
    <!doctype html>
    <html><head><meta charset="utf-8"><title>ERD Result</title>
    <style>
      body{font-family:Arial; padding:18px; background:#f7f9fc}
      .card{background:#fff;padding:18px;border-radius:8px;box-shadow:0 10px 30px rgba(0,0,0,0.06); margin-bottom:16px;}
      h1{margin-bottom:8px}
      .entity{border-left:4px solid #4f46e5;padding:12px;margin-bottom:10px;border-radius:4px;background:#fbfbff;}
      .attr{padding-left:10px}
      .download{display:inline-block;margin-right:8px;padding:8px 12px;background:#10b981;color:white;border-radius:6px;text-decoration:none}
    </style></head>
    <body>
    <div class="card">
      <h1>✅ Conversion & Parsing Completed</h1>
      <div>
        <a class="download" href="/download_xml?path={{xml_path}}">Download XML</a>
        <a class="download" href="/download_json?path={{json_path}}">Download ERD JSON</a>
        <a class="download" href="/">Upload another</a>
      </div>
    </div>
    <div class="card">
      <h2>ERD Summary</h2>
      <div style="margin-top:12px;">
        <h3>Entities ({{entities|length}})</h3>
        {% for e in entities %}
          <div class="entity">
            <strong>{{e.name}}</strong>
            {% if e.is_weak %}<span style="color:#b91c1c;margin-left:8px">[WEAK]</span>{% endif %}
            {% if e.is_associative %}<span style="color:#b91c1c;margin-left:8px">[ASSOCIATIVE]</span>{% endif %}
            <div class="attr">
              {% if e.attributes %}
                <ul>
                  {% for a in e.attributes %}
                    <li>{{ a.name }} {% if a.type == 'key' %} <strong>[PK]</strong> 🔑{% endif %}{% if a.type == 'multivalued' %} (Multivalued){% endif %}{% if a.type == 'derived' %} (Derived){% endif %}</li>
                  {% endfor %}
                </ul>
              {% else %}
                <em>No attributes found</em>
              {% endif %}
            </div>
          </div>
        {% endfor %}
      </div>
      <div style="margin-top:14px;">
        <h3>Relationships ({{relationships|length}})</h3>
        {% for r in relationships %}
          <div style="padding:10px;border-left:4px solid #f97316;background:#fff9f3;border-radius:6px;margin-bottom:8px;">
            <strong>{{r.name}}</strong>
            {% if r.is_identifying %}<span style="color:#6b21a8;margin-left:8px">[IDENTIFYING]</span>{% endif %}
            {% if r.connection_summary %}
              <div class="attr" style="margin-top:5px; color:#333;">
                {{ r.connection_summary | safe }}
              </div>
            {% endif %}
            {% if r.attributes %}
              <div class="attr" style="margin-top:5px;">
                <small>Attributes: {{ r.attributes | map(attribute='name') | join(', ') }}</small>
              </div>
            {% endif %}
          </div>
        {% endfor %}
      </div>
      <div style="margin-top:14px;">
        <h3>Inheritance/Specialization ({{inheritances|length}})</h3>
        {% if inheritances %}
          {% for inh in inheritances %}
            <div style="padding:10px;border-left:4px solid #8b5cf6;background:#f5f3ff;border-radius:6px;margin-bottom:8px;">
              <strong>[{{inh.symbol}}] {{inh.parent_entity}}</strong>
              <span style="color:#6b21a8;margin-left:8px">({{inh.inheritance_type|upper}})</span>
              <div class="attr" style="margin-top:5px; color:#333;">
                <strong>Subtypes:</strong> {{ inh.child_entities | map(attribute='name') | join(', ') }}
              </div>
            </div>
          {% endfor %}
        {% else %}
          <em>No inheritance/specialization hierarchies found</em>
        {% endif %}
      </div>
      <div style="margin-top:14px;">
        <h3>Structural Connections ({{connections|length}})</h3>
         <em>(Connections are now processed into Relationship summaries)</em>
      </div>
    </div>
    <div class="card">
      <h3>Generated ERD Description (Markdown)</h3>
      <pre style="white-space:pre-wrap;">{{ erd_description }}</pre>
    </div>
    </body></html>
    """,
    entities=erd_json['entities'],
    relationships=erd_json['relationships'],
    connections=erd_json['connections'],
    inheritances=erd_json.get('inheritances', []),
    erd_description=erd_json['erd_description'],
    xml_path=xml_out,
    json_path=os.path.join(tmp_dir, 'erd.json')
    )
    return html

@app.route('/download_xml')
def download_xml():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return "File not found.", 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path), mimetype='application/xml')

@app.route('/download_json')
def download_json():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return "File not found.", 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path), mimetype='application/json')

@app.route('/api/convert', methods=['POST'])
def api_convert():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded (field "file")'}), 400
    f = request.files['file']
    if not allowed_file(f.filename):
        return jsonify({'error': 'Only SVG, GraphML, or XML files allowed (.svg, .graphml, .xml)'}), 400

    tmp_dir = tempfile.mkdtemp(prefix='file_api_')
    file_path = os.path.join(tmp_dir, secure_filename(f.filename))
    f.save(file_path)

    # Check if it's a GraphML file
    if is_graphml_file(f.filename):
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as fh:
                file_content = fh.read()

            # Parse GraphML directly to ERD JSON
            erd_json = graphml_to_erd_json(file_content)

            if erd_json is None:
                return jsonify({
                    'error': 'GraphML parsing failed',
                    'message': 'Could not parse GraphML file. Please ensure it is a valid yEd GraphML file with ERD entities, attributes, and relationships.'
                }), 400

            print("="*80)
            print("START: ERD_JSON FROM /api/convert (GraphML)")
            print("="*80)
            print(json.dumps(erd_json, indent=2))
            print("="*80)
            print("END: ERD_JSON FROM /api/convert (GraphML)")
            print("="*80)

            return jsonify({'xml': None, 'erd': erd_json, 'source': 'graphml'})

        except Exception as e:
            return jsonify({'error': 'GraphML conversion failed', 'message': str(e)}), 500

    # Otherwise, process as SVG
    xml_out = os.path.join(tmp_dir, secure_filename(f.filename).rsplit('.',1)[0] + '.xml')

    try:
        result = svg_to_drawio_erd(file_path, xml_out)
        if result is None:
            return jsonify({
                'error': 'No Draw.io data found',
                'message': 'This SVG file does not contain embedded Draw.io data. Please export your diagram from Draw.io with "Include a copy of my diagram" option enabled.'
            }), 400
    except Exception as e:
        return jsonify({'error': 'conversion failed', 'message': str(e)}), 500

    try:
        xml_text = open(xml_out, 'r', encoding='utf-8').read()
    except Exception as e:
        return jsonify({'error': 'reading xml failed', 'message': str(e)}), 500

    try:
        parser = ERDParser(xml_text)
        parser.parse()
    except Exception as e:
        return jsonify({'error': 'parsing xml failed', 'message': str(e)}), 500

    # --- Debugging Prints ---
    print("="*80)
    print("START: RAW PARSER DATA (Before JSON serialization)")
    print("="*80)
    
    print("\n--- parser.entities ---")
    print(parser.entities) 
    
    print("\n--- parser.relationships ---")
    print(parser.relationships)

    print("\n--- parser.attributes ---")
    print(parser.attributes)
    
    print("\n--- parser.connections ---")
    print(parser.connections)
    
    print("="*80)
    print("END: RAW PARSER DATA")
    print("="*80)

    try:
        erd_json = serialize_parser(parser)
        print("="*80)
        print("START: ERD_JSON FROM /api/convert")
        print("="*80)
        print(json.dumps(erd_json, indent=2))
        print("="*80)
        print("END: ERD_JSON FROM /api/convert (SVG)")
        print("="*80)

        return jsonify({'xml': xml_text, 'erd': erd_json, 'source': 'svg'})

    except Exception as e:
        return jsonify({'error': 'Failed to serialize ERD data', 'message': str(e)}), 500

@app.route('/api/convert_to_structured', methods=['POST'])
def api_convert_to_structured():
    """Convert ERD to structured JSON format (for testing/debugging)"""
    try:
        data = request.get_json()
        if not data or 'erd' not in data:
            return jsonify({'error': 'Missing erd in request body'}), 400

        structured = convert_to_structured_format(data['erd'])
        return jsonify(structured)

    except Exception as e:
        return jsonify({'error': 'Conversion failed', 'message': str(e)}), 500

@app.route('/api/grade', methods=['POST'])
def api_grade():
    try:
        data = request.get_json()
        if not data or 'student_erd' not in data or 'teacher_erd' not in data:
            return jsonify({'error': 'Missing student_erd or teacher_erd in request body'}), 400

        student_erd = data['student_erd']
        teacher_erd = data['teacher_erd']
        custom_requirements = data.get('custom_requirements', None)  # Optional custom requirements

        grading_json = grade_erd_with_ai(student_erd, teacher_erd, custom_requirements)

        if "error" in grading_json:
            return jsonify(grading_json), 500

        return jsonify(grading_json)

    except Exception as e:
        return jsonify({'error': 'Grading failed', 'message': str(e)}), 500

@app.route('/api/grade_with_schema', methods=['POST'])
def api_grade_with_schema():
    """Grade student ERD using evaluation schema rubric"""
    try:
        data = request.get_json()
        if not data or 'student_erd' not in data or 'evaluation_schema' not in data:
            return jsonify({'error': 'Missing student_erd or evaluation_schema in request body'}), 400

        student_erd = data['student_erd']
        evaluation_schema = data['evaluation_schema']

        # Grade using schema
        grading_results = grade_with_schema(student_erd, evaluation_schema)

        return jsonify(grading_results)

    except Exception as e:
        return jsonify({'error': 'Schema-based grading failed', 'message': str(e)}), 500

def convert_to_structured_format(erd_data):
    """
    Convert ERD data to a structured JSON format optimized for LLM comparison.

    Returns a dictionary with:
    - entities: list of entities with attributes and their types
    - relationships: list of relationships with cardinality and relationship type
    - inheritances: list of inheritance hierarchies
    """
    structured_entities = []

    for entity in erd_data.get('entities', []):
        entity_dict = {
            'name': entity['name'],
            'type': []
        }

        # Add entity type flags
        if entity.get('is_weak'):
            entity_dict['type'].append('weak')
        if entity.get('is_associative'):
            entity_dict['type'].append('associative')
        if not entity_dict['type']:
            entity_dict['type'] = ['regular']

        # Add attributes with types
        entity_dict['attributes'] = []
        for attr in entity.get('attributes', []):
            attr_dict = {
                'name': attr['name'],
                'is_primary_key': attr.get('type') == 'key',
                'is_multivalued': attr.get('type') == 'multivalued',
                'is_derived': attr.get('type') == 'derived',
                'is_composite': attr.get('type') == 'composite'
            }
            entity_dict['attributes'].append(attr_dict)

        structured_entities.append(entity_dict)

    # Process relationships
    structured_relationships = []
    for rel in erd_data.get('relationships', []):
        rel_dict = {
            'name': rel['name'],
            'is_identifying': rel.get('is_identifying', False),
            'participants': [],
            'attributes': [{'name': a['name']} for a in rel.get('attributes', [])]
        }

        # Extract participants and cardinality from connection_summary
        summary = rel.get('connection_summary', '')

        # Parse participants - looking for pattern like "Entity1 [cardinality] ... Entity2 [cardinality]"
        import re
        from html import unescape

        participant_pattern = r'\*\*([^*]+)\*\*\s*\[([^\]]*)\]'
        matches = re.findall(participant_pattern, summary)

        for entity_name, cardinality in matches:
            # Clean entity name: remove HTML tags and decode HTML entities
            clean_name = re.sub(r'<[^>]+>', '', entity_name)  # Remove HTML tags
            clean_name = unescape(clean_name)  # Decode HTML entities like &nbsp;
            clean_name = clean_name.strip()  # Remove whitespace

            rel_dict['participants'].append({
                'entity': clean_name,
                'cardinality': cardinality.strip()
            })

        # Helper function to determine cardinality type
        def get_card_type(card):
            if not card:
                return 'unknown'
            card_upper = card.strip().upper()

            # Check for "many" indicators
            if 'M' in card_upper or 'N' in card_upper or '*' in card:
                return 'many'

            # Check for "one" indicators - be more specific to avoid false matches
            # 0..1 is still "one" (optional one)
            if card_upper in ['1', '0..1', 'E O', 'EO', 'ONE', 'EXACTLY ONE']:
                return 'one'

            # Check for ranges that indicate "one"
            if card_upper.startswith('0..1') or card_upper.startswith('1'):
                # But exclude "1..*" which means "many"
                if '..*' not in card_upper and 'MANY' not in card_upper:
                    return 'one'

            # Check for patterns like "1..*", "0..*" - these are "many"
            if '..*' in card_upper:
                return 'many'

            return 'unknown'

        # Determine relationship type from the relationship data itself or cardinalities
        # Check if relationship_type is already set in the source data
        if 'relationship_type' in rel and rel['relationship_type'] in ['unary', 'binary', 'ternary', 'n-ary']:
            rel_dict['relationship_type'] = rel['relationship_type']
        else:
            # Fallback: determine from participant count
            if len(rel_dict['participants']) == 1:
                # Unary relationship (self-referencing)
                rel_dict['relationship_type'] = 'unary'
            elif len(rel_dict['participants']) == 2:
                # Binary relationship - determine cardinality type
                card1 = rel_dict['participants'][0]['cardinality']
                card2 = rel_dict['participants'][1]['cardinality']

                type1 = get_card_type(card1)
                type2 = get_card_type(card2)

                if type1 == 'one' and type2 == 'one':
                    rel_dict['relationship_type'] = 'one-to-one'
                elif type1 == 'one' and type2 == 'many':
                    rel_dict['relationship_type'] = 'one-to-many'
                elif type1 == 'many' and type2 == 'one':
                    rel_dict['relationship_type'] = 'many-to-one'
                elif type1 == 'many' and type2 == 'many':
                    rel_dict['relationship_type'] = 'many-to-many'
                else:
                    rel_dict['relationship_type'] = 'unknown'
            elif len(rel_dict['participants']) == 3:
                # Ternary relationship
                rel_dict['relationship_type'] = 'ternary'
            elif len(rel_dict['participants']) > 3:
                # N-ary relationship
                rel_dict['relationship_type'] = 'n-ary'
            else:
                # No participants
                rel_dict['relationship_type'] = 'no-participants'

        structured_relationships.append(rel_dict)

    # Process inheritances
    structured_inheritances = []
    for inh in erd_data.get('inheritances', []):
        inh_dict = {
            'parent_entity': inh['parent_entity'],
            'inheritance_type': inh['inheritance_type'],
            'symbol': inh.get('symbol', '?'),
            'child_entities': [child['name'] for child in inh.get('child_entities', [])]
        }
        structured_inheritances.append(inh_dict)

    return {
        'entities': structured_entities,
        'relationships': structured_relationships,
        'inheritances': structured_inheritances
    }

def calculate_total_score(breakdown):
    """
    Calculate the total score from the breakdown scores.
    This ensures the math is always correct, even if the AI makes a mistake.

    Args:
        breakdown: Dictionary with scores in format "earned/total" (e.g., "38/40")

    Returns:
        tuple: (total_earned, total_possible) e.g., (98, 100)
    """
    total_earned = 0
    total_possible = 0

    for score_str in breakdown.values():
        if '/' in score_str:
            parts = score_str.split('/')
            earned = int(parts[0])
            possible = int(parts[1])
            total_earned += earned
            total_possible += possible

    return total_earned, total_possible

def grade_erd_with_ai(student_erd, teacher_erd, custom_requirements=None, max_retries=3):
    """
    Use Google Gemini to grade student ERD against teacher's ERD.

    Args:
        student_erd: The student's ERD data
        teacher_erd: The teacher's ERD data (correct answer)
        custom_requirements: Optional custom grading requirements from the grader
        max_retries: Maximum number of retry attempts for malformed responses
    """
    import time

    last_error = None

    for attempt in range(max_retries):
        try:
            # Add exponential backoff for retries
            if attempt > 0:
                wait_time = 2 ** attempt  # 2, 4, 8 seconds
                print(f"Retry attempt {attempt + 1}/{max_retries} after {wait_time}s delay...")
                time.sleep(wait_time)

            return _grade_erd_attempt(student_erd, teacher_erd, custom_requirements)
        except Exception as e:
            last_error = e
            error_msg = str(e)
            # If it's a malformed response and we have retries left, try again
            if attempt < max_retries - 1 and ('malformed' in error_msg.lower() or 'json' in error_msg.lower() or 'valueerror' in str(type(e)).lower()):
                print(f"Attempt {attempt + 1}/{max_retries} failed with error: {error_msg[:100]}")
                print(f"Retrying...")
                continue
            else:
                # Last attempt - return user-friendly error
                print(f"Final attempt {attempt + 1}/{max_retries} failed. No more retries.")
                break

    # All retries exhausted - return structured error response
    return {
        "error": "AI generated malformed response",
        "message": f"The AI failed to generate a valid response after {max_retries} attempts. This may be due to API issues or the complexity of the ERD diagrams.",
        "details": {
            "attempts": max_retries,
            "last_error": str(last_error) if last_error else "Unknown error"
        },
        "suggestions": [
            "Try simplifying the ERD diagrams",
            "Wait a moment and try again",
            "Check if the ERD data is valid"
        ]
    }


def _grade_erd_attempt(student_erd, teacher_erd, custom_requirements):
    """
    Single attempt to grade ERD with AI.
    Separated from main function to enable retry logic.
    """
    try:
        structured_teacher = convert_to_structured_format(teacher_erd)
        structured_student = convert_to_structured_format(student_erd)


        if json.dumps(structured_student, sort_keys=True) == json.dumps(structured_teacher, sort_keys=True):
            print("="*80)
            print("IDENTICAL ERDs DETECTED - Returning perfect score 100/100")
            print("="*80)
            return {
                "score": "100/100",
                "analysis": {
                    "correctEntities": "All entities correct",
                    "missingEntities": "None",
                    "correctRelationships": "All relationships correct",
                    "incorrectRelationships": "None",
                    "missingRelationships": "None",
                    "primaryKeyAnalysis": "All primary keys present",
                    "inheritanceAnalysis": "Perfect match",
                    "cardinalityAnalysis": "All cardinalities correct"
                },
                "breakdown": {
                    "entities": "20/20",
                    "relationships": "40/40",
                    "cardinalities": "10/10",
                    "primaryKeys": "20/20",
                    "inheritance": "10/10"
                },
                "feedback": {
                    "strengths": "Perfect submission - identical to model answer",
                    "errors": "None",
                    "missing": "None"
                },
                "suggestions": ["Excellent work! Your ERD perfectly matches the model answer."]
            }
        from grade_erd_json_prompting import create_json_prompt

        # Create structured JSON prompt
        json_prompt = create_json_prompt(structured_teacher, structured_student, custom_requirements)

        model = genai.GenerativeModel('gemini-2.0-flash-lite')

        # Convert JSON prompt to string with clear instructions
        prompt = f"""
You are a precise data processing system for ERD grading.

INSTRUCTIONS:
You will receive a STRUCTURED JSON CONFIGURATION that contains:
1. The grading task specification
2. The grading rules and criteria
3. Reference examples for calibration
4. The model answer (teacher's ERD)
5. The student submission to be graded

Your job is to PROCESS this structured data and return a JSON response following the exact output specification.

Process the following STRUCTURED JSON GRADING CONFIGURATION and return the exact JSON output format specified in the configuration.

========================
STRUCTURED GRADING CONFIGURATION (JSON):
========================
```json
{json.dumps(json_prompt, indent=2, ensure_ascii=False)}
```

PROCESSING INSTRUCTIONS:
1. Read the entire JSON configuration above
2. Apply the grading rules specified in "grading_rules"
3. Use the "reference_calibration" examples to calibrate your scoring
4. Compare the "model_answer" with the "student_submission"
5. Return a JSON response matching the "output_specification" exactly

CRITICAL OUTPUT REQUIREMENTS:
1. Your response MUST be valid, parseable JSON
2. Start with {{ and end with }} - nothing before or after
3. Do NOT include markdown code fences (no ```)
4. Do NOT include any explanatory text outside the JSON
5. ALL fields must be STRINGS except "suggestions" which is an array of strings
6. The breakdown scores MUST add up to the overall score
7. Each suggestion in the array must be under 200 characters
8. Ensure all strings are properly escaped and terminated
9. If you encounter any issues, output a minimal valid JSON with an error field
10. KEEP ALL ANALYSIS FIELDS CONCISE - use summaries with counts, NOT exhaustive lists
11. For correctRelationships, write "X/Y relationships are correct" NOT a list of all relationships
12. Maximum length for ANY string field in "analysis" is 300 characters

RESPONSE FORMAT - EXACTLY THIS STRUCTURE:
{{
  "score": "XX/100",
  "analysis": {{ ... }},
  "breakdown": {{ ... }},
  "feedback": {{ ... }},
  "suggestions": ["...", "...", "..."]
}}
"""

        print("="*80)
        print("START: PROMPT SENT TO GEMINI API")
        print("="*80)
        print(prompt)
        print("="*80)
        print("END: PROMPT SENT TO GEMINI API")
        print("="*80)

        # Configure generation for consistency and accuracy
        generation_config = genai.types.GenerationConfig(
            temperature=0.0,  # Deterministic output (0.0 = most consistent)
            top_p=0.95,       # Nucleus sampling
            top_k=40,         # Top-k sampling
            max_output_tokens=8192,  # Increased to allow for complete responses
        )

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        raw_text = response.text

        # Clean up the response text - remove markdown code fences and trim
        json_text = raw_text.strip()

        # Remove markdown code fences if present
        if json_text.startswith("```json"):
            json_text = json_text[7:]  # Remove ```json
        elif json_text.startswith("```"):
            json_text = json_text[3:]  # Remove ```

        if json_text.endswith("```"):
            json_text = json_text[:-3]  # Remove trailing ```

        json_text = json_text.strip()

        # Try to parse the JSON with multiple fallback strategies
        result = None
        parse_error = None

        try:
            result = json.loads(json_text)
        except json.JSONDecodeError as json_err:
            parse_error = json_err
            print(f"JSON Decode Error: {json_err}")
            print(f"Raw AI Response (first 1000 chars):\n{raw_text[:1000]}")

            # Strategy 1: Try to fix unterminated strings by finding the last valid closing brace
            try:
                import re
                # Find the last valid closing brace
                last_brace = json_text.rfind('}')
                if last_brace > 0:
                    truncated_json = json_text[:last_brace + 1]
                    result = json.loads(truncated_json)
                    result['_warning'] = 'AI response was truncated to fix malformed JSON'
                    print("Successfully recovered by truncating to last valid brace")
            except:
                pass

            # Strategy 2: Try to fix excessive repetition in suggestions array
            if result is None:
                try:
                    # Remove excessively long strings in suggestions array
                    json_text_fixed = re.sub(
                        r'"suggestions":\s*\[\s*"([^"]{1000,})"',
                        r'"suggestions": ["Response truncated due to excessive length"',
                        json_text
                    )
                    # Also try to close any unclosed arrays/objects
                    if json_text_fixed.count('{') > json_text_fixed.count('}'):
                        json_text_fixed += '}'
                    if json_text_fixed.count('[') > json_text_fixed.count(']'):
                        json_text_fixed += ']'

                    result = json.loads(json_text_fixed)
                    result['_warning'] = 'AI response had excessive repetition and was fixed'
                    print("Successfully recovered by fixing suggestions array")
                except:
                    pass

            # Strategy 3: Extract JSON from partial response using regex
            if result is None:
                try:
                    # Try to find a complete JSON object in the response
                    json_match = re.search(r'\{[\s\S]*\}', json_text)
                    if json_match:
                        potential_json = json_match.group(0)
                        result = json.loads(potential_json)
                        result['_warning'] = 'JSON extracted from partial response'
                        print("Successfully recovered by extracting JSON from partial response")
                except:
                    pass

            # If all strategies fail, raise an exception for retry handling
            if result is None:
                error_details = {
                    "error_type": type(parse_error).__name__,
                    "error_message": str(parse_error),
                    "error_location": f"Line {str(parse_error).split('line')[1].split()[0]}" if 'line' in str(parse_error) else 'unknown',
                    "response_length": len(raw_text),
                    "response_preview": raw_text[:500] + "..." if len(raw_text) > 500 else raw_text
                }
                # Raise exception to trigger retry mechanism
                raise ValueError(f"AI generated malformed JSON response: {error_details['error_message']}")

        # Validate the parsed result has required fields
        required_fields = ['score', 'analysis', 'breakdown', 'feedback', 'suggestions']
        missing_fields = [field for field in required_fields if field not in result]

        if missing_fields:
            print(f"Warning: AI response missing required fields: {missing_fields}")
            result['_warning_missing_fields'] = missing_fields
            # Add default values for missing fields
            if 'score' not in result:
                result['score'] = "0/100"
            if 'analysis' not in result:
                result['analysis'] = {"error": "Analysis not provided by AI"}
            if 'breakdown' not in result:
                result['breakdown'] = {
                    "entities": "0/20",
                    "relationships": "0/40",
                    "cardinalities": "0/10",
                    "primaryKeys": "0/20",
                    "inheritance": "0/10"
                }
            if 'feedback' not in result:
                result['feedback'] = {"error": "Feedback not provided by AI"}
            if 'suggestions' not in result:
                result['suggestions'] = ["Please try grading again"]

        # Truncate excessively long strings in analysis to prevent future parsing issues
        MAX_ANALYSIS_FIELD_LENGTH = 500  # characters
        if 'analysis' in result and isinstance(result['analysis'], dict):
            for key, value in result['analysis'].items():
                if isinstance(value, str) and len(value) > MAX_ANALYSIS_FIELD_LENGTH:
                    result['analysis'][key] = value[:MAX_ANALYSIS_FIELD_LENGTH] + "... (truncated)"
                    print(f"Warning: Truncated analysis.{key} from {len(value)} to {MAX_ANALYSIS_FIELD_LENGTH} chars")

        # Recalculate the total score to ensure correctness
        if 'breakdown' in result:
            try:
                total_earned, total_possible = calculate_total_score(result['breakdown'])
    
                result['score'] = f"{total_earned}/{total_possible}"
              
                if result.get('score') != f"{total_earned}/{total_possible}":
                    result['_score_recalculated'] = True
            except Exception as calc_err:
                print(f"Warning: Could not recalculate score: {calc_err}")

        # Check for system mismatch and apply 20-point penalty
        if 'analysis' in result and 'correctnessAnalysis' in result['analysis']:
            correctness_analysis = result['analysis']['correctnessAnalysis']

            # Check if systems don't match
            if isinstance(correctness_analysis, str) and 'System match: NO' in correctness_analysis:
                print("="*80)
                print("SYSTEM MISMATCH DETECTED - Applying 20-point penalty")
                print(f"Correctness Analysis: {correctness_analysis}")
                print("="*80)

                # Extract current score
                current_score_str = result.get('score', '0/100')
                try:
                    current_score = int(current_score_str.split('/')[0])

                    # Deduct 20 points (minimum 0)
                    penalized_score = max(0, current_score - 20)

                    # Update the score
                    result['score'] = f"{penalized_score}/100"

                    # Add note to feedback
                    if 'feedback' in result and isinstance(result['feedback'], dict):
                        if 'errors' in result['feedback']:
                            result['feedback']['errors'] = f"SYSTEM MISMATCH PENALTY (-20 points): Student modeled wrong system. {result['feedback']['errors']}"
                        else:
                            result['feedback']['errors'] = "SYSTEM MISMATCH PENALTY (-20 points): Student modeled a completely different system than required."

                    print(f"Original score: {current_score}/100")
                    print(f"Penalized score: {penalized_score}/100")
                    print("="*80)

                except (ValueError, IndexError) as e:
                    print(f"Warning: Could not apply system mismatch penalty: {e}")

        result['_debug_prompt'] = prompt  # Store the prompt for debugging
        return result

    except Exception as e:
        raw_response_text = "No response from model."
        if 'raw_text' in locals():
            raw_response_text = raw_text[:2000]  # Limit to 2000 chars to avoid huge error messages

        return {
            "error": f"Failed: {str(e)}",
            "raw_response_text": raw_response_text
        }


def format_entities_for_prompt(entities):
    """Format entities for the AI prompt"""
    result = []
    for e in entities:
        flags = []
        if e.get('is_weak'):
            flags.append('[WEAK]')
        if e.get('is_associative'):
            flags.append('[ASSOCIATIVE]')
        attrs = []
        for a in e.get('attributes', []):
            attr_str = a['name']
            if a.get('type') == 'key':
                attr_str += ' (PK)'
            elif a.get('type') == 'multivalued':
                attr_str += ' (Multivalued)'
            elif a.get('type') == 'derived':
                attr_str += ' (Derived)'
            attrs.append(attr_str)
        flag_str = ' '.join(flags) if flags else ''
        attr_str = ', '.join(attrs) if attrs else 'No attributes'
        result.append(f"- {e['name']} {flag_str}\n  Attributes: {attr_str}")
    return '\n'.join(result) if result else 'None'

def format_relationships_for_prompt(relationships):
    """Format relationships for the AI prompt"""
    result = []
    for r in relationships:
        flags = '[IDENTIFYING]' if r.get('is_identifying') else ''
        conn_summary = r.get('connection_summary', 'No connections').replace('**', '')
        attrs = []
        for a in r.get('attributes', []):
            attrs.append(a['name'])
        attr_str = f"Attributes: {', '.join(attrs)}" if attrs else 'No attributes'
        result.append(f"- {r['name']} {flags}\n  {conn_summary}\n  {attr_str}")
    return '\n'.join(result) if result else 'None'

def format_connections_for_prompt(connections):
    """This will now be empty, which is fine."""
    result = []
    for c in connections:
        cardinality = f"[{c['cardinality']}]" if c.get('cardinality') else ''
        result.append(f"- {c['source_name']} → {c['target_name']} {cardinality}")
    return '\n'.join(result) if result else 'None'

def format_inheritances_for_prompt(inheritances):
    """Format inheritance/specialization hierarchies for the AI prompt"""
    if not inheritances:
        return '\nInheritance/Specialization: None'
    result = ['\nInheritance/Specialization:']
    type_descriptions = {
        'disjoint': 'Disjoint (XOR) - Entity is one subtype only',
        'union': 'Union (Total) - Every parent MUST be in at least one subtype',
        'overlapping': 'Overlapping (OR) - Can be in multiple subtypes'
    }
    for inh in inheritances:
        symbol = inh.get('symbol', '?')
        inh_type = inh.get('inheritance_type', 'unknown')
        type_desc = type_descriptions.get(inh_type, inh_type)
        parent = inh.get('parent_entity', 'Unknown')
        children = ', '.join([child['name'] for child in inh.get('child_entities', [])])
        result.append(f"- [{symbol}] {parent} → {type_desc}")
        result.append(f"  Subtypes: {children}")
    return '\n'.join(result)

if __name__ == '__main__':
    app.run(debug=True, port=5001)