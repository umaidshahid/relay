import {
  Badge,
  Button,
  Card,
  Collapse,
  Group,
  NativeSelect,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useEffect, useState } from "react";
import {
  createCredential,
  deleteCredential,
  getCredentials,
} from "../api";
import { useAuth } from "../auth";
import type { CredentialResponse } from "../types";

export function CredentialsPage() {
  const { token } = useAuth();
  const [credentials, setCredentials] = useState<CredentialResponse[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const form = useForm({
    initialValues: {
      name: "",
      backend_type: "openai_compat",
      base_url: "",
      credential: "",
    },
    validate: {
      name: (v) => (v.trim() ? null : "Name is required"),
      base_url: (v) => (v.trim() ? null : "Base URL is required"),
    },
  });

  function load() {
    if (!token) return;
    getCredentials(token).then(setCredentials).catch(console.error);
  }

  useEffect(() => { load(); }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreate(values: typeof form.values) {
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await createCredential(token, {
        name: values.name,
        backend_type: values.backend_type,
        base_url: values.base_url,
        credential: values.credential || null,
      });
      form.reset();
      setShowForm(false);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id: string) {
    if (!token) return;
    setDeleteError(null);
    try {
      await deleteCredential(token, id);
      load();
    } catch (e) {
      setDeleteError(
        e instanceof Error ? e.message : "Failed to delete"
      );
    }
  }

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={3}>Backends</Title>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "Add backend"}
        </Button>
      </Group>

      <Collapse in={showForm}>
        <Card withBorder>
          <form onSubmit={form.onSubmit(handleCreate)}>
            <Stack gap="sm">
              <TextInput
                label="Name"
                placeholder="e.g. OpenAI, Local Ollama"
                {...form.getInputProps("name")}
              />
              <NativeSelect
                label="Backend type"
                data={[
                  { value: "openai_compat", label: "OpenAI-compatible (OpenAI, Groq, Together, etc.)" },
                  { value: "ollama", label: "Ollama API (local or remote Ollama instance)" },
                ]}
                {...form.getInputProps("backend_type")}
              />
              <TextInput
                label="Base URL"
                placeholder="https://api.openai.com/v1"
                {...form.getInputProps("base_url")}
              />
              <PasswordInput
                label={
                  form.values.backend_type === "ollama"
                    ? "API key (optional)"
                    : "Provider API key"
                }
                placeholder="sk-..."
                {...form.getInputProps("credential")}
              />
              {error && <Text c="red" size="sm">{error}</Text>}
              <Button type="submit" loading={saving}>Save backend</Button>
            </Stack>
          </form>
        </Card>
      </Collapse>

      {deleteError && <Text c="red" size="sm">{deleteError}</Text>}

      {credentials.length === 0 && !showForm ? (
        <Text c="dimmed">No backends configured yet. Add one to start creating proxy keys.</Text>
      ) : (
        <Stack gap="sm">
          {credentials.map((c) => (
            <Card key={c.id} withBorder>
              <Group justify="space-between" wrap="nowrap">
                <Stack gap={2}>
                  <Group gap="xs">
                    <Text fw={600}>{c.name}</Text>
                    <Badge size="sm" variant="light" color={c.backend_type === "ollama" ? "grape" : "blue"}>
                      {c.backend_type === "ollama" ? "Ollama API" : "OpenAI-compat"}
                    </Badge>
                  </Group>
                  <Text size="sm" c="dimmed">{c.base_url}</Text>
                  {c.credential_masked && (
                    <Text size="xs" c="dimmed">Key: {c.credential_masked}</Text>
                  )}
                </Stack>
                <Button
                  variant="subtle"
                  color="red"
                  size="xs"
                  onClick={() => handleDelete(c.id)}
                >
                  Delete
                </Button>
              </Group>
            </Card>
          ))}
        </Stack>
      )}
    </Stack>
  );
}
