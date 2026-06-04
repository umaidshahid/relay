import { Badge, Card, Group, Pagination, Table, Text, Title } from "@mantine/core";
import { useState } from "react";
import type { RequestRecord, RequestsResponse } from "../types";

const PAGE_SIZE = 10;

interface Props {
  data: RequestsResponse | null;
  onPageChange: (offset: number) => void;
}

function TokenCell({ value, source }: { value: number; source: "exact" | "estimated" }) {
  if (source === "estimated") {
    return (
      <Text span title="Token count is estimated (tiktoken fallback)">
        ~{value.toLocaleString()}
      </Text>
    );
  }
  return <>{value.toLocaleString()}</>;
}

function StatusBadge({ code }: { code: number }) {
  const color = code < 300 ? "green" : code < 500 ? "yellow" : "red";
  return <Badge color={color} variant="light" size="sm">{code}</Badge>;
}

function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleString();
}

export function RequestLog({ data, onPageChange }: Props) {
  const [activePage, setActivePage] = useState(1);

  if (!data) {
    return (
      <Card shadow="sm" padding="lg" radius="md" withBorder>
        <Title order={4} mb="md">Request Log</Title>
        <Text c="dimmed">Loading…</Text>
      </Card>
    );
  }

  const totalPages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));

  function handlePageChange(page: number) {
    setActivePage(page);
    onPageChange((page - 1) * PAGE_SIZE);
  }

  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Group justify="space-between" mb="md">
        <Title order={4}>Request Log</Title>
        <Text size="sm" c="dimmed">{data.total.toLocaleString()} total</Text>
      </Group>

      {data.items.length === 0 ? (
        <Text c="dimmed">No requests recorded yet.</Text>
      ) : (
        <>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Timestamp</Table.Th>
                <Table.Th>Key</Table.Th>
                <Table.Th>Model</Table.Th>
                <Table.Th>Backend</Table.Th>
                <Table.Th>Input</Table.Th>
                <Table.Th>Output</Table.Th>
                <Table.Th>t/s</Table.Th>
                <Table.Th>Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data.items.map((row: RequestRecord) => (
                <Table.Tr key={row.id}>
                  <Table.Td>
                    <Text size="xs" c="dimmed">{formatTimestamp(row.timestamp)}</Text>
                  </Table.Td>
                  <Table.Td>{row.proxy_key_label}</Table.Td>
                  <Table.Td>{row.model}</Table.Td>
                  <Table.Td>{row.backend_type}</Table.Td>
                  <Table.Td>
                    <TokenCell value={row.input_tokens} source={row.token_count_source} />
                  </Table.Td>
                  <Table.Td>
                    <TokenCell value={row.output_tokens} source={row.token_count_source} />
                  </Table.Td>
                  <Table.Td>
                    {row.tokens_per_second !== null ? `${row.tokens_per_second}` : "—"}
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge code={row.status_code} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>

          <Group justify="space-between" align="center" mt="md">
            <Text size="xs" c="dimmed">
              Page {activePage} of {totalPages}
            </Text>
            <Pagination
              total={totalPages}
              value={activePage}
              onChange={handlePageChange}
              size="sm"
            />
          </Group>
        </>
      )}
    </Card>
  );
}
