"use client";

import { useCallback, useEffect, useState } from "react";
import * as api from "@/lib/api";
import type {
  Attribute,
  OutputArtifact,
  Project,
  Question,
  ReviewItem,
} from "@/lib/types";

interface Loadable<T> {
  data: T | undefined;
  loading: boolean;
  error: string | undefined;
  refresh: () => void;
}

export function useProject(projectId: string): Loadable<Project> {
  const [data, setData] = useState<Project>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getProject(projectId)
      .then((p) => !cancelled && setData(p))
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [projectId, tick]);

  return { data, loading, error, refresh: () => setTick((t) => t + 1) };
}

export function useAttributes(projectId: string): Loadable<Attribute[]> {
  const [data, setData] = useState<Attribute[]>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listAttributes(projectId)
      .then((a) => !cancelled && setData(a))
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [projectId, tick]);

  return { data, loading, error, refresh: () => setTick((t) => t + 1) };
}

export function useQuestions(projectId: string): Loadable<Question[]> {
  const [data, setData] = useState<Question[]>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listQuestions(projectId)
      .then((q) => !cancelled && setData(q))
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [projectId, tick]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, refresh };
}

export function useReviewItems(projectId: string): Loadable<ReviewItem[]> {
  const [data, setData] = useState<ReviewItem[]>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listReviewItems(projectId)
      .then((r) => !cancelled && setData(r))
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [projectId, tick]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, refresh };
}

export function useOutputs(projectId: string): Loadable<OutputArtifact[]> {
  const [data, setData] = useState<OutputArtifact[]>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>();
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .listOutputs(projectId)
      .then((o) => !cancelled && setData(o))
      .catch((e) => !cancelled && setError(String(e)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [projectId, tick]);

  const refresh = useCallback(() => setTick((t) => t + 1), []);
  return { data, loading, error, refresh };
}
