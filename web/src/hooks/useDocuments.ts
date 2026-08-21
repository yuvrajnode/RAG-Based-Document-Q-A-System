import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { DocumentSummary, Stats, UploadOutcome } from "../lib/types";

export function useDocuments() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [list, currentStats] = await Promise.all([api.listDocuments(), api.stats()]);
      setDocuments(list.documents);
      setStats(currentStats);
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "could not reach the API");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /** Uploads run sequentially: ingestion is CPU-bound, and a parallel drop of
   *  twenty files would just queue behind itself with a less useful progress
   *  readout. */
  const upload = useCallback(
    async (files: File[]): Promise<UploadOutcome[]> => {
      setUploading(true);
      const outcomes: UploadOutcome[] = [];
      try {
        for (const file of files) {
          outcomes.push(await api.upload(file));
        }
        await refresh();
      } finally {
        setUploading(false);
      }
      return outcomes;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await api.deleteDocument(id);
      await refresh();
    },
    [refresh],
  );

  const clear = useCallback(async () => {
    await api.clearDocuments();
    await refresh();
  }, [refresh]);

  return { documents, stats, loading, uploading, error, refresh, upload, remove, clear };
}
