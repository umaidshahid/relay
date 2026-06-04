import {
  Anchor,
  Button,
  Paper,
  PasswordInput,
  Text,
  TextInput,
  Title,
} from "@mantine/core";
import { useForm } from "@mantine/form";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { register } from "../api";
import classes from "./AuthenticationImage.module.css";

export function SignupPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const form = useForm({
    initialValues: { email: "", password: "" },
    validate: {
      email: (v) => (/^\S+@\S+$/.test(v) ? null : "Invalid email"),
      password: (v) => (v.length >= 8 ? null : "Password must be at least 8 characters"),
    },
  });

  async function handleSubmit(values: { email: string; password: string }) {
    setError(null);
    setLoading(true);
    try {
      await register(values.email, values.password);
      await login(values.email, values.password);
      navigate("/app");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed. Try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={classes.wrapper}>
      <Paper className={classes.form} radius={0}>
        <Text ta="center" fw={800} size="xl" className={classes.logo}>
          Relay
        </Text>

        <Title order={2} className={classes.title}>
          Create your account
        </Title>

        <form onSubmit={form.onSubmit(handleSubmit)}>
          <TextInput
            label="Email address"
            placeholder="you@example.com"
            size="md"
            radius="md"
            {...form.getInputProps("email")}
          />
          <PasswordInput
            label="Password"
            placeholder="Min. 8 characters"
            mt="md"
            size="md"
            radius="md"
            {...form.getInputProps("password")}
          />

          {error && (
            <Text c="red" size="sm" mt="sm">
              {error}
            </Text>
          )}

          <Button fullWidth mt="xl" size="md" radius="md" type="submit" loading={loading}>
            Create account
          </Button>
        </form>

        <Text ta="center" mt="md">
          Already have an account?{" "}
          <Anchor fw={500} onClick={() => navigate("/login")}>
            Sign in
          </Anchor>
        </Text>
      </Paper>
    </div>
  );
}
