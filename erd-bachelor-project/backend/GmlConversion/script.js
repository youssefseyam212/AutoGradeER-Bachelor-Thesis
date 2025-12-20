let erdData = {
    entities: {},
    attributes: [],
    relationships: [],
    edges: [],
    nodes: {}, // Changed from array to object for fast lookup
    relationshipTypes: {}
};

document.getElementById('fileInput').addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            parseGraphML(e.target.result);
        };
        reader.readAsText(file);
    }
});

// Add drag and drop functionality
const uploadSection = document.querySelector('.upload-section');
uploadSection.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadSection.style.background = '#e8e8ff';
});

uploadSection.addEventListener('dragleave', () => {
    uploadSection.style.background = '#f8f9fa';
});

uploadSection.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadSection.style.background = '#f8f9fa';

    const file = e.dataTransfer.files[0];
    if (file && (file.name.endsWith('.graphml') || file.name.endsWith('.xml'))) {
        const reader = new FileReader();
        reader.onload = function(e) {
            parseGraphML(e.target.result);
        };
        reader.readAsText(file);
    } else {
        alert('Please drop a valid GraphML or XML file.');
    }
});

function parseGraphML(xmlString) {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlString, "text/xml");

    // Reset data
    erdData = {
        entities: {},
        attributes: [],
        relationships: [],
        edges: [],
        nodes: {},
        relationshipTypes: {}
    };

    // Parse nodes
    const nodes = xmlDoc.querySelectorAll('node');
    nodes.forEach(node => {
        const id = node.getAttribute('id');
        const labelElement = node.querySelector('y\\:NodeLabel, NodeLabel');
        const label = labelElement ? labelElement.textContent : 'Unknown';
        const configElement = node.querySelector('y\\:GenericNode, GenericNode');
        const config = configElement ? configElement.getAttribute('configuration') : '';
        const isUnderlined = labelElement ? labelElement.getAttribute('underlinedText') === 'true' : false;

        const nodeData = {
            id: id,
            label: label,
            config: config,
            isPrimaryKey: isUnderlined
        };

        erdData.nodes[id] = nodeData;

        if (config.includes('small_entity')) {
            if (!erdData.entities[label]) {
                erdData.entities[label] = {
                    id: id,
                    attributes: []
                };
            }
        } else if (config.includes('attribute')) {
            erdData.attributes.push(nodeData);
        } else if (config.includes('relationship')) {
            erdData.relationships.push(nodeData);
        }
    });

    // Parse edges
    const edges = xmlDoc.querySelectorAll('edge');
    edges.forEach(edge => {
        const source = edge.getAttribute('source');
        const target = edge.getAttribute('target');

        // Get arrow types to determine cardinality
        const arrowsElement = edge.querySelector('y\\:Arrows, Arrows');
        const sourceArrow = arrowsElement ? arrowsElement.getAttribute('source') : 'none';
        const targetArrow = arrowsElement ? arrowsElement.getAttribute('target') : 'none';

        erdData.edges.push({
            source,
            target,
            sourceArrow,
            targetArrow
        });

        // Connect attributes to entities
        const sourceNode = erdData.nodes[source];
        const targetNode = erdData.nodes[target];

        if (sourceNode && targetNode) {
            // If source is entity and target is attribute
            if (sourceNode.config.includes('small_entity') && targetNode.config.includes('attribute')) {
                const entityName = sourceNode.label;
                if (erdData.entities[entityName]) {
                    erdData.entities[entityName].attributes.push({
                        name: targetNode.label,
                        isPrimaryKey: targetNode.isPrimaryKey
                    });
                }
            }
            // If target is entity and source is attribute
            else if (targetNode.config.includes('small_entity') && sourceNode.config.includes('attribute')) {
                const entityName = targetNode.label;
                if (erdData.entities[entityName]) {
                    erdData.entities[entityName].attributes.push({
                        name: sourceNode.label,
                        isPrimaryKey: sourceNode.isPrimaryKey
                    });
                }
            }
        }
    });

    // Analyze relationship types
    analyzeRelationshipTypes();

    displayERD();
}

// --- NEW HELPER FUNCTION ---
// Interprets yEd arrow types into 'one' or 'many'
function getCardinalityFromArrow(arrowType) {
    if (arrowType.includes('crows_foot_many')) { // Catches 'crows_foot_many' and 'crows_foot_many_mandatory'
        return 'many';
    }
    if (arrowType.includes('crows_foot_one')) { // Catches 'crows_foot_one' and 'crows_foot_one_mandatory'
        return 'one';
    }
    return 'one'; // Default for 'none' arrow
}

function analyzeRelationshipTypes() {
    // Reset relationship types
    erdData.relationshipTypes = {};

    // Find relationships between entities through relationship nodes
    erdData.relationships.forEach(relationshipNode => {
        // Find edges connected to this relationship node
        const connectedEdges = erdData.edges.filter(edge =>
            edge.source === relationshipNode.id || edge.target === relationshipNode.id
        );

        // Find entities connected to this relationship
        const connectedEntities = [];

        connectedEdges.forEach(edge => {
            const nodeId = edge.source === relationshipNode.id ? edge.target : edge.source;
            const node = erdData.nodes[nodeId];
            if (node && node.config.includes('small_entity')) {
                connectedEntities.push({
                    entity: node,
                    edge: edge,
                    // This checks if the *relationship* is the source of the edge
                    isRelationshipSource: edge.source === relationshipNode.id
                });
            }
        });

        // We should have exactly 2 entities connected to a relationship
        if (connectedEntities.length === 2) {
            const entity1 = connectedEntities[0];
            const entity2 = connectedEntities[1];

            // --- START OF CORRECTED LOGIC ---

            // Determine cardinality for entity1
            let cardinality1 = 'one';
            if (entity1.isRelationshipSource) {
                // Relationship is source, entity is target
                // We check the arrow at the entity's end (targetArrow)
                cardinality1 = getCardinalityFromArrow(entity1.edge.targetArrow);
            } else {
                // Entity is source, relationship is target (this is the common yEd case)
                // We check the arrow at the entity's end (sourceArrow)
                cardinality1 = getCardinalityFromArrow(entity1.edge.sourceArrow);
            }

            // Determine cardinality for entity2
            let cardinality2 = 'one';
            if (entity2.isRelationshipSource) {
                // Relationship is source, entity is target
                cardinality2 = getCardinalityFromArrow(entity2.edge.targetArrow);
            } else {
                // Entity is source, relationship is target
                cardinality2 = getCardinalityFromArrow(entity2.edge.sourceArrow);
            }

            // --- END OF CORRECTED LOGIC ---

            let type = 'unknown';
            let cardinality = 'unknown';

            if (cardinality1 === 'one' && cardinality2 === 'one') {
                type = 'one-to-one';
                cardinality = '1:1';
            } else if (cardinality1 === 'one' && cardinality2 === 'many') {
                type = 'one-to-many';
                cardinality = '1:N';
            } else if (cardinality1 === 'many' && cardinality2 === 'one') {
                type = 'one-to-many';
                cardinality = 'N:1';
            } else if (cardinality1 === 'many' && cardinality2 === 'many') {
                type = 'many-to-many';
                cardinality = 'M:N';
            }

            // Store details for display and SQL generation
            const relationshipKey = [entity1.entity.label, entity2.entity.label].sort().join('-') + '-' + relationshipNode.label;

            erdData.relationshipTypes[relationshipKey] = {
                type: type,
                cardinality: cardinality,
                relationshipNode: relationshipNode.label,
                // Store the *actual* entity labels and their determined cardinalities
                entity1Label: entity1.entity.label,
                entity2Label: entity2.entity.label,
                entity1Cardinality: cardinality1,
                entity2Cardinality: cardinality2
            };
        }
    });
}

function displayERD() {
    // Update stats
    const entityCount = Object.keys(erdData.entities).length;
    const attributeCount = erdData.attributes.length;
    const relationshipCount = erdData.relationships.length;
    const relationshipTypesCount = Object.keys(erdData.relationshipTypes).length;

    document.getElementById('entityCount').textContent = entityCount;
    document.getElementById('attributeCount').textContent = attributeCount;
    document.getElementById('relationshipCount').textContent = relationshipCount;
    document.getElementById('relationshipTypesCount').textContent = relationshipTypesCount;

    document.getElementById('statsSection').style.display = 'block';

    // Display structure
    let structureHTML = '';

    for (const [entityName, entityData] of Object.entries(erdData.entities)) {
        structureHTML += `
            <div class="entity-item">
                <h3>🏢 ${entityName.toUpperCase()}</h3>
                <ul>
        `;

        if (entityData.attributes.length > 0) {
            entityData.attributes.forEach(attr => {
                const pkClass = attr.isPrimaryKey ? ' class="pk"' : '';
                const pkIcon = attr.isPrimaryKey ? '🔑 ' : '• ';
                structureHTML += `<li${pkClass}>${pkIcon}${attr.name}</li>`;
            });
        } else {
            structureHTML += '<li style="color: #999;">No attributes connected</li>';
        }

        structureHTML += `
                </ul>
            </div>
        `;
    }

    // Display relationships with types
    if (Object.keys(erdData.relationshipTypes).length > 0) {
        structureHTML += '<h2 style="margin-top: 30px; color: #667eea;">🔗 Relationships</h2>';

        for (const [key, relationship] of Object.entries(erdData.relationshipTypes)) {
            const typeClass = relationship.type.replace(/-/g, '-');
            const connectorSymbol = getConnectorSymbol(relationship.cardinality);

            // --- START OF CORRECTED DISPLAY ---

            // Create relationship description using the stored, accurate labels
            const description = `${relationship.entity1Label} (${relationship.entity1Cardinality}) ↔ ${relationship.entity2Label} (${relationship.entity2Cardinality})`;

            structureHTML += `
                <div class="relationship-card">
                    <h3>
                        ⚡ ${relationship.relationshipNode.toUpperCase()}
                        <span class="relationship-type ${typeClass}">${relationship.cardinality}</span>
                    </h3>
                    <div class="relationship-details">
                        <p><strong>Type:</strong> ${relationship.type.replace(/-/g, ' ').toUpperCase()}</p>
                        <p><strong>Description:</strong> ${description}</p>
                        <div class="relationship-entities">
                            <div class="relationship-entity">${relationship.entity1Label} (${relationship.entity1Cardinality})</div>
                            <div class="relationship-connector">
                                <span class="connector-symbol">${connectorSymbol}</span>
                            </div>
                            <div class="relationship-entity">${relationship.entity2Label} (${relationship.entity2Cardinality})</div>
                        </div>
                    </div>
                </div>
            `;
            // --- END OF CORRECTED DISPLAY ---
        }
    }

    document.getElementById('structureContent').innerHTML = structureHTML;
}

function getConnectorSymbol(cardinality) {
    switch(cardinality) {
        case '1:1':
            return '⟷';
        case '1:N':
        case 'N:1':
            return '⟷'; // Symbol doesn't need direction, text explains it
        case 'M:N':
            return '⟷';
        default:
            return '—';
    }
}

// --- NEW HELPER FUNCTION ---
// Finds the primary key attribute name for a given entity
function findPrimaryKey(entityName) {
    const entity = erdData.entities[entityName];
    if (!entity) return 'id'; // Fallback
    const pk = entity.attributes.find(attr => attr.isPrimaryKey);
    return pk ? pk.name : 'id'; // Fallback to 'id' if no PK is marked
}

function downloadSQL() {
    let sql = '-- Generated SQL Schema from ERD\n';
    sql += '-- ' + '='.repeat(70) + '\n\n';

    // Create all tables first
    for (const [entityName, entityData] of Object.entries(erdData.entities)) {
        sql += `-- Table: ${entityName}\n`;
        sql += `CREATE TABLE ${entityName} (\n`;

        const columns = [];
        const primaryKeys = [];

        entityData.attributes.forEach(attr => {
            const dataType = inferDataType(attr.name);
            let columnDef = `    ${attr.name} ${dataType}`;

            if (attr.isPrimaryKey) {
                primaryKeys.push(attr.name);
                columnDef += ' NOT NULL';
            }

            columns.push(columnDef);
        });

        // Add primary key constraint at the end
        if (primaryKeys.length > 0) {
            columns.push(`    PRIMARY KEY (${primaryKeys.join(', ')})`);
        }

        sql += columns.join(',\n');
        sql += '\n);\n\n';
    }

    // --- START OF CORRECTED SQL GENERATION ---

    // Add foreign key constraints and junction tables
    sql += '\n-- ' + '='.repeat(70) + '\n';
    sql += '-- Foreign Keys & Junction Tables\n';
    sql += '-- ' + '='.repeat(70) + '\n\n';

    for (const [key, relationship] of Object.entries(erdData.relationshipTypes)) {

        if (relationship.type === 'one-to-many') {
            // Find the "one" side and the "many" side
            const oneSide = relationship.entity1Cardinality === 'one' ? relationship.entity1Label : relationship.entity2Label;
            const manySide = relationship.entity1Cardinality === 'many' ? relationship.entity1Label : relationship.entity2Label;

            const oneSidePK = findPrimaryKey(oneSide);
            const oneSidePKType = inferDataType(oneSidePK);
            const fkColumn = `${oneSide.toLowerCase()}_${oneSidePK}`;
            const fkName = `fk_${manySide}_${oneSide}`;

            sql += `-- Foreign key for 1:N relationship: ${oneSide} -> ${manySide}\n`;
            sql += `ALTER TABLE ${manySide}\n`;
            sql += `ADD COLUMN ${fkColumn} ${oneSidePKType};\n`;
            sql += `ALTER TABLE ${manySide}\n`;
            sql += `ADD CONSTRAINT ${fkName} FOREIGN KEY (${fkColumn}) REFERENCES ${oneSide}(${oneSidePK});\n\n`;

        } else if (relationship.type === 'one-to-one') {
            // For 1:1, we'll add a unique foreign key to one of the tables
            // We arbitrarily pick entity1 to hold the key to entity2
            const [entity1, entity2] = [relationship.entity1Label, relationship.entity2Label];
            const entity2PK = findPrimaryKey(entity2);
            const entity2PKType = inferDataType(entity2PK);
            const fkColumn = `${entity2.toLowerCase()}_${entity2PK}`;
            const fkName = `fk_${entity1}_${entity2}`;

            sql += `-- Foreign key for 1:1 relationship: ${entity2} -> ${entity1} (unique)\n`;
            sql += `ALTER TABLE ${entity1}\n`;
            sql += `ADD COLUMN ${fkColumn} ${entity2PKType} UNIQUE;\n`;
            sql += `ALTER TABLE ${entity1}\n`;
            sql += `ADD CONSTRAINT ${fkName} FOREIGN KEY (${fkColumn}) REFERENCES ${entity2}(${entity2PK});\n\n`;

        } else if (relationship.type === 'many-to-many') {
            // For M:N, create a junction table
            const [entity1, entity2] = [relationship.entity1Label, relationship.entity2Label];
            const junctionTable = `${entity1}_${entity2}_${relationship.relationshipNode}`.toLowerCase().replace(/[^a-z0-9_]/g, '');

            const entity1PK = findPrimaryKey(entity1);
            const entity1PKType = inferDataType(entity1PK);
            const entity1FK = `${entity1.toLowerCase()}_${entity1PK}`;

            const entity2PK = findPrimaryKey(entity2);
            const entity2PKType = inferDataType(entity2PK);
            const entity2FK = `${entity2.toLowerCase()}_${entity2PK}`;

            sql += `-- Junction table for M:N relationship: ${entity1} <-> ${entity2}\n`;
            sql += `CREATE TABLE ${junctionTable} (\n`;
            sql += `    ${entity1FK} ${entity1PKType} NOT NULL,\n`;
            sql += `    ${entity2FK} ${entity2PKType} NOT NULL,\n`;
            sql += `    PRIMARY KEY (${entity1FK}, ${entity2FK}),\n`;
            sql += `    FOREIGN KEY (${entity1FK}) REFERENCES ${entity1}(${entity1PK}),\n`;
            sql += `    FOREIGN KEY (${entity2FK}) REFERENCES ${entity2}(${entity2PK})\n`;
            sql += `);\n\n`;
        }
    }
    // --- END OF CORRECTED SQL GENERATION ---

    const dataBlob = new Blob([sql], {type: 'text/plain'});
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'database_schema.sql';
    link.click();
}

function inferDataType(attrName) {
    const name = attrName.toLowerCase();
    if (name.includes('id')) return 'INTEGER';
    if (name.includes('email')) return 'VARCHAR(255)';
    if (name.includes('password')) return 'VARCHAR(255)';
    if (name.includes('name')) return 'VARCHAR(100)';
    if (name.includes('age')) return 'INTEGER';
    if (name.includes('date') || name.includes('time')) return 'TIMESTAMP';
    if (name.includes('subject')) return 'VARCHAR(100)';
    return 'VARCHAR(255)';
}

// Auto-load sample data for demonstration
window.addEventListener('load', function() {
    const sampleGraphML = `<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:java="http://www.yworks.com/xml/yfiles-common/1.0/java" xmlns:sys="http://www.yworks.com/xml/yfiles-common/markup/primitives/2.0" xmlns:x="http://www.yworks.com/xml/yfiles-common/markup/2.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:y="http://www.yworks.com/xml/graphml" xmlns:yed="http://www.yworks.com/xml/yed/3" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">
  <key attr.name="Description" attr.type="string" for="graph" id="d0"/>
  <key for="port" id="d1" yfiles.type="portgraphics"/>
  <key for="port" id="d2" yfiles.type="portgeometry"/>
  <key for="port" id="d3" yfiles.type="portuserdata"/>
  <key attr.name="url" attr.type="string" for="node" id="d4"/>
  <key attr.name="description" attr.type="string" for="node" id="d5"/>
  <key for="node" id="d6" yfiles.type="nodegraphics"/>
  <key for="graphml" id="d7" yfiles.type="resources"/>
  <key attr.name="url" attr.type="string" for="edge" id="d8"/>
  <key attr.name="description" attr.type="string" for="edge" id="d9"/>
  <key for="edge" id="d10" yfiles.type="edgegraphics"/>
  <graph edgedefault="directed" id="G">
    <data key="d0"/>
    <node id="n0">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.small_entity">
          <y:Geometry height="40.0" width="80.0" x="337.0" y="236.0"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="48.2265625" x="15.88671875" xml:space="preserve" y="10.93359375">student<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n1">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.attribute">
          <y:Geometry height="40.0" width="80.0" x="317.0" y="141.0"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="35.453125" x="22.2734375" xml:space="preserve" y="10.93359375">email<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n2">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.attribute">
          <y:Geometry height="40.0" width="80.0" x="446.0" y="147.0"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="35.962890625" x="22.0185546875" xml:space="preserve" y="10.93359375">name<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n3">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.attribute">
          <y:Geometry height="40.0" width="80.0" x="500.0" y="217.0"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="24.794921875" x="27.6025390625" xml:space="preserve" y="10.93359375">age<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n4">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.attribute">
          <y:Geometry height="40.0" width="80.0" x="140.0" y="187.0"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="59.494140625" x="10.2529296875" xml:space="preserve" y="10.93359375">password<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n5">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.small_entity">
          <y:Geometry height="40.0" width="80.0" x="332.0" y="548.6666666666667"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="32.4765625" x="23.76171875" xml:space="preserve" y="10.93359375">class<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n6">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.attribute">
          <y:Geometry height="40.0" width="90.0" x="538.0" y="548.6666666666667"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="52.205078125" x="18.8974609375" xml:space="preserve" y="10.93359375">subjects<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n7">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.attribute">
          <y:Geometry height="40.0" width="80.0" x="207.0" y="250.0"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="bold" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" underlinedText="true" verticalTextPosition="bottom" visible="true" width="15.853515625" x="32.0732421875" xml:space="preserve" y="10.93359375">id<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n8">
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.relationship">
          <y:Geometry height="56.0" width="90.0" x="332.0" y="391.0"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="41.2890625" x="24.35546875" xml:space="preserve" y="18.93359375">attend<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n9">
      <data key="d5"/>
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.relationship">
          <y:Geometry height="56.0" width="90.0" x="107.2890776393071" y="540.6666666666667"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="35.39453125" x="27.302734375" xml:space="preserve" y="18.93359375">teach<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <node id="n10">
      <data key="d5"/>
      <data key="d6">
        <y:GenericNode configuration="com.yworks.entityRelationship.small_entity">
          <y:Geometry height="40.0" width="80.0" x="-131.1579585993297" y="556.6666666666666"/>
          <y:Fill color="#E8EEF7" color2="#B7C9E3" transparent="false"/>
          <y:BorderStyle color="#000000" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" fontFamily="Dialog" fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false" height="18.1328125" horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#000000" verticalTextPosition="bottom" visible="true" width="46.990234375" x="16.5048828125" xml:space="preserve" y="10.93359375">teacher<y:LabelModel><y:SmartNodeLabelModel distance="4.0"/></y:LabelModel><y:ModelParameter><y:SmartNodeLabelModelParameter labelRatioX="0.0" labelRatioY="0.0" nodeRatioX="0.0" nodeRatioY="0.0" offsetX="0.0" offsetY="0.0" upX="0.0" upY="-1.0"/></y:ModelParameter></y:NodeLabel>
        </y:GenericNode>
      </data>
    </node>
    <edge id="e0" source="n0" target="n1">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="none" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e1" source="n0" target="n2">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="none" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e2" source="n0" target="n3">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="none" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e3" source="n0" target="n4">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="none" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e4" source="n6" target="n5">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="none" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e5" source="n7" target="n0">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="none" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e6" source="n0" target="n8">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="crows_foot_one" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e7" source="n5" target="n8">
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="crows_foot_many" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e8" source="n10" target="n9">
      <data key="d9"/>
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="crows_foot_one" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
    <edge id="e9" source="n5" target="n9">
      <data key="d9"/>
      <data key="d10">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="#000000" type="line" width="1.0"/>
          <y:Arrows source="crows_foot_many_mandatory" target="none"/>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
  </graph>
  <data key="d7">
    <y:Resources/>
  </data>
</graphml>`;

    // Auto-load the sample GraphML from the user's previous example
    parseGraphML(sampleGraphML);
});
