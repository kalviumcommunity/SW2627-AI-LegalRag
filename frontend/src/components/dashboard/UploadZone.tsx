import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Card } from '../common/Card';
import { DoodleArrow } from '../common/Illustrations';
import { documentsApi } from '../../api/documents';
import { useToast } from '../common/Toast';
import type { IngestResponse } from '../../api/types';

interface UploadZoneProps {
  onUploadSuccess?: (doc: IngestResponse) => void;
}

export const UploadZone: React.FC<UploadZoneProps> = ({ onUploadSuccess }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showSuccess, showError } = useToast();

  const MAX_BYTES = 10 * 1024 * 1024; // 10MB
  const ALLOWED_EXTS = ['.pdf', '.txt', '.md'];

  const validateFile = (file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      return `Unsupported file format (${ext}). Only PDF, TXT, and Markdown files are supported.`;
    }
    if (file.size > MAX_BYTES) {
      return `File exceeds maximum upload size of 10 MB (${(file.size / (1024 * 1024)).toFixed(2)} MB).`;
    }
    if (file.size === 0) {
      return 'File is empty (0 bytes). Please upload a valid document.';
    }
    return null;
  };

  const processUpload = async (file: File) => {
    const error = validateFile(file);
    if (error) {
      setUploadError(error);
      showError(error);
      return;
    }

    setUploadError(null);
    setIsUploading(true);

    try {
      const response = await documentsApi.ingest(file);
      if (response.status === 'processed') {
        showSuccess(`"${file.name}" ingested successfully with ${response.chunk_count} chunks.`);
      } else if (response.status === 'ocr_required') {
        showSuccess(`"${file.name}" uploaded, but requires OCR (${response.detail || 'scanned content'}).`);
      } else {
        showError(response.detail || 'Document processing failed.');
      }
      if (onUploadSuccess) {
        onUploadSuccess(response);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed. Check backend connection.';
      setUploadError(msg);
      showError(msg);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processUpload(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      processUpload(e.target.files[0]);
    }
  };

  return (
    <Card
      padding="none"
      style={{
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'stretch',
        backgroundColor: '#FFFFFF',
        borderRadius: 'var(--radius-card)',
        overflow: 'hidden',
      }}
    >
      {/* Left: Drag & Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        style={{
          flex: '1 1 65%',
          margin: '1.25rem',
          padding: '2.25rem 1.5rem',
          borderRadius: '16px',
          border: `2px dashed ${isDragging ? '#7C3AED' : '#C4B5FD'}`,
          backgroundColor: isDragging ? '#EDE9FE' : '#FAF8FF',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          textAlign: 'center',
          transition: 'all 0.2s ease',
          cursor: isUploading ? 'wait' : 'pointer',
        }}
        onClick={() => {
          if (!isUploading && fileInputRef.current) {
            fileInputRef.current.click();
          }
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md"
          onChange={handleFileChange}
          style={{ display: 'none' }}
          disabled={isUploading}
        />

        {/* Cloud Upload Icon */}
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '50%',
            backgroundColor: '#EDE9FE',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#6D28D9',
            marginBottom: '1rem',
          }}
        >
          {isUploading ? (
            <Loader2 size={28} className="animate-spin" />
          ) : (
            <UploadCloud size={28} />
          )}
        </div>

        <h3
          style={{
            fontSize: '1.15rem',
            fontWeight: 700,
            color: '#18181B',
            marginBottom: '0.4rem',
          }}
        >
          {isUploading ? 'Processing & Embedding Document...' : 'Upload a property document'}
        </h3>

        <p
          style={{
            fontSize: '0.875rem',
            color: '#6B7280',
            marginBottom: '1.25rem',
            maxWidth: '320px',
          }}
        >
          {isUploading
            ? 'Extracting clean text, chunking, and creating embeddings...'
            : 'Drag and drop a PDF, TXT, or MD file here or click to browse'}
        </p>

        <button
          type="button"
          disabled={isUploading}
          className="btn-primary"
          style={{
            backgroundColor: '#312E81',
            padding: '0.65rem 1.75rem',
          }}
          onClick={(e) => {
            e.stopPropagation();
            fileInputRef.current?.click();
          }}
        >
          {isUploading ? 'Uploading...' : 'Choose a file'}
        </button>

        {uploadError && (
          <div
            style={{
              marginTop: '1rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              color: '#DC2626',
              fontSize: '0.8125rem',
              fontWeight: 500,
            }}
          >
            <AlertCircle size={15} />
            <span>{uploadError}</span>
          </div>
        )}
      </div>

      {/* Right: Format Pills & Handwritten Callout */}
      <div
        style={{
          flex: '1 1 35%',
          padding: '2rem 1.75rem 1.5rem 0.5rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
        }}
      >
        {/* Pills list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                backgroundColor: '#FEE2E2',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#DC2626',
              }}
            >
              <FileText size={16} />
            </div>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#374151' }}>
              PDF documents
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                backgroundColor: '#DBEAFE',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#2563EB',
              }}
            >
              <FileText size={16} />
            </div>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#374151' }}>
              Text files (.txt)
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                backgroundColor: '#EDE9FE',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#7C3AED',
              }}
            >
              <FileText size={16} />
            </div>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#374151' }}>
              Markdown files (.md)
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '8px',
                backgroundColor: '#DCFCE7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#16A34A',
              }}
            >
              <CheckCircle2 size={16} />
            </div>
            <span style={{ fontSize: '0.875rem', fontWeight: 600, color: '#374151' }}>
              Max size: 10 MB
            </span>
          </div>
        </div>

        {/* Playful Handwritten annotation with arrow */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'flex-end',
            gap: '0.25rem',
            marginTop: '1rem',
          }}
        >
          <div style={{ transform: 'rotate(-15deg)' }}>
            <DoodleArrow direction="down-right" color="#4338CA" />
          </div>
          <span
            className="handwritten"
            style={{
              color: '#4338CA',
              fontSize: '1.25rem',
              lineHeight: 1.15,
              transform: 'rotate(-3deg)',
              maxWidth: '140px',
            }}
          >
            Legal docs, reports, leases and more!
          </span>
        </div>
      </div>
    </Card>
  );
};
