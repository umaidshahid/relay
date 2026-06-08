import { Card, Grid, Text, Title } from "@mantine/core";
import type { Summary } from "../types";

interface Props {
  data: Summary | null;
  loaded: boolean;
}

function StatCard({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Text size="sm" c="dimmed" tt="uppercase" fw={600} mb={4}>
        {label}
      </Text>
      <Title order={3}>{value}</Title>
    </Card>
  );
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

export function SummaryCards({ data, loaded }: Props) {
  // Only show the loading placeholder until the first fetch resolves. Once
  // loaded, a brand-new user simply has zeros — which is meaningful, not a
  // loading state.
  if (!data && !loaded) {
    return (
      <Grid>
        {[1, 2, 3, 4].map((i) => (
          <Grid.Col key={i} span={{ base: 12, sm: 6, md: 3 }}>
            <Card shadow="sm" padding="lg" radius="md" withBorder>
              <Text c="dimmed">Loading…</Text>
            </Card>
          </Grid.Col>
        ))}
      </Grid>
    );
  }

  const summary = data ?? {
    total_cost: 0,
    total_requests: 0,
    total_input_tokens: 0,
    total_output_tokens: 0,
    avg_tokens_per_second: null,
  };

  return (
    <Grid>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard label="Total Requests" value={formatNumber(summary.total_requests)} />
      </Grid.Col>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard label="Input Tokens" value={formatNumber(summary.total_input_tokens)} />
      </Grid.Col>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard label="Output Tokens" value={formatNumber(summary.total_output_tokens)} />
      </Grid.Col>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard
          label="Avg Tokens / sec"
          value={summary.avg_tokens_per_second !== null ? `${summary.avg_tokens_per_second} t/s` : "—"}
        />
      </Grid.Col>
    </Grid>
  );
}
