import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center space-y-4 p-8 text-center text-muted-foreground">
      <div className="rounded-full bg-muted p-6">
        <Settings className="h-12 w-12" />
      </div>
      <h2 className="text-2xl font-bold tracking-tight text-foreground">Settings</h2>
      <p className="max-w-md">
        Coming Soon. Manage your account, API keys, and workspace preferences here.
      </p>
    </div>
  );
}
