import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { useAuth } from "@/context/AuthContext";
import type { User } from "@/types";

const MOCK_USERS: User[] = [
  { id: "1", email: "analyst@breathe.io", role: "ANALYST" },
  { id: "2", email: "admin@breathe.io",   role: "ADMIN" },
];

export default function LoginPage() {
  const { setUser } = useAuth();
  const navigate    = useNavigate();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const found = MOCK_USERS.find((u) => u.email === email);
    if (!found || password !== "password") {
      setError("Invalid credentials.");
      return;
    }
    setUser(found);
    navigate("/dashboard");
  }

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center">
      <Card className="w-full max-w-sm shadow-sm">
        <CardHeader className="text-center pb-2">
          <div className="mx-auto mb-3 h-10 w-10 rounded-lg bg-neutral-900 text-white
                          flex items-center justify-center text-lg font-bold">
            B
          </div>
          <CardTitle className="text-lg">breathe ESG</CardTitle>
          <p className="text-sm text-muted-foreground">Emissions Review Platform</p>
        </CardHeader>

        <CardContent className="space-y-4">
          <Separator />

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="space-y-1">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {error && (
              <p className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" className="w-full">
              Sign In
            </Button>
          </form>

          <p className="text-xs text-muted-foreground text-center">
            Demo: analyst@breathe.io or admin@breathe.io / password
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
