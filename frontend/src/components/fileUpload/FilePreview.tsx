import { useEffect, useState } from "react";
import "./FileUpload.css";

type PreviewKind = "image" | "pdf" | "text" | "unsupported";

type FilePreviewProps = {
  fileUrl: string;
  fileType?: string;
  fileName?: string;
};

function resolvePreviewKind(
  fileType: string,
  fileName: string
): PreviewKind {
  const mime = fileType.toLowerCase();
  const name = fileName.toLowerCase();

  if (mime.startsWith("image/") || /\.(png|jpe?g|gif|webp)$/i.test(name)) {
    return "image";
  }
  if (mime === "application/pdf" || name.endsWith(".pdf")) {
    return "pdf";
  }
  if (mime.startsWith("text/") || name.endsWith(".txt")) {
    return "text";
  }
  return "unsupported";
}

function TextFilePreview({ fileUrl }: { fileUrl: string }) {
  const [content, setContent] = useState<string>("Loading preview...");
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const response = await fetch(fileUrl);
        if (!response.ok) {
          throw new Error("Failed to load file");
        }
        const text = await response.text();
        if (!cancelled) {
          setContent(text);
          setError(false);
        }
      } catch {
        if (!cancelled) {
          setError(true);
          setContent("Could not load text preview.");
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [fileUrl]);

  if (error) {
    return <p className="file-preview-fallback">{content}</p>;
  }

  return <pre className="file-preview-text">{content}</pre>;
}

function FilePreview({ fileUrl, fileType = "", fileName = "" }: FilePreviewProps) {
  const kind = resolvePreviewKind(fileType, fileName);

  if (kind === "image") {
    return (
      <div className="file-preview">
        <img src={fileUrl} alt={fileName || "Preview"} className="file-preview-image" />
      </div>
    );
  }

  if (kind === "pdf") {
    return (
      <div className="file-preview">
        <iframe
          src={fileUrl}
          title={fileName || "PDF preview"}
          className="file-preview-frame"
        />
      </div>
    );
  }

  if (kind === "text") {
    return (
      <div className="file-preview">
        <TextFilePreview fileUrl={fileUrl} />
      </div>
    );
  }

  return (
    <div className="file-preview">
      <p className="file-preview-fallback">
        Preview is not available for this file type.{" "}
        <a href={fileUrl} target="_blank" rel="noreferrer">
          Open file
        </a>
      </p>
    </div>
  );
}

export default FilePreview;
