import { useState } from 'react';

function FileUploader({ id, label, onChange, fileName, isTeacher = false }) {
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
    if (files && files.length > 0) {
      // Create a synthetic event to match the expected onChange signature
      const syntheticEvent = {
        target: {
          files: files
        }
      };
      onChange(syntheticEvent);
    }
  };

  return (
    <div className="file-uploader-wrapper">
      <label className="file-uploader-label-text">{label}</label>
      <form className="file-upload-form">
        <label
          htmlFor={id}
          className={`file-upload-label ${isDragging ? 'dragging' : ''} ${isTeacher ? 'theme-teacher' : ''}`}
          onDragEnter={handleDragEnter}
          onDragLeave={handleDragLeave}
          onDragOver={handleDragOver}
          onDrop={handleDrop}
        >
          <div className="file-upload-design">
            <svg viewBox="0 0 640 512" height="1em">
              <path d="M144 480C64.5 480 0 415.5 0 336c0-62.8 40.2-116.2 96.2-135.9c-.1-2.7-.2-5.4-.2-8.1c0-88.4 71.6-160 160-160c59.3 0 111 32.2 138.7 80.2C409.9 102 428.3 96 448 96c53 0 96 43 96 96c0 12.2-2.3 23.8-6.4 34.6C596 238.4 640 290.1 640 352c0 70.7-57.3 128-128 128H144zm79-217c-9.4 9.4-9.4 24.6 0 33.9s24.6 9.4 33.9 0l39-39V392c0 13.3 10.7 24 24 24s24-10.7 24-24V257.9l39 39c9.4 9.4 24.6 9.4 33.9 0s9.4-24.6 0-33.9l-80-80c-9.4-9.4-24.6-9.4-33.9 0l-80 80z"></path>
            </svg>
            <p className="drag-drop-text">Drag and Drop</p>
            <p className="or-text">or</p>
            <span className="browse-button">Browse file</span>
          </div>
          <input
            id={id}
            type="file"
            accept=".svg"
            onChange={onChange}
            style={{ display: 'none' }}
          />
        </label>
      </form>
      {fileName && (
        <p className={`upload-file-name ${isTeacher ? 'theme-teacher' : ''}`}>
          {fileName}
        </p>
      )}
    </div>
  );
}

export default FileUploader;
