import { Anchor, Container, Group, Text } from "@mantine/core";
import classes from "./Footer.module.css";

const links = [
  { href: "https://github.com/umaidshahid/relay", label: "GitHub" },
];

export function Footer() {
  return (
    <div className={classes.footer}>
      <Container className={classes.inner}>
        <Text fw={800} size="lg">Relay</Text>
        <Group gap="xl">
          {links.map((link) => (
            <Anchor key={link.label} href={link.href} c="dimmed" size="sm">
              {link.label}
            </Anchor>
          ))}
        </Group>
      </Container>
    </div>
  );
}
