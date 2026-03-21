import { apiDelete, apiGet, apiPostForm, apiPostJson } from "./client";

export interface PatentBatchItemResult {
  url: string;
  patent_id: number | null;
  patent_code?: string | null;
  extracted_images: number;
  extraction_status: string;
  error?: string | null;
  duplicate: boolean;
}

export interface PatentBatchResponse {
  results: PatentBatchItemResult[];
}

export interface JobAcceptedResponse {
  job_id: string;
  status: string;
}

export interface JobLogItem {
  id: number;
  level: string;
  message: string;
  created_at: string;
}

export interface JobStatusResponse {
  job_id: string;
  job_type: string;
  status: string;
  cancel_requested?: boolean;
  error?: string | null;
  logs: JobLogItem[];
  summary?: PatentBatchResponse | ProcessImagesResponse | SearchResponse | null;
}

export interface ProcessFailure {
  image_id: number;
  error: string;
}

export interface ProcessImagesResponse {
  processed_count: number;
  failed_count: number;
  processed_image_ids: number[];
  failures: ProcessFailure[];
  stopped_early?: boolean;
}

export interface UnprocessedCountResponse {
  count: number;
}

export interface SearchResultItem {
  image_id: number;
  similarity: number;
  smiles?: string | null;
  image_url: string;
  patent_code: string;
  page_number?: number | null;
  patent_source_url: string;
}

export interface SearchResponse {
  query_smiles: string;
  results: SearchResultItem[];
}

export interface CompoundBrowserItem {
  compound_id: number;
  patent_id: number;
  patent_code: string;
  patent_source_url: string;
  image_url: string;
  page_number?: number | null;
  processing_status: string;
  smiles?: string | null;
  has_embedding: boolean;
  created_at: string;
  updated_at: string;
  last_error?: string | null;
}

export interface CompoundBrowserResponse {
  items: CompoundBrowserItem[];
  total: number;
  offset: number;
  limit: number;
}

export interface PatentMetadataItem {
  patent_id: number;
  patent_code: string;
  source_url: string;
  extraction_status: string;
  total_compounds: number;
  processed_compounds: number;
  unprocessed_compounds: number;
  failed_compounds: number;
  created_at: string;
  last_error?: string | null;
}

export interface PatentMetadataSummary {
  total_patents: number;
  processed_patents: number;
  unprocessed_patents: number;
}

export interface PatentMetadataResponse {
  items: PatentMetadataItem[];
  summary: PatentMetadataSummary;
  total: number;
  offset: number;
  limit: number;
}

export interface CompoundSelectionResponse {
  affected_count: number;
}

export function uploadPatents(urls: string[]): Promise<JobAcceptedResponse> {
  return apiPostJson<JobAcceptedResponse>("/api/patents/batch", { urls });
}

export function processImages(
  limit: number,
  order: "oldest" | "newest",
  patentCodes: string[] = [],
  compoundIds: number[] = []
): Promise<JobAcceptedResponse> {
  return apiPostJson<JobAcceptedResponse>("/api/images/process", {
    limit,
    order,
    patent_codes: patentCodes,
    compound_ids: compoundIds
  });
}

export function getUnprocessedCount(): Promise<UnprocessedCountResponse> {
  return apiGet<UnprocessedCountResponse>("/api/images/unprocessed-count");
}

export function getCompounds(offset: number, limit: number, patentCode?: string): Promise<CompoundBrowserResponse> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit)
  });
  if (patentCode) {
    params.set("patent_code", patentCode);
  }
  return apiGet<CompoundBrowserResponse>(`/api/compounds?${params.toString()}`);
}

export function getPatentCodes(): Promise<string[]> {
  return apiGet<string[]>("/api/patents/codes");
}

export function getPatentMetadata(offset: number, limit: number, patentCode?: string): Promise<PatentMetadataResponse> {
  const params = new URLSearchParams({
    offset: String(offset),
    limit: String(limit)
  });
  if (patentCode) {
    params.set("patent_code", patentCode);
  }
  return apiGet<PatentMetadataResponse>(`/api/patents/metadata?${params.toString()}`);
}

export function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  return apiGet<JobStatusResponse>(`/api/jobs/${jobId}`);
}

export function cancelJob(jobId: string): Promise<JobAcceptedResponse> {
  return apiPostJson<JobAcceptedResponse>(`/api/jobs/${jobId}/cancel`, {});
}

export function searchByImage(file: File, k: number): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("k", String(k));
  return apiPostForm<SearchResponse>("/api/search/image", formData);
}

export function searchByImageJob(file: File, k: number): Promise<JobAcceptedResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("k", String(k));
  return apiPostForm<JobAcceptedResponse>("/api/search/image-job", formData);
}

export function searchBySmilesJob(smiles: string, k: number): Promise<JobAcceptedResponse> {
  const formData = new FormData();
  formData.append("smiles", smiles);
  formData.append("k", String(k));
  return apiPostForm<JobAcceptedResponse>("/api/search/smiles-job", formData);
}

export function deleteCompounds(compoundIds: number[]): Promise<CompoundSelectionResponse> {
  return apiPostJson<CompoundSelectionResponse>("/api/compounds/delete", { compound_ids: compoundIds });
}

export function reprocessCompounds(compoundIds: number[]): Promise<JobAcceptedResponse> {
  return apiPostJson<JobAcceptedResponse>("/api/compounds/reprocess", { compound_ids: compoundIds });
}

export async function deletePatent(patentCode: string): Promise<CompoundSelectionResponse> {
  return apiDelete<CompoundSelectionResponse>(`/api/compounds/patent/${encodeURIComponent(patentCode)}`);
}
