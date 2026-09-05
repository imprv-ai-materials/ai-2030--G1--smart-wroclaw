import type { ReactNode } from "react";

import { Card, CardContent } from "@/components/ui/card";

/** Centered card layout shared by the auth pages. */
export function AuthShell({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="mx-auto w-full max-w-sm px-4 py-10 md:py-16">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {description ? (
        <p className="mt-1.5 text-sm text-muted-foreground">{description}</p>
      ) : null}

      <Card className="mt-6">
        <CardContent>{children}</CardContent>
      </Card>

      {footer ? (
        <div className="mt-4 text-center text-sm text-muted-foreground">
          {footer}
        </div>
      ) : null}
    </div>
  );
}
