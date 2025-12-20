import { useState, useEffect, useRef } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faDatabase, faLink, faCodeBranch, faKey, faArrowUp } from '@fortawesome/free-solid-svg-icons';

function ERDDisplay({ data1, data2, file1Name, file2Name }) {
  const column1Ref = useRef(null);
  const column2Ref = useRef(null);
  const [showScrollTop1, setShowScrollTop1] = useState(false);
  const [showScrollTop2, setShowScrollTop2] = useState(false);

  useEffect(() => {
    const handleScroll = (ref, setShowScrollTop) => (e) => {
      if (e.target.scrollTop > 100) {
        setShowScrollTop(true);
        e.target.classList.add('scrolled');
      } else {
        setShowScrollTop(false);
        e.target.classList.remove('scrolled');
      }
    };

    const col1 = column1Ref.current;
    const col2 = column2Ref.current;

    const handler1 = col1 ? handleScroll(column1Ref, setShowScrollTop1) : null;
    const handler2 = col2 ? handleScroll(column2Ref, setShowScrollTop2) : null;

    if (col1 && handler1) {
      col1.addEventListener('scroll', handler1);
    }

    if (col2 && handler2) {
      col2.addEventListener('scroll', handler2);
    }

    return () => {
      if (col1 && handler1) {
        col1.removeEventListener('scroll', handler1);
      }
      if (col2 && handler2) {
        col2.removeEventListener('scroll', handler2);
      }
    };
  }, [data1, data2]);

  const scrollToTop = (ref) => {
    if (ref.current) {
      ref.current.scrollTo({ top: 0, behavior: 'smooth' });
    }
  };

  if (data2) {
    return (
      <div className="comparison-layout">
        <div className="diagram-column file1" ref={column1Ref}>
          <div className="diagram-title file1">Student ERD: {file1Name}</div>
          <ERDStructure data={data1} isFile2={false} />
          {showScrollTop1 && (
            <button
              className="scroll-to-top-btn"
              onClick={() => scrollToTop(column1Ref)}
              aria-label="Scroll to top"
            >
              <FontAwesomeIcon icon={faArrowUp} />
            </button>
          )}
        </div>
        <div className="diagram-column file2" ref={column2Ref}>
          <div className="diagram-title file2">Model Answer ERD: {file2Name}</div>
          <ERDStructure data={data2} isFile2={true} />
          {showScrollTop2 && (
            <button
              className="scroll-to-top-btn"
              onClick={() => scrollToTop(column2Ref)}
              aria-label="Scroll to top"
            >
              <FontAwesomeIcon icon={faArrowUp} />
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="single-layout">
      <div className="diagram-column file1" ref={column1Ref}>
        <div className="diagram-title file1">Student ERD: {file1Name}</div>
        <ERDStructure data={data1} isFile2={false} />
        {showScrollTop1 && (
          <button
            className="scroll-to-top-btn"
            onClick={() => scrollToTop(column1Ref)}
            aria-label="Scroll to top"
          >
            <FontAwesomeIcon icon={faArrowUp} />
          </button>
        )}
      </div>
    </div>
  );
}

function ERDStructure({ data, isFile2 }) {
  return (
    <>
      {data.entities && data.entities.length > 0 && (
        <>
          <h2 className="section-title">
            Entities
            <span className="count-badge">{data.entities.length}</span>
          </h2>
          {data.entities.map((entity, index) => (
            <EntityItem key={index} entity={entity} isFile2={isFile2} />
          ))}
        </>
      )}

      {data.relationships && data.relationships.length > 0 && (
        <>
          <h2 className="section-title">
            Relationships
            <span className="count-badge">{data.relationships.length}</span>
          </h2>
          {data.relationships.map((rel, index) => (
            <RelationshipItem key={index} relationship={rel} />
          ))}
        </>
      )}

      {data.inheritances && data.inheritances.length > 0 && (
        <>
          <h2 className="section-title">
            Inheritance/Specialization
            <span className="count-badge">{data.inheritances.length}</span>
          </h2>
          {data.inheritances.map((inh, index) => (
            <InheritanceItem key={index} inheritance={inh} />
          ))}
        </>
      )}
    </>
  );
}

function EntityItem({ entity, isFile2 }) {
  const [collapsed, setCollapsed] = useState(true);
  const pkClass = isFile2 ? 'pk-file2' : 'pk';

  return (
    <div className={`erd-item entity-item ${collapsed ? 'collapsed' : ''}`}>
      <div className="collapsible-header" onClick={() => setCollapsed(!collapsed)}>
        <h3>
          <FontAwesomeIcon icon={faDatabase} /> {entity.name.toUpperCase()}
          {entity.is_weak && <span className="text-weak"> [WEAK]</span>}
          {entity.is_associative && <span className="text-weak"> [ASSOCIATIVE]</span>}
          {entity.attributes && entity.attributes.length > 0 && (
            <span className="attr-count-badge">{entity.attributes.length} attr</span>
          )}
        </h3>
        <span className="chevron-icon">›</span>
      </div>
      <div className="attribute-list">
        <ul>
          {entity.attributes && entity.attributes.length > 0 ? (
            entity.attributes.map((attr, index) => (
              <li key={index} className={attr.type === 'key' ? pkClass : ''}>
                {attr.type === 'key' ? (
                  <><FontAwesomeIcon icon={faKey} style={{ marginRight: '8px' }} /> </>
                ) : '• '}
                {attr.name}
              </li>
            ))
          ) : (
            <li style={{ color: '#999' }}>No attributes</li>
          )}
        </ul>
      </div>
    </div>
  );
}

function RelationshipItem({ relationship }) {
  const [collapsed, setCollapsed] = useState(true);

  // Parse connection summary to extract entities and cardinalities
  const parseConnectionSummary = (summary) => {
    if (!summary) return null;

    // Strip HTML tags to get clean text
    const cleanSummary = summary.replace(/<[^>]+>/g, '');

    // Try multiple patterns to match different formats
    // Pattern 1: [1] **ENTITY** has a relationship-type with **ENTITY** [1]
    let match = cleanSummary.match(/\[([^\]]+)\]\s+\*\*([^*]+)\*\*.*?with\s+\*\*([^*]+)\*\*\s+\[([^\]]+)\]/);

    if (match) {
      return {
        leftCardinality: match[1],
        leftEntity: match[2].trim(),
        rightEntity: match[3].trim(),
        rightCardinality: match[4]
      };
    }

    // Pattern 2: **ENTITY** [1] has a relationship-type with **ENTITY** [1]
    match = cleanSummary.match(/\*\*([^*]+)\*\*\s+\[([^\]]+)\].*?with\s+\*\*([^*]+)\*\*\s+\[([^\]]+)\]/);

    if (match) {
      return {
        leftEntity: match[1].trim(),
        leftCardinality: match[2],
        rightEntity: match[3].trim(),
        rightCardinality: match[4]
      };
    }

    // Pattern 3: Connects format - **ENTITY** [cardinality] - **ENTITY** [cardinality] - **ENTITY** [cardinality]
    // For ternary relationships
    match = cleanSummary.match(/Connects:\s*\*\*([^*]+)\*\*\s+\[([^\]]+)\]\s*-\s*\*\*([^*]+)\*\*\s+\[([^\]]+)\]\s*-\s*\*\*([^*]+)\*\*\s+\[([^\]]+)\]/);

    if (match) {
      return {
        entities: [
          { name: match[1].trim(), cardinality: match[2] },
          { name: match[3].trim(), cardinality: match[4] },
          { name: match[5].trim(), cardinality: match[6] }
        ]
      };
    }

    // Pattern 4: Simple format without markdown - ENTITY [1] ... ENTITY [1]
    match = cleanSummary.match(/([A-Za-z_][A-Za-z0-9_]*)\s+\[([^\]]+)\].*?with\s+([A-Za-z_][A-Za-z0-9_]*)\s+\[([^\]]+)\]/);

    if (match) {
      return {
        leftEntity: match[1].trim(),
        leftCardinality: match[2],
        rightEntity: match[3].trim(),
        rightCardinality: match[4]
      };
    }

    return null;
  };

  // Parse the full description to extract relationship type
  const parseRelationshipType = (summary) => {
    if (!summary) return null;
    // Strip HTML tags first
    const cleanSummary = summary.replace(/<[^>]+>/g, '');
    const typeMatch = cleanSummary.match(/has a (.*?) relationship with/i);
    return typeMatch ? typeMatch[1].trim() : null;
  };

  const connectionInfo = parseConnectionSummary(relationship.connection_summary);
  const relationshipType = parseRelationshipType(relationship.connection_summary);

  return (
    <div className={`erd-item relationship-item-modern ${collapsed ? 'collapsed' : ''}`}>
      <div className="collapsible-header" onClick={() => setCollapsed(!collapsed)}>
        <div className="relationship-header-content">
          <FontAwesomeIcon icon={faLink} className="relationship-icon" />
          <span className="relationship-title">{relationship.name}</span>
          {relationship.is_identifying && <span className="identifying-tag">IDENTIFYING</span>}
          {relationship.relationship_type === 'ternary' && <span className="ternary-tag">TERNARY</span>}
          {relationship.relationship_type === 'unary' && <span className="ternary-tag">UNARY</span>}
          {relationship.relationship_type === 'n-ary' && <span className="ternary-tag">N-ARY</span>}
        </div>
        <span className="chevron-icon">›</span>
      </div>
      <div className="attribute-list">
        {/* Special handling for ternary relationships */}
        {relationship.relationship_type === 'ternary' && relationship.participants ? (
          <div className="ternary-visual-diagram">
            {/* Relationship name in center diamond */}
            <div className="ternary-relationship-center">
              <div className="relationship-diamond">
                {relationship.name}
              </div>
            </div>

            {/* Three branches pointing to entities */}
            <div className="ternary-branches">
              {relationship.participants.map((participant, index) => (
                <div key={index} className="ternary-branch">
                  <div className="cardinality-badge">{participant.cardinality}</div>
                  <div className="branch-line"></div>
                  <div className="entity-box">{participant.entity || participant.name}</div>
                </div>
              ))}
            </div>
          </div>
        ) : connectionInfo ? (
          <div className="relationship-visual">
            {connectionInfo.entities ? (
              // N-ary relationship (4+ entities) - Vertical layout
              <div className="relationship-flow-vertical">
                {connectionInfo.entities.map((entity, index) => (
                  <div key={index} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                    <span className="entity-node">{entity.name}</span>
                    <span className="cardinality-label">{entity.cardinality}</span>
                    {index < connectionInfo.entities.length - 1 && (
                      <span className="arrow-connector-vertical">↓</span>
                    )}
                  </div>
                ))}
              </div>
            ) : relationshipType ? (
              // Binary relationship (2 entities) - Vertical layout
              <div className="relationship-flow-vertical">
                <span className="entity-node">{connectionInfo.leftEntity}</span>
                <span className="arrow-connector-vertical">↓</span>
                <span className="cardinality-label">{connectionInfo.leftCardinality}</span>
                <span className="relation-type-label">{relationshipType}</span>
                <span className="cardinality-label">{connectionInfo.rightCardinality}</span>
                <span className="arrow-connector-vertical">↓</span>
                <span className="entity-node">{connectionInfo.rightEntity}</span>
              </div>
            ) : (
              // Simple binary without relationship type - Vertical layout
              <div className="relationship-flow-vertical">
                <span className="entity-node">{connectionInfo.leftEntity}</span>
                <span className="arrow-connector-vertical">↓</span>
                <span className="cardinality-label">{connectionInfo.leftCardinality}</span>
                <span className="arrow-connector-vertical">↓</span>
                <span className="cardinality-label">{connectionInfo.rightCardinality}</span>
                <span className="arrow-connector-vertical">↓</span>
                <span className="entity-node">{connectionInfo.rightEntity}</span>
              </div>
            )}
          </div>
        ) : (
          relationship.connection_summary && (
            <div className="relationship-visual">
              <p style={{ fontSize: '0.9em', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                {relationship.connection_summary.replace(/<[^>]+>/g, '')}
              </p>
            </div>
          )
        )}
        {relationship.attributes && relationship.attributes.length > 0 && (
          <div className="relationship-attributes">
            {relationship.attributes.map((attr, index) => (
              <span key={index} className={`attr-chip ${attr.type === 'key' ? 'pk-chip' : ''}`}>
                {attr.type === 'key' && <FontAwesomeIcon icon={faKey} />}
                {attr.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InheritanceItem({ inheritance }) {
  const [collapsed, setCollapsed] = useState(true);

  const badgeClass = {
    'disjoint': 'badge-disjoint',
    'union': 'badge-union',
    'overlapping': 'badge-overlapping'
  }[inheritance.inheritance_type] || '';

  const typeDesc = {
    'disjoint': 'Disjoint (XOR) - Entity is one subtype only',
    'union': 'Union (Total) - Every parent MUST be in at least one subtype',
    'overlapping': 'Overlapping (OR) - Can be in multiple subtypes'
  }[inheritance.inheritance_type] || inheritance.inheritance_type;

  return (
    <div className={`erd-item inheritance-item ${collapsed ? 'collapsed' : ''}`}>
      <div className="collapsible-header" onClick={() => setCollapsed(!collapsed)}>
        <h3>
          <FontAwesomeIcon icon={faCodeBranch} /> {inheritance.parent_entity.toUpperCase()}
          <span className={`inheritance-badge ${badgeClass}`}>
            [{inheritance.symbol}] {inheritance.inheritance_type.toUpperCase()}
          </span>
          {inheritance.child_entities && inheritance.child_entities.length > 0 && (
            <span className="attr-count-badge">{inheritance.child_entities.length} subtypes</span>
          )}
        </h3>
        <span className="chevron-icon">›</span>
      </div>
      <div className="attribute-list">
        <div className="connection-summary">
          <strong>Type:</strong> {typeDesc}
        </div>
        <strong style={{ color: 'var(--text-primary)' }}>Subtypes:</strong>
        <ul>
          {inheritance.child_entities && inheritance.child_entities.length > 0 ? (
            inheritance.child_entities.map((child, index) => (
              <li key={index}>→ {child.name}</li>
            ))
          ) : (
            <li style={{ color: '#999' }}>No subtypes</li>
          )}
        </ul>
      </div>
    </div>
  );
}

export default ERDDisplay;
