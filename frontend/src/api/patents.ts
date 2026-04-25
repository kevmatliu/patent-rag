import { apiDelete, apiGet, apiPostForm, apiPostJson, apiPostNoBody } from "./client";

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

export interface SimilarCoreRecommendationItem {
  core_smiles: string;
  apply_core_smiles: string;
  score: number;
  support_count: number;
  reason: string;
}

export interface RGroupRecommendationItem {
  rgroup_smiles: string;
  count: number;
  reason: string;
}

export interface ApplyModificationResponse {
  smiles: string;
  core_smiles: string;
}

export interface DecomposedStructureRGroupItem {
  r_label: string;
  r_group: string;
}

export interface DecomposeStructureResponse {
  canonical_smiles: string;
  reduced_core: string;
  labeled_core_smiles: string;
  attachment_points: string[];
  r_groups: DecomposedStructureRGroupItem[];
}

export interface SmilesSvgResponse {
  svg: string;
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
  canonical_smiles?: string | null;
  validation_status?: string | null;
  is_compound?: boolean | null;
  is_duplicate_within_patent: boolean;
  duplicate_of_compound_id?: number | null;
  kept_for_series_analysis: boolean;
  murcko_scaffold_smiles?: string | null;
  reduced_core?: string | null;
  core_smiles?: string | null;
  core_smarts?: string | null;
  validation_error?: string | null;
  pipeline_version?: string | null;
  has_embedding: boolean;
  created_at: string;
  updated_at: string;
  last_error?: string | null;
}

export interface CompoundRGroupItem {
  compound_id: number;
  patent_id: number;
  core_smiles?: string | null;
  core_smarts?: string | null;
  r_label: string;
  r_group: string;
  pipeline_version?: string | null;
  created_at: string;
}

export interface CompoundRGroupResponse {
  compound_id: number;
  items: CompoundRGroupItem[];
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

export interface ResetDatabaseResponse {
  patents_deleted: number;
  compounds_deleted: number;
  jobs_deleted: number;
  logs_deleted: number;
  files_deleted: number;
}

export function uploadPatents(urls: string[]): Promise<JobAcceptedResponse> {
  return apiPostJson<JobAcceptedResponse>("/api/patents/batch", { urls });
}

export function uploadPatentPdfs(files: File[]): Promise<JobAcceptedResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  return apiPostForm<JobAcceptedResponse>("/api/patents/upload-pdfs", formData);
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

export function searchByStructureJob(payload: {
  core_smiles?: string;
  r_groups: Record<string, string>;
  k?: number;
}): Promise<JobAcceptedResponse> {
  return apiPostJson<JobAcceptedResponse>("/api/search/structure-job", payload);
}

export function recommendSimilarCores(coreSmiles: string, k = 20): Promise<SimilarCoreRecommendationItem[]> {
  return apiPostJson<SimilarCoreRecommendationItem[]>("/recommend/similar-cores", {
    core_smiles: coreSmiles,
    k
  });
}

export function recommendRGroups(
  coreSmiles: string,
  attachmentPoint: string,
  k = 20
): Promise<RGroupRecommendationItem[]> {
  return apiPostJson<RGroupRecommendationItem[]>("/recommend/rgroups", {
    core_smiles: coreSmiles,
    attachment_point: attachmentPoint,
    k
  });
}

export function applyModification(payload: {
  current_smiles: string;
  target_core_smiles?: string;
  attachment_point?: string;
  rgroup_smiles?: string;
}): Promise<ApplyModificationResponse> {
  return apiPostJson<ApplyModificationResponse>("/recommend/apply-modification", payload);
}

export function decomposeStructure(currentSmiles: string): Promise<DecomposeStructureResponse> {
  return apiPostJson<DecomposeStructureResponse>("/recommend/decompose-structure", {
    current_smiles: currentSmiles
  });
}

export function renderSmilesSvg(smiles: string): Promise<SmilesSvgResponse> {
  return apiPostJson<SmilesSvgResponse>("/api/format/smiles-to-svg", {
    struct: smiles
  });
}

export function deleteCompounds(compoundIds: number[]): Promise<CompoundSelectionResponse> {
  return apiPostJson<CompoundSelectionResponse>("/api/compounds/delete", { compound_ids: compoundIds });
}

export function reprocessCompounds(compoundIds: number[]): Promise<JobAcceptedResponse> {
  return apiPostJson<JobAcceptedResponse>("/api/compounds/reprocess", { compound_ids: compoundIds });
}

export function getCompoundRGroups(compoundId: number): Promise<CompoundRGroupResponse> {
  return apiGet<CompoundRGroupResponse>(`/api/compounds/${compoundId}/r-groups`);
}

export async function deletePatent(patentCode: string): Promise<CompoundSelectionResponse> {
  return apiDelete<CompoundSelectionResponse>(`/api/compounds/patent/${encodeURIComponent(patentCode)}`);
}

export function resetDatabase(): Promise<ResetDatabaseResponse> {
  return apiPostNoBody<ResetDatabaseResponse>("/api/admin/reset-database");
}
