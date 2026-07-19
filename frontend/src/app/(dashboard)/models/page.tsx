import { BrainCircuit } from 'lucide-react';

export default function ModelsPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center space-y-4 p-8 text-center text-muted-foreground">
      <div className="rounded-full bg-muted p-6">
        <BrainCircuit className="h-12 w-12" />
      </div>
      <h2 className="text-2xl font-bold tracking-tight text-foreground">Models</h2>
      <p className="max-w-md">
        Coming Soon. This section will allow you to train, evaluate, and deploy machine learning models automatically.
      </p>
    </div>
  );
}
