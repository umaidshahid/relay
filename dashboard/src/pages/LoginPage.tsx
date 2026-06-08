import {
  Anchor,
  Button,
  Center,
  Divider,
  Group,
  Paper,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useToggle, upperFirst } from "@mantine/hooks";
import { IconBrandGithub, IconBrandGoogle } from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { getAuthConfig, register, startOAuth, type AuthConfig } from "../api";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [type, toggle] = useToggle(["login", "register"] as const);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [oauth, setOauth] = useState<AuthConfig>({ google: false, github: false });
  const [oauthPending, setOauthPending] = useState<null | "google" | "github">(null);

  // Discover which OAuth providers the backend has configured so we only
  // enable the buttons that will actually work.
  useEffect(() => {
    getAuthConfig()
      .then(setOauth)
      .catch(() => setOauth({ google: false, github: false }));
  }, []);

  async function handleOAuth(provider: "google" | "github") {
    setError(null);
    setOauthPending(provider);
    try {
      await startOAuth(provider); // redirects the browser away on success
    } catch {
      setError(`Could not start ${provider} sign-in. Try again.`);
      setOauthPending(null);
    }
  }

  const form = useForm({
    initialValues: { email: "", password: "" },
    validate: {
      email: (v) => (/^\S+@\S+$/.test(v) ? null : "Invalid email"),
      password: (v) =>
        type === "register" && v.length < 8
          ? "Password must be at least 8 characters"
          : v.length < 6
          ? "Password too short"
          : null,
    },
  });

  async function handleSubmit(values: { email: string; password: string }) {
    setError(null);
    setLoading(true);
    try {
      if (type === "register") {
        await register(values.email, values.password);
      }
      await login(values.email, values.password);
      navigate("/app");
    } catch (e) {
      setError(
        type === "register"
          ? (e instanceof Error ? e.message : "Registration failed")
          : "Invalid email or password"
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Center mih="100vh" bg="var(--mantine-color-body)">
      <Stack align="center" gap="lg" w="100%" maw={480} px="md">
        <Stack align="center" gap={4}>
          <Title order={1} fw={800} size={32}>Relay</Title>
          <Text c="dimmed" size="sm">Self-hosted LLM proxy</Text>
        </Stack>

        <Paper radius="md" p="xl" withBorder w="100%">
          <Text size="lg" fw={500} mb="md">
            {type === "login" ? "Welcome back" : "Create your account"}
          </Text>

          <Stack gap="sm">
            <Button
              fullWidth
              radius="xl"
              variant="default"
              leftSection={<IconBrandGoogle size={18} />}
              disabled={!oauth.google}
              loading={oauthPending === "google"}
              onClick={() => handleOAuth("google")}
              title={oauth.google ? undefined : "Google OAuth not configured"}
            >
              Continue with Google
            </Button>
            <Button
              fullWidth
              radius="xl"
              variant="default"
              leftSection={<IconBrandGithub size={18} />}
              disabled={!oauth.github}
              loading={oauthPending === "github"}
              onClick={() => handleOAuth("github")}
              title={oauth.github ? undefined : "GitHub OAuth not configured"}
            >
              Continue with GitHub
            </Button>
          </Stack>

          <Divider label="Or continue with email" labelPosition="center" my="lg" />

          <form onSubmit={form.onSubmit(handleSubmit)}>
            <Stack>
              <TextInput
                required
                label="Email"
                placeholder="you@example.com"
                radius="md"
                {...form.getInputProps("email")}
              />
              <PasswordInput
                required
                label="Password"
                placeholder={type === "register" ? "Min. 8 characters" : "Your password"}
                radius="md"
                {...form.getInputProps("password")}
              />
              {error && <Text c="red" size="sm">{error}</Text>}
            </Stack>

            <Group justify="space-between" mt="xl">
              <Anchor
                component="button"
                type="button"
                size="xs"
                onClick={() => { toggle(); setError(null); form.reset(); }}
              >
                {type === "register"
                  ? "Already have an account? Sign in"
                  : "No account? Sign up"}
              </Anchor>
              <Button type="submit" radius="xl" loading={loading}>
                {upperFirst(type === "login" ? "sign in" : "sign up")}
              </Button>
            </Group>
          </form>
        </Paper>

        <Anchor size="sm" c="dimmed" onClick={() => navigate("/")}>
          Back to home
        </Anchor>
      </Stack>
    </Center>
  );
}
