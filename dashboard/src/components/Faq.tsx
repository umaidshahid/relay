import { Accordion, Container, Grid, Image, Title } from "@mantine/core";
import faqImage from "./faq-image.svg";
import classes from "./Faq.module.css";

const FAQS = [
  {
    value: "what-is-relay",
    question: "What is Relay?",
    answer:
      "Relay is a self-hosted HTTP proxy that sits between your applications and any LLM backend (OpenAI, Ollama, Groq, and others). It records token usage and speed for every request and shows it on a per-user dashboard.",
  },
  {
    value: "credentials",
    question: "Are my provider API keys safe?",
    answer:
      "Yes. Provider keys are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256) with a key you generate and hold outside the database. Even a full database breach does not yield usable credentials. The plaintext is decrypted transiently in memory only at the moment a request is forwarded, and never logged or returned in any response.",
  },
  {
    value: "multiple-backends",
    question: "Can I connect multiple LLM backends?",
    answer:
      "Yes. You can add as many backends as you like, each with its own name, type (OpenAI-compatible or Ollama), URL, and API key. When creating a proxy key you pick which backend it routes to, so different applications can use different providers.",
  },
  {
    value: "rate-limiting",
    question: "How does rate limiting work?",
    answer:
      "Each proxy key has an optional requests-per-minute limit you set when creating it. Relay enforces a sliding-window counter in memory. Requests that exceed the limit receive a 429 response with a Retry-After header.",
  },
  {
    value: "multi-user",
    question: "Can multiple people use the same Relay instance?",
    answer:
      "Yes. Each user signs up independently, configures their own backends and proxy keys, and sees only their own usage. Isolation is enforced at the database layer. No user can access another user's data through any API endpoint.",
  },
  {
    value: "deploy",
    question: "How do I deploy Relay?",
    answer:
      "Run docker compose up at the repo root. Caddy handles HTTPS automatically via Let's Encrypt once you point a subdomain at the server. The full stack (proxy, dashboard, and reverse proxy) starts in one command.",
  },
];

export function Faq() {
  return (
    <div className={classes.wrapper} id="faq">
      <Container size="lg">
        <Grid gutter={50}>
          <Grid.Col span={{ base: 12, md: 5 }}>
            <Image src={faqImage} alt="Frequently Asked Questions" />
          </Grid.Col>
          <Grid.Col span={{ base: 12, md: 7 }}>
            <Title order={2} ta="left" className={classes.title}>
              Frequently Asked Questions
            </Title>
            <Accordion chevronPosition="right" variant="separated">
              {FAQS.map((f) => (
                <Accordion.Item className={classes.item} value={f.value} key={f.value}>
                  <Accordion.Control>{f.question}</Accordion.Control>
                  <Accordion.Panel>{f.answer}</Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          </Grid.Col>
        </Grid>
      </Container>
    </div>
  );
}
