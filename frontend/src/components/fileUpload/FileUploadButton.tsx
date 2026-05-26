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
    <label
      className={`mt-1.5 inline-flex w-fit cursor-pointer rounded-[10px] bg-gradient-to-br from-blue-600 to-blue-700 px-[18px] py-2.5 text-[0.95rem] font-semibold text-white shadow-[0_12px_30px_rgba(37,99,235,0.35)] transition hover:-translate-y-px hover:shadow-[0_14px_34px_rgba(37,99,235,0.45)] ${className}`.trim()}
    >
      {label}
      <input type="file" className="hidden" onChange={handleFileChange} />
    </label>
  );
}

export default FileUploadButton;
