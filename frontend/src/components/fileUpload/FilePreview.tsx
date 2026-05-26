import { useEffect, useState } from "react";

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
    return <p className="m-0 text-slate-500">{content}</p>;
  }

  return (
    <pre className="m-0 whitespace-pre-wrap break-words rounded-lg bg-slate-100 p-3 text-sm text-slate-800">
      {content}
    </pre>
  );
}

function FilePreview({ fileUrl, fileType = "", fileName = "" }: FilePreviewProps) {
  const kind = resolvePreviewKind(fileType, fileName);

  if (kind === "image") {
    return (
      <div className="mt-5 max-h-[500px] overflow-auto">
        <img
          src={fileUrl}
          alt={fileName || "Preview"}
          className="block h-auto max-w-full rounded-lg"
        />
      </div>
    );
  }

  if (kind === "pdf") {
    return (
      <div className="mt-5 max-h-[500px] overflow-auto">
        <iframe
          src={fileUrl}
          title={fileName || "PDF preview"}
          className="min-h-[360px] w-full rounded-lg border border-slate-300"
        />
      </div>
    );
  }

  if (kind === "text") {
    return (
      <div className="mt-5 max-h-[500px] overflow-auto">
        <TextFilePreview fileUrl={fileUrl} />
      </div>
    );
  }

  return (
    <div className="mt-5 max-h-[500px] overflow-auto">
      <p className="m-0 text-slate-500">
        Preview is not available for this file type.{" "}
        <a
          href={fileUrl}
          target="_blank"
          rel="noreferrer"
          className="text-blue-400 hover:underline"
        >
          Open file
        </a>
      </p>
    </div>
  );
}

export default FilePreview;
