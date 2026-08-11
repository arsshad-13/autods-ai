import { TrainedModel } from "@/types/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface ModelLeaderboardProps {
  models: TrainedModel[];
}

export function ModelLeaderboard({ models }: ModelLeaderboardProps) {
  if (!models || models.length === 0) {
    return (
      <div className="text-center p-8 border rounded-lg bg-gray-50/50">
        <p className="text-gray-500">No models trained yet.</p>
      </div>
    );
  }

  const isClassification = models[0]?.task_type === "Classification";
  const metricsKeys = isClassification 
    ? ["Accuracy", "F1 Score", "Precision", "Recall"] 
    : ["RMSE", "MAE", "R2"];

  return (
    <div className="border rounded-lg overflow-hidden">
      <Table>
        <TableHeader className="bg-gray-50">
          <TableRow>
            <TableHead>Algorithm</TableHead>
            {metricsKeys.map((key) => (
              <TableHead key={key} className="text-right">{key}</TableHead>
            ))}
            <TableHead className="text-right">Duration (s)</TableHead>
            <TableHead className="text-center">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {models.map((model) => (
            <TableRow key={model.uuid} className={model.is_best ? "bg-green-50/30" : ""}>
              <TableCell className="font-medium">
                {model.algorithm}
                {model.is_best && (
                  <Badge variant="default" className="ml-2 bg-green-600 hover:bg-green-700">
                    BEST
                  </Badge>
                )}
              </TableCell>
              {metricsKeys.map((key) => (
                <TableCell key={key} className="text-right">
                  {model.metrics?.[key] !== undefined 
                    ? Number(model.metrics[key]).toFixed(4) 
                    : "-"}
                </TableCell>
              ))}
              <TableCell className="text-right">
                {model.training_duration !== undefined 
                  ? Number(model.training_duration).toFixed(2) 
                  : "-"}
              </TableCell>
              <TableCell className="text-center">
                <Badge variant={model.status === "COMPLETED" ? "default" : "secondary"}>
                  {model.status}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
