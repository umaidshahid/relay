import { Card, Grid, Text, Title } from "@mantine/core";
import type { Summary } from "../types";

interface Props {
  data: Summary | null;
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

export function SummaryCards({ data }: Props) {
  if (!data) {
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

  return (
    <Grid>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard label="Total Requests" value={formatNumber(data.total_requests)} />
      </Grid.Col>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard label="Input Tokens" value={formatNumber(data.total_input_tokens)} />
      </Grid.Col>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard label="Output Tokens" value={formatNumber(data.total_output_tokens)} />
      </Grid.Col>
      <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
        <StatCard
          label="Avg Tokens / sec"
          value={data.avg_tokens_per_second !== null ? `${data.avg_tokens_per_second} t/s` : "—"}
        />
      </Grid.Col>
    </Grid>
  );
}
