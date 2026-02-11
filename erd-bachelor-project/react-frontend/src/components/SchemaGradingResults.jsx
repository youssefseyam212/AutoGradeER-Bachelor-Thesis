import { useState } from 'react';

function SchemaGradingResults({ results }) {
  const [expandedSection, setExpandedSection] = useState(null);

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  const getScoreColor = (earned, total) => {
    const percentage = (earned / total) * 100;
    if (percentage >= 90) return '#10b981'; // Green
    if (percentage >= 75) return '#f59e0b'; // Orange
    return '#ef4444'; // Red
  };

  const getGradePercentage = () => {
    const percentage = (results.total_score / results.total_possible * 100).toFixed(1);
    return percentage;
  };

  const renderSectionItem = (item) => {
    const statusIcon = item.found ? '✓' : '✗';
    const statusClass = item.found ? 'found' : 'missing';
    const pointsText = item.found
      ? `${item.points_earned}/${item.points_possible}`
      : `0/${item.points_possible}`;

    // Type badge mapping
    const typeLabels = {
      'entity': 'Entity',
      'weak_entity': 'Weak Entity',
      'relationship': 'Relationship',
      'ternary': 'Ternary',
      'inheritance': 'Inheritance'
    };

    const hasDetailedExplanation = item.detailed_explanation;

    return (
      <div key={item.name} className={`schema-item ${statusClass}`}>
        <div className="item-header">
          <span className="item-status">{statusIcon}</span>
          <span className="item-name">
            {item.name}
            {item.type && (
              <span className={`item-type-badge ${item.type}`}>
                {typeLabels[item.type] || item.type}
              </span>
            )}
          </span>
          <span className="item-points">{pointsText} pts</span>
        </div>
        {item.note && (
          <div className="item-note">{item.note}</div>
        )}

        {/* Detailed AI-generated explanation */}
        {hasDetailedExplanation && (
          <div className="detailed-explanation">
            <div className="explanation-header">
              <strong>📚 Detailed Explanation</strong>
            </div>

            {item.detailed_explanation.why_wrong && (
              <div className="explanation-section why-wrong">
                <strong className="explanation-title">❌ Why This Is Marked Wrong:</strong>
                <p>{item.detailed_explanation.why_wrong}</p>
              </div>
            )}

            {item.detailed_explanation.what_is_correct && (
              <div className="explanation-section what-correct">
                <strong className="explanation-title">✅ What Is Correct:</strong>
                <p>{item.detailed_explanation.what_is_correct}</p>
              </div>
            )}

            {item.detailed_explanation.what_should_happen && (
              <div className="explanation-section what-should-happen">
                <strong className="explanation-title">🎯 Expected Business Logic:</strong>
                <p>{item.detailed_explanation.what_should_happen}</p>
              </div>
            )}

            {item.detailed_explanation.correct_equivalent && (
              <div className="explanation-section correct-equivalent">
                <strong className="explanation-title">💡 Correct Equivalent:</strong>
                <p className="code-highlight">{item.detailed_explanation.correct_equivalent}</p>
              </div>
            )}

            {item.detailed_explanation.how_to_fix && (
              <div className="explanation-section how-to-fix">
                <strong className="explanation-title">🔧 How To Fix:</strong>
                <p>{item.detailed_explanation.how_to_fix}</p>
              </div>
            )}
          </div>
        )}

        {item.issues && item.issues.length > 0 && (
          <div className="item-issues">
            <strong>Issues:</strong>
            <ul>
              {item.issues.map((issue, idx) => (
                <li key={idx}>{issue}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="schema-grading-results">
      {/* Overall Score */}
      <div className="results-header">
        <h2>Grading Results</h2>
        <div className="overall-score">
          <div className="score-circle" style={{
            background: `conic-gradient(${getScoreColor(results.total_score, results.total_possible)} ${getGradePercentage() * 3.6}deg, #e5e7eb 0deg)`
          }}>
            <div className="score-inner">
              <div className="score-value">{getGradePercentage()}%</div>
              <div className="score-fraction">{results.total_score}/{results.total_possible}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Breakdown Summary */}
      <div className="breakdown-summary">
        <h3>Score Breakdown</h3>
        <div className="breakdown-cards">
          {results.breakdown && Object.entries(results.breakdown).map(([section, sectionData]) => {
            const sectionScore = sectionData.score;
            const sectionTotal = sectionData.total;
            const percentage = ((sectionScore / sectionTotal) * 100).toFixed(0);

            return (
              <div key={section} className="breakdown-card">
                <div className="card-header">
                  <h4>{section.charAt(0).toUpperCase() + section.slice(1)}</h4>
                  <span className="card-score" style={{ color: getScoreColor(sectionScore, sectionTotal) }}>
                    {sectionScore}/{sectionTotal}
                  </span>
                </div>
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{
                      width: `${percentage}%`,
                      backgroundColor: getScoreColor(sectionScore, sectionTotal)
                    }}
                  />
                </div>
                <div className="card-stats">
                  <span>{percentage}%</span>
                  <span>{sectionData.found}/{sectionData.total_items} items</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Detailed Results */}
      <div className="detailed-results">
        <h3>Detailed Analysis</h3>

        {results.breakdown && Object.entries(results.breakdown).map(([section, sectionData]) => (
          <div key={section} className="results-section">
            <div
              className={`section-header ${expandedSection === section ? 'expanded' : ''}`}
              onClick={() => toggleSection(section)}
            >
              <div className="section-title">
                <span className="expand-icon">{expandedSection === section ? '▼' : '▶'}</span>
                <h4>{section.charAt(0).toUpperCase() + section.slice(1)}</h4>
                <span className="section-count">({sectionData.found}/{sectionData.total_items})</span>
              </div>
              <span className="section-score">
                {sectionData.score}/{sectionData.total} pts
              </span>
            </div>

            {expandedSection === section && (
              <div className="section-content">
                {sectionData.items && sectionData.items.map(renderSectionItem)}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Deductions */}
      {results.deductions_applied && results.deductions_applied.length > 0 && (
        <div className="deductions-section">
          <h3>Deductions Applied</h3>
          <div className="deductions-list">
            {results.deductions_applied.map((deduction, idx) => (
              <div key={idx} className="deduction-item">
                <span className="deduction-icon">⚠️</span>
                <span className="deduction-description">{deduction.reason}</span>
                <span className="deduction-count">×{deduction.count}</span>
                <span className="deduction-points">-{deduction.total_deduction} pts</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Intelligent Grading */}
      {results.ai_grading && (
        <div className="ai-grading-section">
          <h3>🤖 AI Intelligent Analysis</h3>
          <div className="ai-grading-summary">
            <div className="ai-score-card">
              <h4>AI Score</h4>
              <div className="ai-score-value">
                {results.ai_grading.ai_score}/{results.ai_grading.ai_total_possible}
              </div>
              <div className="ai-percentage">{results.ai_grading.ai_percentage}%</div>
              {results.grading_method && (
                <div className="grading-method">Method: {results.grading_method}</div>
              )}
              {results.score_components && results.score_components.weighted && (
                <div className="weighted-score" style={{
                  marginTop: '15px',
                  padding: '12px',
                  backgroundColor: '#f0f9ff',
                  borderRadius: '8px',
                  border: '2px solid #3b82f6'
                }}>
                  <strong style={{ color: '#1e40af' }}>Weighted Score (40% rule + 60% AI):</strong>
                  <div style={{ fontSize: '1.3em', fontWeight: 'bold', color: '#1e40af', marginTop: '5px' }}>
                    {results.score_components.weighted}/{results.ai_grading.ai_total_possible}
                  </div>
                </div>
              )}
            </div>

            {results.ai_grading.analysis && (
              <div className="ai-analysis-details">
                <div className="analysis-item">
                  <strong>✓ Correctly Modeled:</strong>
                  <p>{results.ai_grading.analysis.correctly_modeled_concepts}</p>
                </div>
                {results.ai_grading.analysis.missing_concepts && (
                  <div className="analysis-item">
                    <strong>✗ Missing:</strong>
                    <p>{results.ai_grading.analysis.missing_concepts}</p>
                  </div>
                )}
                {results.ai_grading.analysis.alternative_designs_recognized && (
                  <div className="analysis-item highlight">
                    <strong>💡 Alternative Designs Recognized:</strong>
                    <p>{results.ai_grading.analysis.alternative_designs_recognized}</p>
                  </div>
                )}
                {results.ai_grading.analysis.semantic_issues && (
                  <div className="analysis-item warning">
                    <strong>⚠️ Conceptual Issues:</strong>
                    <p>{results.ai_grading.analysis.semantic_issues}</p>
                  </div>
                )}
              </div>
            )}

            {results.ai_grading.adjustments && (
              <div className="ai-adjustments">
                <h4>Score Adjustments</h4>
                <p>{results.ai_grading.adjustments.reasoning}</p>
                {results.ai_grading.adjustments.bonus_for_valid_alternatives > 0 && (
                  <div className="adjustment-item bonus">
                    +{results.ai_grading.adjustments.bonus_for_valid_alternatives} pts: Valid alternative design
                  </div>
                )}
                {results.ai_grading.adjustments.deduction_for_missing_concepts > 0 && (
                  <div className="adjustment-item deduction">
                    -{results.ai_grading.adjustments.deduction_for_missing_concepts} pts: Missing concepts
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* AI Feedback */}
      {results.ai_feedback && (
        <div className="ai-feedback-section">
          <h3>📝 Feedback</h3>
          <div className="feedback-content">
            <div className="feedback-item">
              <strong>Strengths:</strong>
              <p>{results.ai_feedback.strengths}</p>
            </div>
            <div className="feedback-item">
              <strong>Areas for Improvement:</strong>
              <p>{results.ai_feedback.improvements}</p>
            </div>
            {results.ai_feedback.suggestions && results.ai_feedback.suggestions.length > 0 && (
              <div className="feedback-item">
                <strong>Suggestions:</strong>
                <ul>
                  {results.ai_feedback.suggestions.map((suggestion, idx) => (
                    <li key={idx}>{suggestion}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Download Report */}
      <div className="actions-section">
        <button
          className="download-button"
          onClick={() => {
            const dataStr = JSON.stringify(results, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `grading_report_${new Date().toISOString()}.json`;
            link.click();
            URL.revokeObjectURL(url);
          }}
        >
          📥 Download Detailed Report
        </button>
      </div>
    </div>
  );
}

export default SchemaGradingResults;
