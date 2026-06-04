import {
  IconActivity,
  IconKey,
  IconServer,
  IconShieldLock,
  IconSwitchHorizontal,
  IconChartBar,
} from "@tabler/icons-react";
import {
  Badge,
  Card,
  Container,
  Group,
  SimpleGrid,
  Text,
  Title,
  useMantineTheme,
} from "@mantine/core";
import classes from "./FeaturesCards.module.css";

const FEATURES = [
  {
    title: "Any LLM backend",
    description:
      "Connect to OpenAI, Groq, Together, any OpenAI-compatible API, or a self-hosted Ollama instance. Switch backends per key without changing your application code.",
    icon: IconServer,
  },
  {
    title: "Per-key rate limiting",
    description:
      "Create multiple proxy keys, each pointing to a different backend. Set a requests-per-minute cap on any key to protect against runaway scripts.",
    icon: IconKey,
  },
  {
    title: "Token and speed metrics",
    description:
      "Every request is logged with input tokens, output tokens, and tokens per second. See averages per model and per key so you know what is fast and what is slow.",
    icon: IconActivity,
  },
  {
    title: "Credential security",
    description:
      "Provider API keys are encrypted at rest with Fernet (AES-128 + HMAC). They never appear in logs, error messages, or API responses. Only a masked suffix is shown.",
    icon: IconShieldLock,
  },
  {
    title: "Multi-user, fully isolated",
    description:
      "Each user has their own backends, proxy keys, and usage history. No user can see or access another user's data. Isolation is enforced at the database layer.",
    icon: IconSwitchHorizontal,
  },
  {
    title: "Live dashboard",
    description:
      "A React dashboard shows your usage in real time: summary cards, a tokens per second chart, breakdown by key and model, and a paginated request log. Auto-refreshes every 30 seconds.",
    icon: IconChartBar,
  },
];

export function FeaturesCards() {
  const theme = useMantineTheme();

  const features = FEATURES.map((f) => (
    <Card key={f.title} shadow="md" radius="md" className={classes.card} padding="xl">
      <f.icon size={40} stroke={1.5} color={theme.colors.blue[6]} />
      <Text fz="lg" fw={500} className={classes.cardTitle} mt="md">
        {f.title}
      </Text>
      <Text fz="sm" c="dimmed" mt="sm">
        {f.description}
      </Text>
    </Card>
  ));

  return (
    <Container size="lg" py="xl" id="features">
      <Group justify="center">
        <Badge variant="filled" size="lg">Features</Badge>
      </Group>

      <Title order={2} className={classes.title} ta="center" mt="sm">
        Everything you need to self-host your LLM proxy
      </Title>

      <Text c="dimmed" className={classes.description} ta="center" mt="md">
        Relay is a single Docker Compose command away. No cloud accounts, no vendor lock-in, no per-seat pricing.
      </Text>

      <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="xl" mt={50}>
        {features}
      </SimpleGrid>
    </Container>
  );
}
