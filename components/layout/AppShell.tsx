import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-8 items-center justify-between border-b border-line bg-panel px-5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted">
          <span>Catalog desk</span>
          <span>Local session · files stay on this machine</span>
        </div>
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}
