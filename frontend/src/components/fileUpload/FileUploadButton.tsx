import "./FileUpload.css";

type FileUploadButtonProps = {
  onFileSelect: (file: File | null) => void;
  label?: string;
  className?: string;
};

function FileUploadButton({
  onFileSelect,
  label = "Select File",
  className = "",
}: FileUploadButtonProps) {
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    onFileSelect(event.target.files?.[0] ?? null);
    event.target.value = "";
  };

  return (
    <label className={`upload-button ${className}`.trim()}>
      {label}
      <input
        type="file"
        className="upload-input"
        onChange={handleFileChange}
      />
    </label>
  );
}

export default FileUploadButton;
