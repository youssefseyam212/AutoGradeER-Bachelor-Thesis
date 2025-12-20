import { useState } from 'react';
import Loader from './Loader';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faMicrochip, faListCheck, faChevronDown, faChevronUp, faBug } from '@fortawesome/free-solid-svg-icons';

function GradingSection({ studentData, teacherData }) {
  const [grading, setGrading] = useState(false);
  const [gradingResult, setGradingResult] = useState(null);
  const [error, setError] = useState('');
  const [customRequirements, setCustomRequirements] = useState('');
  const [showRequirements, setShowRequirements] = useState(false);

  const handleGrade = async () => {
    if (!studentData || !teacherData) {
      alert('Please upload and convert both SVG files first.');
      return;
    }

    try {
      setGrading(true);
      setError('');

      const requestBody = {
        student_erd: studentData,
        teacher_erd: teacherData
      };

      // Add custom requirements if provided
      if (customRequirements.trim()) {
        requestBody.custom_requirements = customRequirements.trim();
      }

      const response = await fetch('/api/grade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });

      const data = await response.json();

      if (!response.ok) {
        let errorMsg = data.message || data.error || 'Grading failed';
        if (data.raw_response_text) {
          errorMsg += `\n\nRaw AI Response: ${data.raw_response_text}`;
        }
        throw new Error(errorMsg);
      }

      setGradingResult(data);
    } catch (err) {
      setError(err.message);
      console.error(err);
    } finally {
      setGrading(false);
    }
  };

  return (
    <div className="grading-section">
      <h2>AI-Powered ERD Grading</h2>
      <div className="grading-info">
        <strong>Note:</strong> This feature grades the <strong>Student ERD</strong> (blue) against the{' '}
        <strong>Model Answer ERD</strong> (gray) using AI.
      </div>

      {/* Custom Requirements Section */}
      <div className="custom-requirements-card">
        <button
          className="requirements-toggle-btn"
          onClick={() => setShowRequirements(!showRequirements)}
          type="button"
        >
          <FontAwesomeIcon icon={faListCheck} />
          <span>Custom Grading Requirements (Optional)</span>
          <FontAwesomeIcon icon={showRequirements ? faChevronUp : faChevronDown} className="toggle-icon" />
        </button>

        {showRequirements && (
          <div className="requirements-content">
            <p className="requirements-description">
              Add custom grading instructions. You can use these to:
              <strong> add mandatory checks</strong> (deduct marks if violated),
              <strong> exclude components</strong> (ignore certain entities/relationships), or
              <strong> award bonus points</strong> (extra credit for specific features).
            </p>
            <textarea
              className="requirements-textarea"
              value={customRequirements}
              onChange={(e) => setCustomRequirements(e.target.value)}
              placeholder="Examples:&#10;&#10;MANDATORY CHECKS (deduct if missing):&#10;- Entity 'Youssef' must be present. Deduct 2 marks if missing.&#10;- All entities must have primary keys. Deduct 5 marks if violated.&#10;&#10;EXCLUSIONS (ignore in grading):&#10;- Do not grade the 'Address' entity in comparison.&#10;- Ignore inheritance hierarchies for this assignment.&#10;&#10;BONUS CRITERIA (award extra points):&#10;- Give +3 marks if all entities are normalized to 3NF.&#10;- Award +5 marks if composite attributes are properly used."
              rows="8"
            />
            <div className="requirements-footer">
              <small>
                <FontAwesomeIcon icon={faMicrochip} /> The AI will prioritize these custom requirements and apply them during grading. Be specific with point values for deductions/bonuses.
              </small>
            </div>
          </div>
        )}
      </div>

      <div className="controls-row">
        <button
          onClick={handleGrade}
          className="g-button g-button-contained grade-btn"
          disabled={grading}
          style={{ fontSize: '1em' }}
        >
          {grading ? <div className="g-spinner"></div> : 'Generate Grade & Feedback'}
        </button>
      </div>

      <div>
        {grading && <Loader text="AI is grading... Please wait." />}

        {error && (
          <div className="incorrect-item" style={{ padding: '20px' }}>
            <strong>Error:</strong> {error}
          </div>
        )}

        {!grading && !error && !gradingResult && (
          <div className="grading-loading">
            <FontAwesomeIcon icon={faMicrochip} /> Click "Generate Grade & Feedback" to get AI-powered grading results.
          </div>
        )}

        {!grading && gradingResult && (
          <GradingReport data={gradingResult} customRequirements={customRequirements} />
        )}
      </div>
    </div>
  );
}

function GradingReport({ data, customRequirements }) {
  const [showDebug, setShowDebug] = useState(false);

  const getGradeClass = (letterGrade) => {
    if (!letterGrade) return '';
    const grade = letterGrade.toUpperCase().charAt(0);
    if (grade === 'A' || grade === 'B') return 'grade-good';
    if (grade === 'C') return 'grade-average';
    if (grade === 'D' || grade === 'F') return 'grade-poor';
    return '';
  };

  // Helper function to safely render values (convert objects to strings)
  const safeRender = (value) => {
    if (!value) return null;
    if (typeof value === 'string') return value;
    if (typeof value === 'object') {
      return JSON.stringify(value, null, 2);
    }
    return String(value);
  };

  const gradeClass = getGradeClass(data.letterGrade);

  return (
    <div className="grading-content">
      <div className="grading-content-inner">
        {/* Debug Button */}
        {data._debug_prompt && (
          <div style={{ marginBottom: '20px' }}>
            <button
              onClick={() => setShowDebug(!showDebug)}
              className="g-button g-button-outlined"
              style={{
                fontSize: '0.9em',
                padding: '8px 16px',
                backgroundColor: '#f3f4f6',
                color: '#374151',
                border: '1px solid #d1d5db'
              }}
            >
              <FontAwesomeIcon icon={faBug} style={{ marginRight: '8px' }} />
              {showDebug ? 'Hide' : 'Show'} Debug Info (Student & Model JSON)
            </button>
          </div>
        )}

        {/* Debug Card */}
        {showDebug && data._debug_prompt && (
          <div className="waterfall-item" style={{
            backgroundColor: '#f9fafb',
            border: '2px solid #e5e7eb',
            marginBottom: '20px'
          }}>
            <h3 style={{ color: '#6b7280' }}>
              <FontAwesomeIcon icon={faBug} /> Debug: ERD Data Sent to LLM
            </h3>

            {/* Student ERD JSON */}
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: '#3b82f6', marginBottom: '10px', fontSize: '14px' }}>
                📘 Student ERD (JSON)
              </h4>
              <div style={{
                backgroundColor: '#ffffff',
                padding: '15px',
                borderRadius: '8px',
                border: '1px solid #bfdbfe',
                maxHeight: '400px',
                overflowY: 'auto',
                fontFamily: 'ui-monospace, SFMono-Regular, Monaco, Consolas, monospace',
                fontSize: '12px',
                lineHeight: '1.6',
                color: '#1f2937',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}>
                {(() => {
                  try {
                    // NEW: Extract from JSON prompt structure
                    const promptMatch = data._debug_prompt.match(/```json\n([\s\S]*?)\n```/);
                    if (promptMatch) {
                      const jsonPrompt = JSON.parse(promptMatch[1]);
                      if (jsonPrompt.student_submission && jsonPrompt.student_submission.data) {
                        return JSON.stringify(jsonPrompt.student_submission.data, null, 2);
                      }
                    }

                    // OLD: Fallback to old format for backward compatibility
                    const oldStudentMatch = data._debug_prompt.match(/STUDENT'S ERD \(TO BE GRADED\)[\s\S]*?```json\n([\s\S]*?)\n```/);
                    if (oldStudentMatch) {
                      return JSON.stringify(JSON.parse(oldStudentMatch[1]), null, 2);
                    }

                    return 'Could not extract student ERD from prompt';
                  } catch (e) {
                    return `Error parsing student ERD JSON: ${e.message}`;
                  }
                })()}
              </div>
            </div>

            {/* Model Answer ERD JSON */}
            <div>
              <h4 style={{ color: '#6b7280', marginBottom: '10px', fontSize: '14px' }}>
                📗 Model Answer ERD (JSON)
              </h4>
              <div style={{
                backgroundColor: '#ffffff',
                padding: '15px',
                borderRadius: '8px',
                border: '1px solid #d1d5db',
                maxHeight: '400px',
                overflowY: 'auto',
                fontFamily: 'ui-monospace, SFMono-Regular, Monaco, Consolas, monospace',
                fontSize: '12px',
                lineHeight: '1.6',
                color: '#1f2937',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
              }}>
                {(() => {
                  try {
                    // NEW: Extract from JSON prompt structure
                    const promptMatch = data._debug_prompt.match(/```json\n([\s\S]*?)\n```/);
                    if (promptMatch) {
                      const jsonPrompt = JSON.parse(promptMatch[1]);
                      if (jsonPrompt.model_answer && jsonPrompt.model_answer.data) {
                        return JSON.stringify(jsonPrompt.model_answer.data, null, 2);
                      }
                    }

                    // OLD: Fallback to old format for backward compatibility
                    const oldModelMatch = data._debug_prompt.match(/TEACHER'S ERD \(MODEL ANSWER\)[\s\S]*?```json\n([\s\S]*?)\n```/);
                    if (oldModelMatch) {
                      return JSON.stringify(JSON.parse(oldModelMatch[1]), null, 2);
                    }

                    return 'Could not extract model answer ERD from prompt';
                  } catch (e) {
                    return `Error parsing model answer ERD JSON: ${e.message}`;
                  }
                })()}
              </div>
            </div>

            <div style={{
              marginTop: '15px',
              fontSize: '0.85em',
              color: '#6b7280',
              fontStyle: 'italic'
            }}>
              💡 This shows the parsed ERD data (entities, relationships, attributes, cardinalities) that was sent to the AI for comparison.
            </div>
          </div>
        )}

        {/* Custom Requirements Indicator */}
        {customRequirements && customRequirements.trim() && (
          <div className="custom-requirements-indicator">
            <FontAwesomeIcon icon={faListCheck} />
            <span>This grading includes custom requirements provided by the instructor.</span>
          </div>
        )}

        {/* Section 1: Overall Grade */}
        {data.score && (
          <div className="waterfall-item">
            <h3>1. Overall Score</h3>
            <div className="grade-score-container">
              <div className={`grade-score ${gradeClass}`}>
                <strong>Score:</strong> {data.score}
              </div>
            </div>
          </div>
        )}

        {/* Section 2: Correctness Analysis */}
        {data.analysis && (
          <div className="waterfall-item">
            <h3>2. Correctness Analysis</h3>
            {data.analysis.correctEntities && (
              <>
                <h4>Correct Entities</h4>
                <p className="feedback-item">{safeRender(data.analysis.correctEntities)}</p>
              </>
            )}
            {data.analysis.missingEntities && (
              <>
                <h4>Missing or Incorrect Entities</h4>
                <p className="feedback-item">{safeRender(data.analysis.missingEntities)}</p>
              </>
            )}
            {data.analysis.correctRelationships && (
              <>
                <h4>Correct Relationships</h4>
                <p className="feedback-item">{safeRender(data.analysis.correctRelationships)}</p>
              </>
            )}
            {data.analysis.incorrectRelationships && (
              <>
                <h4>❌ Incorrect Relationships (Semantic Errors)</h4>
                <p className="feedback-item incorrect-item">{safeRender(data.analysis.incorrectRelationships)}</p>
              </>
            )}
            {data.analysis.missingRelationships && (
              <>
                <h4>Missing Relationships</h4>
                <p className="feedback-item">{safeRender(data.analysis.missingRelationships)}</p>
              </>
            )}
            {data.analysis.primaryKeyAnalysis && (
              <>
                <h4>Primary Key Analysis</h4>
                <p className="feedback-item">{safeRender(data.analysis.primaryKeyAnalysis)}</p>
              </>
            )}
            {data.analysis.inheritanceAnalysis && (
              <>
                <h4>Inheritance/Specialization Analysis</h4>
                <p className="feedback-item">{safeRender(data.analysis.inheritanceAnalysis)}</p>
              </>
            )}
            {data.analysis.cardinalityAnalysis && (
              <>
                <h4>Cardinality Analysis (Semantic Correctness)</h4>
                <p className="feedback-item">{safeRender(data.analysis.cardinalityAnalysis)}</p>
              </>
            )}
            {data.analysis.cardinalities && (
              <>
                <h4>Cardinalities</h4>
                <p className="feedback-item">{safeRender(data.analysis.cardinalities)}</p>
              </>
            )}
          </div>
        )}

        {/* Section 3: Detailed Feedback */}
        {data.feedback && (
          <div className="waterfall-item">
            <h3>3. Detailed Feedback</h3>
            {data.feedback.strengths && (
              <>
                <h4>Strengths</h4>
                <p className="feedback-item">{safeRender(data.feedback.strengths)}</p>
              </>
            )}
            {data.feedback.errors && (
              <>
                <h4>Specific Errors and Misconceptions</h4>
                <p className="feedback-item">{safeRender(data.feedback.errors)}</p>
              </>
            )}
            {data.feedback.missing && (
              <>
                <h4>Missing Components</h4>
                <p className="feedback-item">{safeRender(data.feedback.missing)}</p>
              </>
            )}
          </div>
        )}

        {/* Section 4: Grading Breakdown */}
        {data.breakdown && (
          <div className="waterfall-item">
            <h3>4. Grading Breakdown</h3>
            <div className="grade-breakdown">
              {data.breakdown.entities && (
                <div className="breakdown-item">
                  <strong>Entities:</strong> {data.breakdown.entities} points
                </div>
              )}
              {data.breakdown.relationships && (
                <div className="breakdown-item">
                  <strong>Relationships:</strong> {data.breakdown.relationships} points
                </div>
              )}
              {data.breakdown.inheritance && (
                <div className="breakdown-item">
                  <strong>Inheritance/Specialization:</strong> {data.breakdown.inheritance} points
                </div>
              )}
              {data.breakdown.primaryKeys && (
                <div className="breakdown-item">
                  <strong>Primary Keys:</strong> {data.breakdown.primaryKeys} points
                </div>
              )}
              {data.breakdown.otherAttributes && (
                <div className="breakdown-item">
                  <strong>Other Attributes:</strong> {data.breakdown.otherAttributes} points
                </div>
              )}
              {data.breakdown.cardinalities && (
                <div className="breakdown-item">
                  <strong>Cardinalities & Connections:</strong> {data.breakdown.cardinalities} points
                </div>
              )}
              {data.breakdown.customRequirements && (
                <div className="breakdown-item custom-requirement-breakdown">
                  <strong>🔴 Custom Requirements:</strong> {data.breakdown.customRequirements} points
                </div>
              )}
            </div>
          </div>
        )}

        {/* Section 5: Improvement Suggestions */}
        {data.suggestions && data.suggestions.length > 0 && (
          <div className="waterfall-item">
            <h3>5. Improvement Suggestions</h3>
            {data.suggestions.map((suggestion, index) => (
              suggestion && <p key={index} className="feedback-item">{safeRender(suggestion)}</p>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default GradingSection;
