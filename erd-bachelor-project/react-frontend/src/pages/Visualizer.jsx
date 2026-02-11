import { useState } from 'react';
import FileUploader from '../components/FileUploader';
import Loader from '../components/Loader';
import ERDDisplay from '../components/ERDDisplay';
import GradingSection from '../components/GradingSection';

function Visualizer() {
  const [file1, setFile1] = useState(null);
  const [file2, setFile2] = useState(null);
  const [file1Name, setFile1Name] = useState('');
  const [file2Name, setFile2Name] = useState('');
  const [currentData1, setCurrentData1] = useState(null);
  const [currentData2, setCurrentData2] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleFile1Change = (e) => {
    if (e.target.files[0]) {
      setFile1(e.target.files[0]);
      setFile1Name(e.target.files[0].name);
    }
  };

  const handleFile2Change = (e) => {
    if (e.target.files[0]) {
      setFile2(e.target.files[0]);
      setFile2Name(e.target.files[0].name);
    }
  };

  const handleConvert = async () => {
    if (!file1) {
      alert('Please upload the Student ERD file to begin.');
      return;
    }

    try {
      setLoading(true);
      setError('');

      // Convert file 1
      const fd1 = new FormData();
      fd1.append('file', file1);
      const res1 = await fetch('/api/convert', { method: 'POST', body: fd1 });

      if (!res1.ok) {
        const errorText = await res1.text();
        throw new Error(`Failed to convert student file. Server responded with ${res1.status} ${res1.statusText}. Details: ${errorText}`);
      }

      const data1 = await res1.json();
      setCurrentData1(data1.erd);

      // Convert file 2 if exists
      if (file2) {
        const fd2 = new FormData();
        fd2.append('file', file2);
        const res2 = await fetch('/api/convert', { method: 'POST', body: fd2 });

        if (!res2.ok) {
          const errorText = await res2.text();
          throw new Error(`Failed to convert model answer file. Server responded with ${res2.status} ${res2.statusText}. Details: ${errorText}`);
        }

        const data2 = await res2.json();
        setCurrentData2(data2.erd);
      } else {
        setCurrentData2(null);
      }
    } catch (err) {
      setError(err.message);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content">
      <div className="uploader-grid">
        <FileUploader
          id="file1"
          label="Student ERD (SVG/GraphML/XML)"
          onChange={handleFile1Change}
          fileName={file1Name}
        />
        <FileUploader
          id="file2"
          label="Model Answer ERD (SVG/GraphML/XML)"
          onChange={handleFile2Change}
          fileName={file2Name}
          isTeacher={true}
        />
      </div>

      <div className="controls-row">
        <button
          onClick={handleConvert}
          className="g-button g-button-contained"
          disabled={loading}
        >
          {loading ? <div className="g-spinner"></div> : 'Convert & Render'}
        </button>
      </div>

      {error && (
        <p style={{ color: 'var(--google-red)', textAlign: 'center', marginTop: '20px' }}>
          {error}
        </p>
      )}

      {loading && <Loader text="Processing files..." />}

      {!loading && currentData1 && (
        <>
          <div id="statsSection">
            <h2 className="section-title" style={{ textAlign: 'center', marginBottom: '20px', borderBottom: 'none' }}>
              Statistics
            </h2>
            <StatsDisplay data1={currentData1} data2={currentData2} />
          </div>

          <ERDDisplay
            data1={currentData1}
            data2={currentData2}
            file1Name={file1Name}
            file2Name={file2Name}
          />

          {currentData2 && (
            <GradingSection
              studentData={currentData1}
              teacherData={currentData2}
            />
          )}
        </>
      )}

      {!loading && !currentData1 && !error && (
        <p style={{ color: 'var(--text-secondary)', textAlign: 'center', marginTop: '50px' }}>
          Please upload an ERD file (SVG, GraphML, or XML) to get started.
        </p>
      )}
    </div>
  );
}

function StatsDisplay({ data1, data2 }) {
  if (data2) {
    return (
      <div className="stats-comparison-grid">
        <div>
          <h3 style={{ textAlign: 'center', color: 'var(--google-blue)', marginBottom: '15px' }}>
            Student ERD
          </h3>
          <div className="stats stats-file1">
            <div className="stat-card">
              <h3>{data1.entities.length}</h3>
              <p>Entities</p>
            </div>
            <div className="stat-card">
              <h3>{data1.relationships.length}</h3>
              <p>Relationships</p>
            </div>
            <div className="stat-card">
              <h3>{(data1.inheritances || []).length}</h3>
              <p>Inheritance</p>
            </div>
          </div>
        </div>
        <div>
          <h3 style={{ textAlign: 'center', color: 'var(--text-secondary)', marginBottom: '15px' }}>
            Model Answer ERD
          </h3>
          <div className="stats stats-file2">
            <div className="stat-card">
              <h3>{data2.entities.length}</h3>
              <p>Entities</p>
            </div>
            <div className="stat-card">
              <h3>{data2.relationships.length}</h3>
              <p>Relationships</p>
            </div>
            <div className="stat-card">
              <h3>{(data2.inheritances || []).length}</h3>
              <p>Inheritance</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="stats stats-file1">
      <div className="stat-card">
        <h3>{data1.entities.length}</h3>
        <p>Entities</p>
      </div>
      <div className="stat-card">
        <h3>{data1.relationships.length}</h3>
        <p>Relationships</p>
      </div>
      <div className="stat-card">
        <h3>{(data1.inheritances || []).length}</h3>
        <p>Inheritance</p>
      </div>
    </div>
  );
}

export default Visualizer;
