import { useState } from 'react';

function SchemaUploader({ onSchemaUpload }) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragEnter = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFileInput = (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      handleFile(files[0]);
    }
  };

  const handleFile = async (file) => {
    if (!file.name.endsWith('.json')) {
      alert('Please upload a JSON file');
      return;
    }

    try {
      const text = await file.text();
      const schema = JSON.parse(text);
      onSchemaUpload(schema);
    } catch (error) {
      alert('Error parsing JSON file: ' + error.message);
      console.error('JSON parse error:', error);
    }
  };

  return (
    <div
      className={`schema-uploader ${isDragging ? 'dragging' : ''}`}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <div className="upload-content">
        <div className="upload-icon">📄</div>
        <p className="upload-text">
          Drag & drop your evaluation schema JSON file here
        </p>
        <p className="upload-subtext">or</p>
        <label className="upload-button">
          Choose JSON File
          <input
            type="file"
            accept=".json"
            onChange={handleFileInput}
            style={{ display: 'none' }}
          />
        </label>
      </div>
    </div>
  );
}

export default SchemaUploader;
