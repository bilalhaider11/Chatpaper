import { useState } from "react";
import "./FileUpload.css";

function FileUpload() {
  const [fileName, setFileName] = useState<string>("");

  const handleFileChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];

    if (file) {
      setFileName(file.name);
    }
  };

  return (
    <div className="upload-card">
      <h2 className="upload-card-title">Upload your file</h2>
      <p className="upload-card-subtitle">
        Choose a document to start secure processing.
      </p>

      <label className="upload-button">
        Select File
        <input
          type="file"
          className="upload-input"
          onChange={handleFileChange}
        />
      </label>

      {fileName && (
        <p className="selected-file">
          Selected file: <strong>{fileName}</strong>
        </p>
      )}
    </div>
  );
}

export default FileUpload;