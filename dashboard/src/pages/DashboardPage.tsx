import { ActionIcon, Group, Stack, Text, Tooltip } from "@mantine/core";
import { IconRefresh } from "@tabler/icons-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  getByKey,
  getByModel,
  getRequests,
  getSummary,
  getTimeseries,
} from "../api";
import { useAuth } from "../auth";
import { BreakdownTable } from "../components/BreakdownTable";
import { RequestLog } from "../components/RequestLog";
import { SummaryCards } from "../components/SummaryCards";
import { TpsChart } from "../components/TpsChart";
import type {
  KeyBreakdown,
  ModelBreakdown,
  RequestsResponse,
  Summary,
  TimeseriesPoint,
} from "../types";

const REFRESH_INTERVAL_MS = 30_000;

export function DashboardPage() {
  const { token } = useAuth();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [byKey, setByKey] = useState<KeyBreakdown[]>([]);
  const [byModel, setByModel] = useState<ModelBreakdown[]>([]);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const requestOffsetRef = useRef(0);

  const loadRequests = useCallback(
    (offset: number) => {
      if (!token) return;
      requestOffsetRef.current = offset;
      getRequests(token, 10, offset).then(setRequests).catch(console.error);
    },
    [token]
  );

  const loadAll = useCallback(async () => {
    if (!token) return;
    setRefreshing(true);
    try {
      await Promise.all([
        getSummary(token).then(setSummary),
        getByKey(token).then(setByKey),
        getByModel(token).then(setByModel),
        getTimeseries(token, 30).then(setTimeseries),
        getRequests(token, 10, requestOffsetRef.current).then(setRequests),
      ]);
      setLastRefreshed(new Date());
    } catch (err) {
      console.error(err);
    } finally {
      setRefreshing(false);
    }
  }, [token]);

  // Initial load
  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(loadAll, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [loadAll]);

  return (
    <Stack gap="md">
      <Group justify="flex-end" align="center" gap="xs">
        {lastRefreshed && (
          <Text size="xs" c="dimmed">
            Updated {lastRefreshed.toLocaleTimeString()}
          </Text>
        )}
        <Tooltip label="Refresh now">
          <ActionIcon
            variant="subtle"
            onClick={loadAll}
            loading={refreshing}
            aria-label="Refresh"
          >
            <IconRefresh size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <SummaryCards data={summary} />
      <TpsChart data={timeseries} />
      <BreakdownTable byKey={byKey} byModel={byModel} />
      <RequestLog data={requests} onPageChange={loadRequests} />
    </Stack>
  );
}
