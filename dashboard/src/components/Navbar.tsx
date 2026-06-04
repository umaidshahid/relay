import {
  IconKey,
  IconLayoutDashboard,
  IconLogout,
  IconMoon,
  IconServer,
  IconSun,
} from "@tabler/icons-react";
import { Code, Group, Text, useMantineColorScheme } from "@mantine/core";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import classes from "./Navbar.module.css";

const NAV_LINKS = [
  { href: "/app", label: "Dashboard", icon: IconLayoutDashboard },
  { href: "/keys", label: "Proxy Keys", icon: IconKey },
  { href: "/credentials", label: "Backends", icon: IconServer },
];

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  const links = NAV_LINKS.map((item) => (
    <a
      className={classes.link}
      data-active={
        (item.href === "/app"
          ? location.pathname === "/app"
          : location.pathname.startsWith(item.href)) || undefined
      }
      href={item.href}
      key={item.label}
      onClick={(e) => { e.preventDefault(); navigate(item.href); }}
    >
      <item.icon className={classes.linkIcon} stroke={1.5} />
      <span>{item.label}</span>
    </a>
  ));

  return (
    <nav className={classes.navbar}>
      <div className={classes.navbarMain}>
        <Group className={classes.header} justify="space-between">
          <Text fw={800} size="lg">Relay</Text>
          <Code fw={700}>v2.0</Code>
        </Group>
        {links}
      </div>

      <div className={classes.footer}>
        <a
          href="#"
          className={classes.link}
          onClick={(e) => { e.preventDefault(); toggleColorScheme(); }}
        >
          {colorScheme === "dark"
            ? <IconSun className={classes.linkIcon} stroke={1.5} />
            : <IconMoon className={classes.linkIcon} stroke={1.5} />}
          <span>{colorScheme === "dark" ? "Light mode" : "Dark mode"}</span>
        </a>

        {user && (
          <a
            href="#"
            className={classes.link}
            onClick={(e) => { e.preventDefault(); logout(); }}
          >
            <IconLogout className={classes.linkIcon} stroke={1.5} />
            <span>Sign out ({user.email})</span>
          </a>
        )}
      </div>
    </nav>
  );
}
