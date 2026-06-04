import { IconCheck } from "@tabler/icons-react";
import {
  Box,
  Button,
  Container,
  Group,
  List,
  Text,
  ThemeIcon,
  Title,
} from "@mantine/core";
import { useNavigate } from "react-router-dom";
import { Faq } from "../components/Faq";
import { FeaturesCards } from "../components/FeaturesCards";
import { Footer } from "../components/Footer";
import { LandingHeader } from "../components/LandingHeader";
import classes from "../components/Hero.module.css";

const BULLETS = [
  "Route to any OpenAI-compatible or Ollama backend",
  "Multiple proxy keys, each with its own backend and rate limit",
  "Token usage and tokens per second tracked per key and model",
  "Provider credentials encrypted at rest, never exposed",
];

export function LandingPage() {
  const navigate = useNavigate();

  return (
    <Box style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <LandingHeader />

      {/* Hero */}
      <Container size="lg" style={{ flex: 1 }}>
        <div className={classes.inner}>
          <div className={classes.content}>
            <Title className={classes.title}>
              Your self-hosted{" "}
              <span className={classes.highlight}>LLM proxy</span>
            </Title>

            <Text c="dimmed" mt="md" size="lg">
              Relay sits between your apps and any LLM backend. Every token
              is metered, every request is logged, all under your control.
            </Text>

            <List
              mt={30}
              spacing="sm"
              size="sm"
              icon={
                <ThemeIcon size={20} radius="xl" color="blue">
                  <IconCheck size={12} stroke={1.5} />
                </ThemeIcon>
              }
            >
              {BULLETS.map((b) => (
                <List.Item key={b}>{b}</List.Item>
              ))}
            </List>

            <Group mt={40} className={classes.control}>
              <Button radius="xl" size="md" onClick={() => navigate("/login")}>
                Get started
              </Button>
              <Button variant="default" radius="xl" size="md" onClick={() => navigate("/login")}>
                Sign in
              </Button>
            </Group>
          </div>

          {/* Terminal mockup */}
          <Box
            className={classes.visual}
            style={{
              background: "light-dark(var(--mantine-color-gray-0), var(--mantine-color-dark-7))",
              borderRadius: "var(--mantine-radius-md)",
              border: "1px solid light-dark(var(--mantine-color-gray-3), var(--mantine-color-dark-4))",
              padding: "24px",
              fontFamily: "monospace",
              fontSize: 13,
            }}
          >
            <Text c="dimmed" size="xs" mb={4}>$ curl http://relay/v1/chat/completions \</Text>
            <Text c="green" size="xs" mb={4}>{"  "}-H "Authorization: Bearer sk-relay-..."</Text>
            <Text c="dimmed" size="xs" mb="xl">200 OK · 42 tokens · 38 t/s</Text>
            <Box style={{ borderTop: "1px solid light-dark(var(--mantine-color-gray-3), var(--mantine-color-dark-4))", paddingTop: 16 }}>
              <Text size="xs" c="dimmed" mb={8}>Request log</Text>
              {[
                { model: "gemma3:4b",    tps: "41 t/s", tokens: "94" },
                { model: "qwen3.6:35b",  tps: "12 t/s", tokens: "312" },
                { model: "gpt-4o-mini",  tps: "38 t/s", tokens: "58" },
              ].map((r) => (
                <Group key={r.model} justify="space-between" mb={6}>
                  <Text size="xs">{r.model}</Text>
                  <Group gap="xs">
                    <Text size="xs" c="blue">{r.tokens} tok</Text>
                    <Text size="xs" c="green">{r.tps}</Text>
                  </Group>
                </Group>
              ))}
            </Box>
          </Box>
        </div>
      </Container>

      <FeaturesCards />
      <Faq />
      <Footer />
    </Box>
  );
}
