import { FileText } from 'lucide-react';

export default function ReportsPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center space-y-4 p-8 text-center text-muted-foreground">
      <div className="rounded-full bg-muted p-6">
        <FileText className="h-12 w-12" />
      </div>
      <h2 className="text-2xl font-bold tracking-tight text-foreground">Reports</h2>
      <p className="max-w-md">
        Coming Soon. View generated SHAP explainability reports and comprehensive dashboards here.
      </p>
    </div>
  );
}
