import { Card, Table, Tabs, Title } from "@mantine/core";
import type { KeyBreakdown, ModelBreakdown } from "../types";

interface Props {
  byKey: KeyBreakdown[];
  byModel: ModelBreakdown[];
}

function formatNumber(value: number): string {
  return value.toLocaleString();
}

function KeyTable({ rows }: { rows: KeyBreakdown[] }) {
  if (rows.length === 0) {
    return <Table.Tr><Table.Td colSpan={3}>No data yet.</Table.Td></Table.Tr>;
  }
  return (
    <>
      {rows.map((row) => (
        <Table.Tr key={row.proxy_key_id}>
          <Table.Td>{row.proxy_key_label}</Table.Td>
          <Table.Td>{formatNumber(row.total_requests)}</Table.Td>
          <Table.Td>
            {formatNumber(row.total_input_tokens)} / {formatNumber(row.total_output_tokens)}
          </Table.Td>
        </Table.Tr>
      ))}
    </>
  );
}

function ModelTable({ rows }: { rows: ModelBreakdown[] }) {
  if (rows.length === 0) {
    return <Table.Tr><Table.Td colSpan={4}>No data yet.</Table.Td></Table.Tr>;
  }
  return (
    <>
      {rows.map((row) => (
        <Table.Tr key={`${row.model}-${row.backend_type}`}>
          <Table.Td>{row.model}</Table.Td>
          <Table.Td>{row.backend_type}</Table.Td>
          <Table.Td>{formatNumber(row.total_requests)}</Table.Td>
          <Table.Td>
            {formatNumber(row.total_input_tokens)} / {formatNumber(row.total_output_tokens)}
          </Table.Td>
        </Table.Tr>
      ))}
    </>
  );
}

export function BreakdownTable({ byKey, byModel }: Props) {
  return (
    <Card shadow="sm" padding="lg" radius="md" withBorder>
      <Title order={4} mb="md">
        Breakdown
      </Title>
      <Tabs defaultValue="by-key">
        <Tabs.List>
          <Tabs.Tab value="by-key">By API Key</Tabs.Tab>
          <Tabs.Tab value="by-model">By Model</Tabs.Tab>
        </Tabs.List>

        <Tabs.Panel value="by-key" pt="sm">
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Key</Table.Th>
                <Table.Th>Requests</Table.Th>
                <Table.Th>In / Out Tokens</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              <KeyTable rows={byKey} />
            </Table.Tbody>
          </Table>
        </Tabs.Panel>

        <Tabs.Panel value="by-model" pt="sm">
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Model</Table.Th>
                <Table.Th>Backend</Table.Th>
                <Table.Th>Requests</Table.Th>
                <Table.Th>In / Out Tokens</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              <ModelTable rows={byModel} />
            </Table.Tbody>
          </Table>
        </Tabs.Panel>
      </Tabs>
    </Card>
  );
}
