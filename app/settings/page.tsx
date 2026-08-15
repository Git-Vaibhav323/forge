import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { apiMode } from "@/lib/api";

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-6">
      <h1 className="mb-1 text-[17px] font-semibold">Connection</h1>
      <p className="mb-5 text-[12px] text-muted">
        This desk talks to a FastAPI service when you point it at one. Until
        then it reads a local mock drawer.
      </p>

      <Card>
        <CardHeader>
          <p className="text-[13px] font-medium">Backend</p>
        </CardHeader>
        <CardBody className="space-y-3">
          <div className="flex items-center justify-between text-[13px]">
            <span className="text-muted">Mode</span>
            <span className="font-mono uppercase">{apiMode}</span>
          </div>
          <p className="text-[12px] leading-relaxed text-muted">
            Set <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code> in{" "}
            <code className="font-mono">.env.local</code> to{" "}
            <code className="font-mono">http://localhost:8000</code> after the
            backend is running. Leave it blank to keep using the seeded jobs in{" "}
            <code className="font-mono">lib/mock-data.ts</code>.
          </p>
        </CardBody>
      </Card>
    </div>
  );
}
