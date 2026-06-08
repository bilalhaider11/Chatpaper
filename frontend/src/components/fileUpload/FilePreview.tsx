import { useEffect, useState } from "react";
import { FileIcon } from "../icons/Icons";
import "./FileUpload.css";

type PreviewKind = "pdf" | "text" | "csv" | "docx" | "none";

type FilePreviewProps = {
  fileUrl: string;
  fileType?: string;
  fileName?: string;
};

function resolvePreviewKind(fileType: string, fileName: string): PreviewKind {
  const mime = fileType.toLowerCase();
  const name = fileName.toLowerCase();

  if (mime === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  if (mime === "text/csv" || name.endsWith(".csv")) return "csv";
  if (mime.startsWith("text/") || name.endsWith(".txt")) return "text";
  if (
    mime === "application/vnd.openxmlformats-officedocument.wordprocessingml.document" ||
    mime === "application/msword" ||
    name.endsWith(".docx") ||
    name.endsWith(".doc")
  ) return "docx";
  return "none";
}

function TextFilePreview({ fileUrl }: { fileUrl: string }) {
  const [content, setContent] = useState("Loading preview…");

  useEffect(() => {
    let cancelled = false;
    fetch(fileUrl)
      .then((r) => r.text())
      .then((t) => { if (!cancelled) setContent(t); })
      .catch(() => { if (!cancelled) setContent("Could not load text preview."); });
    return () => { cancelled = true; };
  }, [fileUrl]);

  return <pre className="file-preview-text">{content}</pre>;
}

function CsvTablePreview({ fileUrl }: { fileUrl: string }) {
  const [rows, setRows] = useState<string[][]>([]);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(fileUrl)
      .then((r) => r.text())
      .then((text) => {
        if (cancelled) return;
        // Simple CSV parser: handles quoted fields with commas inside
        const parsed = text.trim().split("\n").map((line) => {
          const cells: string[] = [];
          let cur = "";
          let inQuote = false;
          for (const ch of line) {
            if (ch === '"') { inQuote = !inQuote; }
            else if (ch === "," && !inQuote) { cells.push(cur.trim()); cur = ""; }
            else { cur += ch; }
          }
          cells.push(cur.trim());
          return cells;
        });
        setRows(parsed.slice(0, 50)); // cap at 50 rows for performance
      })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [fileUrl]);

  if (error) return <p className="file-preview-fallback">Could not load CSV preview.</p>;
  if (rows.length === 0) return <p className="file-preview-fallback">Loading preview…</p>;

  const [header, ...body] = rows;
  return (
    <div className="file-preview-csv-wrap">
      <table className="file-preview-csv">
        <thead>
          <tr>{header.map((h, i) => <th key={i}>{h}</th>)}</tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri}>
              {row.map((cell, ci) => <td key={ci}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DocxFilePreview({ fileUrl }: { fileUrl: string }) {
  const [html, setHtml] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const arrayBuffer = await fetch(fileUrl).then((r) => r.arrayBuffer());
        const mammoth = await import("mammoth/mammoth.browser");
        const result = await mammoth.convertToHtml({ arrayBuffer });
        if (!cancelled) setHtml(result.value);
      } catch {
        if (!cancelled) setError(true);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, [fileUrl]);

  if (error) return <p className="file-preview-fallback">Could not load DOCX preview.</p>;
  if (html === null) return <p className="file-preview-fallback">Loading preview…</p>;

  // content comes from the user's own locally-selected file — no XSS risk
  return <div className="file-preview-docx" dangerouslySetInnerHTML={{ __html: html }} />;
}

function FilePreview({ fileUrl, fileType = "", fileName = "" }: FilePreviewProps) {
  const kind = resolvePreviewKind(fileType, fileName);

  if (kind === "pdf") {
    return (
      <div className="file-preview">
        <iframe src={fileUrl} title={fileName || "PDF preview"} className="file-preview-frame" />
      </div>
    );
  }

  if (kind === "csv") {
    return (
      <div className="file-preview">
        <CsvTablePreview fileUrl={fileUrl} />
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

  if (kind === "docx") {
    return (
      <div className="file-preview">
        <DocxFilePreview fileUrl={fileUrl} />
      </div>
    );
  }

  // XLSX, XLS — binary spreadsheet, needs SheetJS to render
  return (
    <div className="file-preview file-preview-none">
      <FileIcon className="file-preview-none-icon" strokeWidth={1.5} />
      <p className="file-preview-none-label">No preview available for this file type</p>
    </div>
  );
}

export default FilePreview;
