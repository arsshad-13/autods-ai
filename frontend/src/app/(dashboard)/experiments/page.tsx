import { FlaskConical } from 'lucide-react';

export default function ExperimentsPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center space-y-4 p-8 text-center text-muted-foreground">
      <div className="rounded-full bg-muted p-6">
        <FlaskConical className="h-12 w-12" />
      </div>
      <h2 className="text-2xl font-bold tracking-tight text-foreground">Experiments</h2>
      <p className="max-w-md">
        Coming Soon. Track your model tuning and hyperparameter experiments here.
      </p>
    </div>
  );
}
