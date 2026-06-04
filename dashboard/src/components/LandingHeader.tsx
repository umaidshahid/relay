import {
  ActionIcon,
  Burger,
  Container,
  Divider,
  Drawer,
  Group,
  ScrollArea,
  Text,
  useMantineColorScheme,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconMoon, IconSun } from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";
import classes from "./LandingHeader.module.css";

const LINKS = [
  { href: "#features", label: "Features" },
  { href: "#faq", label: "FAQ" },
  { href: "/login", label: "Sign in" },
];

export function LandingHeader() {
  const [opened, { toggle, close }] = useDisclosure(false);
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const navigate = useNavigate();

  function handleClick(e: React.MouseEvent<HTMLAnchorElement>, href: string) {
    e.preventDefault();
    if (href.startsWith("#")) {
      document.querySelector(href)?.scrollIntoView({ behavior: "smooth" });
    } else {
      navigate(href);
    }
    close();
  }

  const items = LINKS.map((link) => (
    <a
      key={link.label}
      href={link.href}
      className={classes.link}
      onClick={(e) => handleClick(e, link.href)}
    >
      {link.label}
    </a>
  ));

  return (
    <header className={classes.header}>
      <Container size="lg" className={classes.inner}>
        <Text fw={800} size="lg" style={{ cursor: "pointer" }} onClick={() => navigate("/")}>
          Relay
        </Text>

        <Group gap={4} visibleFrom="xs">
          {items}
          <ActionIcon variant="subtle" onClick={toggleColorScheme} size="lg" aria-label="Toggle color scheme">
            {colorScheme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
          </ActionIcon>
        </Group>

        <Burger opened={opened} onClick={toggle} hiddenFrom="xs" size="sm" aria-label="Toggle navigation" />
      </Container>

      <Drawer
        opened={opened}
        onClose={close}
        size="100%"
        padding="md"
        title="Relay"
        hiddenFrom="xs"
        zIndex={1000000}
      >
        <ScrollArea h="calc(100vh - 80px)" mx="-md">
          <Divider my="sm" />
          {items}
          <Divider my="sm" />
          <Group justify="center" pb="md">
            <ActionIcon variant="subtle" onClick={toggleColorScheme} size="lg">
              {colorScheme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
            </ActionIcon>
          </Group>
        </ScrollArea>
      </Drawer>
    </header>
  );
}
