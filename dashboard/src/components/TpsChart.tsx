import { Card, Text, Title } from "@mantine/core";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TimeseriesPoint } from "../types";

interface Props {
  data: TimeseriesPoint[];
}

export function TpsChart({ data }: Props) {
  const hasData = data.some((d) => d.avg_tokens_per_second !== null && d.avg_tokens_per_second !== undefined);

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Title order={4} mb="md">
        Avg Tokens / sec (last 30 days)
      </Title>
      {!hasData ? (
        <Text c="dimmed">No data yet.</Text>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis
              tickFormatter={(v: number) => `${v} t/s`}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(value: number) => [`${value} t/s`, "Avg tokens/sec"]}
            />
            <Line
              type="monotone"
              dataKey="avg_tokens_per_second"
              stroke="#12b886"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
