import { AppShell, Burger, Group, NavLink, Stack, Title } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useCallback, useEffect, useState } from "react";
import {
  getByKey,
  getByModel,
  getRequests,
  getSummary,
  getTimeseries,
} from "./api";
import { BreakdownTable } from "./components/BreakdownTable";
import { CostChart } from "./components/CostChart";
import { RequestLog } from "./components/RequestLog";
import { SummaryCards } from "./components/SummaryCards";
import type {
  KeyBreakdown,
  ModelBreakdown,
  RequestsResponse,
  Summary,
  TimeseriesPoint,
} from "./types";

export default function App() {
  const [opened, { toggle }] = useDisclosure();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [byKey, setByKey] = useState<KeyBreakdown[]>([]);
  const [byModel, setByModel] = useState<ModelBreakdown[]>([]);
  const [timeseries, setTimeseries] = useState<TimeseriesPoint[]>([]);
  const [requests, setRequests] = useState<RequestsResponse | null>(null);

  const loadRequests = useCallback((offset: number) => {
    getRequests(50, offset)
      .then(setRequests)
      .catch(console.error);
  }, []);

  useEffect(() => {
    getSummary().then(setSummary).catch(console.error);
    getByKey().then(setByKey).catch(console.error);
    getByModel().then(setByModel).catch(console.error);
    getTimeseries(30).then(setTimeseries).catch(console.error);
    loadRequests(0);
  }, [loadRequests]);

  return (
    <AppShell
      header={{ height: 56 }}
      navbar={{ width: 200, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
          <Title order={3}>Relay</Title>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <NavLink label="Dashboard" active />
      </AppShell.Navbar>

      <AppShell.Main>
        <Stack gap="md">
          <SummaryCards data={summary} />
          <CostChart data={timeseries} />
          <BreakdownTable byKey={byKey} byModel={byModel} />
          <RequestLog data={requests} onPageChange={loadRequests} />
        </Stack>
      </AppShell.Main>
    </AppShell>
  );
}
