import React, { useEffect, useState, useCallback } from 'react';
import {
  FileText,
  Table as TableIcon,
  Copy,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  Clock,
  ChevronDown,
  ChevronUp,
  Tag,
  ShieldAlert,
  Edit2,
  Check,
  X,
  Layers,
} from 'lucide-react';
import { Card } from '../common/Card';
import { DocumentOcrStatusBadge, DocumentCategoryBadge, StatusBadge } from '../common/Badge';
import { documentsApi } from '../../api/documents';
import { useToast } from '../common/Toast';
import type {
  DocumentClassificationCategory,
  DocumentProcessingStatusResponse,
  DocumentDuplicatesResponse,
  ExtractedTablesResponse,
  ExtractedTable,
} from '../../api/types';

const ALL_CATEGORIES: DocumentClassificationCategory[] = [
  'Sale Deed',
  'Title Deed',
  'Allotment Letter',
  'Agreement to Sell',
  'Encumbrance Certificate',
  'Occupancy Certificate',
  'Completion Certificate',
  'Building Plan Approval',
  'RERA Registration',
  'Property Tax Receipt',
  'Payment Receipt',
  'Loan or Mortgage Document',
  'Legal Notice',
  'Litigation Document',
  'Other / Unknown',
];

interface DocumentIntelligencePanelProps {
  documentId: string;
  onRefresh?: () => void;
}

export const DocumentIntelligencePanel: React.FC<DocumentIntelligencePanelProps> = ({
  documentId,
  onRefresh,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [reprocessing, setReprocessing] = useState<boolean>(false);
  const [updatingCategory, setUpdatingCategory] = useState<boolean>(false);
  const [isEditingCategory, setIsEditingCategory] = useState<boolean>(false);
  const [selectedCategory, setSelectedCategory] = useState<DocumentClassificationCategory>('Other / Unknown');

  const [statusData, setStatusData] = useState<DocumentProcessingStatusResponse | null>(null);
  const [duplicatesData, setDuplicatesData] = useState<DocumentDuplicatesResponse | null>(null);
  const [tablesData, setTablesData] = useState<ExtractedTablesResponse | null>(null);
  const [expandedTableId, setExpandedTableId] = useState<string | null>(null);

  const { showSuccess, showError } = useToast();

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [statusRes, dupsRes, tablesRes] = await Promise.allSettled([
        documentsApi.getProcessingStatus(documentId),
        documentsApi.getDuplicates(documentId),
        documentsApi.getTables(documentId),
      ]);

      if (statusRes.status === 'fulfilled') {
        setStatusData(statusRes.value);
        if (statusRes.value.classification_category) {
          setSelectedCategory(statusRes.value.classification_category);
        }
      }
      if (dupsRes.status === 'fulfilled') {
        setDuplicatesData(dupsRes.value);
      }
      if (tablesRes.status === 'fulfilled') {
        setTablesData(tablesRes.value);
        if (tablesRes.value.tables.length > 0) {
          setExpandedTableId(tablesRes.value.tables[0].table_id);
        }
      }
    } catch (err: unknown) {
      console.warn('Failed to load document intelligence:', err);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleReprocess = async () => {
    try {
      setReprocessing(true);
      await documentsApi.reprocess(documentId);
      showSuccess('Document re-processed through intelligence pipeline');
      await loadData();
      onRefresh?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Re-processing failed';
      showError(msg);
    } finally {
      setReprocessing(false);
    }
  };

  const handleSaveCategory = async () => {
    try {
      setUpdatingCategory(true);
      const updated = await documentsApi.updateClassification(documentId, selectedCategory);
      showSuccess(`Document category updated to "${updated.category}"`);
      setIsEditingCategory(false);
      await loadData();
      onRefresh?.();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update category';
      showError(msg);
    } finally {
      setUpdatingCategory(false);
    }
  };

  if (loading) {
    return (
      <Card className="p-5 mb-6 animate-pulse">
        <div className="h-6 bg-slate-200 rounded w-1/4 mb-4"></div>
        <div className="h-24 bg-slate-100 rounded mb-4"></div>
        <div className="h-24 bg-slate-100 rounded"></div>
      </Card>
    );
  }

  const exactDuplicates = duplicatesData?.exact_matches || [];
  const nearDuplicates = duplicatesData?.near_matches || [];
  const tables = tablesData?.tables || [];

  return (
    <div className="space-y-6 mb-8">
      {/* 1. Duplicate Warning Banner */}
      {exactDuplicates.length > 0 && (
        <div
          data-testid="exact-duplicate-warning"
          style={{
            backgroundColor: '#FEF2F2',
            border: '1px solid #F87171',
            borderRadius: '0.75rem',
            padding: '1rem 1.25rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.75rem',
          }}
        >
          <ShieldAlert className="text-red-600 mt-0.5 flex-shrink-0" size={20} />
          <div className="space-y-1">
            <h4 style={{ fontWeight: 700, color: '#991B1B', fontSize: '0.925rem' }}>
              Duplicate Upload Detected
            </h4>
            <p style={{ color: '#B91C1C', fontSize: '0.85rem' }}>
              This file has identical binary content to previously uploaded document(s):{' '}
              <strong>{exactDuplicates.map((d) => d.filename).join(', ')}</strong>.
            </p>
            <p style={{ color: '#7F1D1D', fontSize: '0.75rem', fontStyle: 'italic' }}>
              Non-destructive note: Duplicate copies are preserved for review and do not alter existing titles.
            </p>
          </div>
        </div>
      )}

      {nearDuplicates.length > 0 && (
        <div
          data-testid="near-duplicate-warning"
          style={{
            backgroundColor: '#FFFBEB',
            border: '1px solid #FCD34D',
            borderRadius: '0.75rem',
            padding: '1rem 1.25rem',
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.75rem',
          }}
        >
          <AlertTriangle className="text-amber-600 mt-0.5 flex-shrink-0" size={20} />
          <div className="space-y-1">
            <h4 style={{ fontWeight: 700, color: '#92400E', fontSize: '0.925rem' }}>
              Potential Near-Duplicate Document
            </h4>
            <ul className="text-xs text-amber-800 space-y-1 mt-1">
              {nearDuplicates.map((nd) => (
                <li key={nd.document_id}>
                  • <strong>{nd.filename}</strong>: {Math.round(nd.similarity * 100)}% textual similarity
                  {nd.reasons.length > 0 ? ` (${nd.reasons[0]})` : ''}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* 2. Main Intelligence Card */}
      <Card className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <div
              style={{
                backgroundColor: '#EFF6FF',
                color: '#2563EB',
                padding: '0.5rem',
                borderRadius: '0.5rem',
              }}
            >
              <FileText size={20} />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-lg flex items-center gap-2">
                Advanced Document Intelligence
              </h3>
              <p className="text-xs text-slate-500">
                Automated OCR, legal classification, row-level table extraction, and duplicate detection
              </p>
            </div>
          </div>

          <button
            onClick={handleReprocess}
            disabled={reprocessing}
            className="btn btn-secondary flex items-center gap-2 text-xs"
            title="Re-run OCR, table extraction, and document classification"
          >
            <RefreshCw size={14} className={reprocessing ? 'animate-spin' : ''} />
            <span>{reprocessing ? 'Processing...' : 'Reprocess Document'}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          {/* Classification Column */}
          <div className="bg-slate-50/70 p-4 rounded-xl border border-slate-100 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Document Classification
              </span>
              {!isEditingCategory && (
                <button
                  onClick={() => setIsEditingCategory(true)}
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium flex items-center gap-1"
                >
                  <Edit2 size={12} />
                  <span>Correct</span>
                </button>
              )}
            </div>

            {!isEditingCategory ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <DocumentCategoryBadge
                    category={statusData?.classification_category || 'Other / Unknown'}
                    confidence={statusData?.classification_confidence}
                    manuallyCorrected={statusData?.classification_manually_corrected}
                    size="md"
                  />
                  {statusData?.classification_confidence !== undefined &&
                    statusData?.classification_confidence !== null && (
                      <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-200 text-slate-700">
                        {Math.round(statusData.classification_confidence * 100)}% confidence
                      </span>
                    )}
                </div>

                {statusData?.classification_reasoning && (
                  <p className="text-xs text-slate-600 bg-white p-2.5 rounded-lg border border-slate-200/80 leading-relaxed">
                    <span className="font-semibold text-slate-700">Classification basis:</span>{' '}
                    {statusData.classification_reasoning}
                  </p>
                )}
              </div>
            ) : (
              <div className="space-y-3 bg-white p-3 rounded-lg border border-indigo-200">
                <label className="text-xs font-semibold text-slate-700 block">
                  Select correct legal document type:
                </label>
                <select
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value as DocumentClassificationCategory)}
                  className="w-full text-xs p-2 border border-slate-300 rounded focus:ring-2 focus:ring-indigo-500 focus:outline-none"
                >
                  {ALL_CATEGORIES.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>

                <div className="flex items-center gap-2 justify-end">
                  <button
                    onClick={() => setIsEditingCategory(false)}
                    disabled={updatingCategory}
                    className="btn btn-secondary text-xs px-2.5 py-1"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSaveCategory}
                    disabled={updatingCategory}
                    className="btn btn-primary text-xs px-3 py-1 flex items-center gap-1"
                  >
                    {updatingCategory ? (
                      <RefreshCw size={12} className="animate-spin" />
                    ) : (
                      <Check size={12} />
                    )}
                    <span>Save</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* OCR Lifecycle Column */}
          <div className="bg-slate-50/70 p-4 rounded-xl border border-slate-100 space-y-3">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
              OCR & Scan Processing
            </span>

            <div className="space-y-2">
              <div className="flex items-center gap-2 flex-wrap">
                <StatusBadge status={statusData?.status || 'processed'} size="sm" />
                {statusData?.ocr_status && (
                  <DocumentOcrStatusBadge status={statusData.ocr_status} size="sm" />
                )}
              </div>

              <div className="text-xs text-slate-600 space-y-1">
                <div>
                  <span className="text-slate-400">Total Pages:</span>{' '}
                  <strong className="text-slate-700">{statusData?.page_count ?? 'N/A'}</strong>
                </div>
                <div>
                  <span className="text-slate-400">Extracted Characters:</span>{' '}
                  <strong className="text-slate-700">
                    {statusData?.extracted_characters.toLocaleString()}
                  </strong>
                </div>
                <div>
                  <span className="text-slate-400">Indexed Chunks:</span>{' '}
                  <strong className="text-slate-700">{statusData?.chunk_count}</strong>
                </div>
              </div>

              {statusData?.ocr_status === 'needs_manual_review' && (
                <div className="text-xs text-orange-800 bg-orange-50 p-2 rounded border border-orange-200">
                  Document scan contained blank or low-contrast pages. Manual review recommended.
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 3. Extracted Structured Tables Section */}
        <div className="mt-8 border-t border-slate-100 pt-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TableIcon size={18} className="text-indigo-600" />
              <h4 className="font-bold text-slate-800 text-sm">
                Extracted Structured Tables ({tables.length})
              </h4>
            </div>
            <span className="text-xs text-slate-500">
              Row relationships preserved without value mixing
            </span>
          </div>

          {tables.length === 0 ? (
            <div className="bg-slate-50/50 border border-dashed border-slate-200 rounded-lg p-6 text-center text-xs text-slate-500">
              No tabular financial schedules or area measurements detected in this document text.
            </div>
          ) : (
            <div className="space-y-4">
              {tables.map((tbl: ExtractedTable, idx: number) => {
                const isExpanded = expandedTableId === tbl.table_id;
                return (
                  <div
                    key={tbl.table_id || idx}
                    className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm"
                  >
                    <button
                      onClick={() =>
                        setExpandedTableId(isExpanded ? null : tbl.table_id)
                      }
                      className="w-full px-4 py-3 bg-slate-50/80 hover:bg-slate-100/80 flex items-center justify-between text-left transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-xs font-bold text-slate-800">
                          {tbl.title || `Table #${idx + 1}`}
                        </span>
                        {tbl.category && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase">
                            {tbl.category.replace('_', ' ')}
                          </span>
                        )}
                        {tbl.page_number && (
                          <span className="text-[11px] text-slate-500 font-mono">
                            Page {tbl.page_number}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-400">
                          {tbl.rows.length} rows × {tbl.headers.length} columns
                        </span>
                        {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="p-4 overflow-x-auto">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead>
                            <tr className="border-b-2 border-slate-200 bg-slate-50">
                              {tbl.headers.map((h, i) => (
                                <th
                                  key={i}
                                  className="py-2.5 px-3 font-semibold text-slate-700 uppercase tracking-wider text-[11px]"
                                >
                                  {h}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {tbl.rows.map((r, rIdx) => (
                              <tr
                                key={rIdx}
                                className={rIdx % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'}
                              >
                                {r.map((c, cIdx) => (
                                  <td
                                    key={cIdx}
                                    className="py-2 px-3 text-slate-800 font-medium"
                                  >
                                    {c}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
};

