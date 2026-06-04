import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Collapse,
  Group,
  Modal,
  NativeSelect,
  NumberInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useCallback, useEffect, useState } from "react";
import { createKey, getCredentials, getKeys, revokeKey } from "../api";
import { useAuth } from "../auth";
import type { CredentialResponse, ProxyKeyResponse } from "../types";

export function KeysPage() {
  const { token } = useAuth();
  const [keys, setKeys] = useState<ProxyKeyResponse[]>([]);
  const [credentials, setCredentials] = useState<CredentialResponse[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const form = useForm({
    initialValues: {
      label: "",
      backend_config_id: "",
      requests_per_minute: "" as string | number,
    },
    validate: {
      backend_config_id: (v) => (v ? null : "Select a backend"),
    },
  });

  const load = useCallback(() => {
    if (!token) return;
    getKeys(token).then(setKeys).catch(console.error);
    getCredentials(token).then(setCredentials).catch(console.error);
  }, [token]);

  useEffect(() => { load(); }, [load]);

  // Pre-select first backend when credentials load
  useEffect(() => {
    if (credentials.length > 0 && !form.values.backend_config_id) {
      form.setFieldValue("backend_config_id", credentials[0]?.id ?? "");
    }
  }, [credentials]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate(values: typeof form.values) {
    if (!token) return;
    setCreating(true);
    setError(null);
    try {
      const rpmVal = values.requests_per_minute;
      const rpm = typeof rpmVal === "number" && rpmVal > 0 ? rpmVal : null;
      const resp = await createKey(token, {
        label: values.label || undefined,
        backend_config_id: values.backend_config_id,
        requests_per_minute: rpm,
      });
      setNewKey(resp.key);
      form.reset();
      setShowForm(false);
      load();
    } catch {
      setError("Failed to create key");
    } finally {
      setCreating(false);
    }
  }

  async function handleRevoke(id: string) {
    if (!token) return;
    try {
      await revokeKey(token, id);
      load();
    } catch {
      setError("Failed to revoke key");
    }
  }

  return (
    <Stack gap="md">
      {/* One-time key modal */}
      <Modal
        opened={!!newKey}
        onClose={() => setNewKey(null)}
        title="Key created — copy it now"
      >
        <Alert color="yellow" mb="sm">
          This is the only time the full key is shown. Copy it somewhere safe.
        </Alert>
        <Code block>{newKey}</Code>
        <Button mt="md" fullWidth onClick={() => setNewKey(null)}>
          I've saved it
        </Button>
      </Modal>

      <Group justify="space-between">
        <Title order={3}>Proxy Keys</Title>
        <Button
          size="sm"
          onClick={() => setShowForm((v) => !v)}
          disabled={credentials.length === 0}
        >
          {showForm ? "Cancel" : "Create key"}
        </Button>
      </Group>

      {credentials.length === 0 && (
        <Alert color="blue">
          Add a backend on the Credentials page before creating proxy keys.
        </Alert>
      )}

      <Collapse in={showForm}>
        <Card withBorder>
          <form onSubmit={form.onSubmit(handleCreate)}>
            <Stack gap="sm">
              <TextInput
                label="Label (optional)"
                placeholder="e.g. my-app"
                {...form.getInputProps("label")}
              />
              <NativeSelect
                label="Backend"
                data={credentials.map((c) => ({ value: c.id, label: c.name }))}
                {...form.getInputProps("backend_config_id")}
              />
              <NumberInput
                label="Rate limit (requests / minute)"
                description="Leave blank for unlimited"
                placeholder="e.g. 60"
                min={1}
                {...form.getInputProps("requests_per_minute")}
              />
              {error && <Text c="red" size="sm">{error}</Text>}
              <Button type="submit" loading={creating}>Create key</Button>
            </Stack>
          </form>
        </Card>
      </Collapse>

      {keys.length === 0 ? (
        <Text c="dimmed">No proxy keys yet.</Text>
      ) : (
        <Stack gap="sm">
          {keys.map((k) => (
            <Card key={k.id} withBorder>
              <Group justify="space-between" wrap="nowrap">
                <Stack gap={2}>
                  <Group gap="xs">
                    <Text fw={500}>{k.label ?? "(unlabelled)"}</Text>
                    {k.backend_name && (
                      <Badge size="sm" variant="light" color="teal">
                        {k.backend_name}
                      </Badge>
                    )}
                    {k.requests_per_minute && (
                      <Badge size="sm" variant="light" color="orange">
                        {k.requests_per_minute} req/min
                      </Badge>
                    )}
                  </Group>
                  <Code>{k.display}</Code>
                </Stack>
                <Button
                  variant="subtle"
                  color="red"
                  size="xs"
                  onClick={() => handleRevoke(k.id)}
                >
                  Revoke
                </Button>
              </Group>
            </Card>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
