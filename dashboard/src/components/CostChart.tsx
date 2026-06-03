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

export function CostChart({ data }: Props) {
  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Title order={4} mb="md">
        Daily Cost (last 30 days)
      </Title>
      {data.length === 0 ? (
        <Text c="dimmed">No data yet.</Text>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} />
            <YAxis
              tickFormatter={(v: number) => `$${v.toFixed(3)}`}
              tick={{ fontSize: 11 }}
            />
            <Tooltip
              formatter={(value: number) => [`$${value.toFixed(4)}`, "Cost"]}
            />
            <Line
              type="monotone"
              dataKey="total_cost"
              stroke="#228be6"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}
