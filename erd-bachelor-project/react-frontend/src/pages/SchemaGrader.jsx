import { useState } from 'react';
import FileUploader from '../components/FileUploader';
import SchemaUploader from '../components/SchemaUploader';
import SchemaGradingResults from '../components/SchemaGradingResults';
import Loader from '../components/Loader';

function SchemaGrader() {
  const [studentFile, setStudentFile] = useState(null);
  const [studentErd, setStudentErd] = useState(null);
  const [evaluationSchema, setEvaluationSchema] = useState(null);
  const [useDefaultSchema, setUseDefaultSchema] = useState(true);
  const [gradingResults, setGradingResults] = useState(null);
  const [isGrading, setIsGrading] = useState(false);
  const [error, setError] = useState(null);

  const handleStudentFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setStudentFile(file);
    setError(null);

    // Convert student ERD file
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:5001/api/convert', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Failed to convert student ERD');
      }

      const data = await response.json();
      setStudentErd(data.erd);
    } catch (err) {
      setError(err.message);
      console.error('Error converting student ERD:', err);
    }
  };

  const handleSchemaUpload = (schema) => {
    setEvaluationSchema(schema);
    setUseDefaultSchema(false);
  };

  const handleGradeNow = async () => {
    if (!studentErd) {
      setError('Please upload a student ERD file first');
      return;
    }

    setIsGrading(true);
    setError(null);
    setGradingResults(null);

    try {
      // Load default schema if needed
      let schema = evaluationSchema;
      if (useDefaultSchema) {
        const response = await fetch('/evaluation_schema.json');
        schema = await response.json();
      }

      // Call grading API
      const response = await fetch('http://localhost:5001/api/grade_with_schema', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          student_erd: studentErd,
          evaluation_schema: schema,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Grading failed');
      }

      const results = await response.json();
      setGradingResults(results);
    } catch (err) {
      setError(err.message);
      console.error('Error grading ERD:', err);
    } finally {
      setIsGrading(false);
    }
  };

  return (
    <div className="schema-grader-page">
      <div className="schema-grader-header">
        <h2>Schema-Based ERD Grading</h2>
        <p>Grade student ERDs using a structured evaluation rubric</p>
      </div>

      {error && (
        <div className="error-banner">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="grading-workflow">
        {/* Step 1: Upload Student ERD */}
        <div className="workflow-step">
          <div className="step-header">
            <span className="step-number">1</span>
            <h3>Upload Student ERD</h3>
          </div>
          <FileUploader
            id="student-erd-upload"
            onChange={handleStudentFileUpload}
            fileName={studentFile?.name}
            label="Select student's ERD file (SVG or GraphML)"
          />
          {studentErd && (
            <div className="success-indicator">
              ✓ Student ERD loaded: {studentErd.entities?.length || 0} entities, {studentErd.relationships?.length || 0} relationships
            </div>
          )}
        </div>

        {/* Step 2: Evaluation Schema */}
        <div className="workflow-step">
          <div className="step-header">
            <span className="step-number">2</span>
            <h3>Evaluation Schema</h3>
          </div>

          <div className="schema-options">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={useDefaultSchema}
                onChange={(e) => setUseDefaultSchema(e.target.checked)}
              />
              Use default evaluation schema (Milestone 1 - HR System)
            </label>

            {!useDefaultSchema && (
              <SchemaUploader onSchemaUpload={handleSchemaUpload} />
            )}

            {(useDefaultSchema || evaluationSchema) && (
              <div className="success-indicator">
                ✓ Schema loaded: {useDefaultSchema ? 'Default (173 points)' : 'Custom'}
              </div>
            )}
          </div>
        </div>

        {/* Step 3: Grade */}
        <div className="workflow-step">
          <div className="step-header">
            <span className="step-number">3</span>
            <h3>Generate Grade</h3>
          </div>

          <button
            className="grade-button"
            onClick={handleGradeNow}
            disabled={!studentErd || isGrading}
          >
            {isGrading ? 'Grading...' : 'Grade Student Work'}
          </button>
        </div>
      </div>

      {/* Loading State */}
      {isGrading && (
        <div className="grading-loader">
          <Loader />
          <p>Analyzing student ERD against evaluation schema...</p>
        </div>
      )}

      {/* Results */}
      {gradingResults && !isGrading && (
        <SchemaGradingResults results={gradingResults} />
      )}
    </div>
  );
}

export default SchemaGrader;
