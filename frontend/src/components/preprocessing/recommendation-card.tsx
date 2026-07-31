"use client";

import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent } from "@/components/ui/card";
import { RecommendationSchema } from "@/types/api";

interface RecommendationCardProps {
  recommendation: RecommendationSchema;
  isSelected: boolean;
  onToggle: (id: string, selected: boolean) => void;
  disabled?: boolean;
}

export function RecommendationCard({
  recommendation,
  isSelected,
  onToggle,
  disabled = false,
}: RecommendationCardProps) {
  return (
    <Card className="transition-all hover:border-primary/50 relative overflow-hidden">
      <CardContent className="p-6">
        <div className="flex items-start gap-4">
          <div className="mt-1">
            <Checkbox
              id={`rec-${recommendation.id}`}
              checked={isSelected}
              onCheckedChange={(checked) => onToggle(recommendation.id, checked as boolean)}
              disabled={disabled}
            />
          </div>
          <div className="flex-1 space-y-4">
            <div>
              <label
                htmlFor={`rec-${recommendation.id}`}
                className="text-lg font-medium leading-none cursor-pointer peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                {recommendation.recommendation}
              </label>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div className="space-y-1">
                <p className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Reason</p>
                <p>{recommendation.reason}</p>
              </div>
              
              <div className="space-y-1">
                <p className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Estimated Impact</p>
                <div className="flex items-center gap-2">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    recommendation.estimated_impact === 'High' ? 'bg-red-500/10 text-red-500' :
                    recommendation.estimated_impact === 'Medium' ? 'bg-amber-500/10 text-amber-500' :
                    'bg-green-500/10 text-green-500'
                  }`}>
                    {recommendation.estimated_impact}
                  </span>
                </div>
              </div>

              <div className="space-y-1 md:col-span-2">
                <p className="text-muted-foreground font-medium text-xs uppercase tracking-wider">Affected Columns</p>
                <div className="flex flex-wrap gap-2 mt-1">
                  {recommendation.affected_columns.slice(0, 10).map((col) => (
                    <span key={col} className="inline-flex bg-muted text-muted-foreground px-2 rounded font-mono text-xs py-0.5">
                      {col}
                    </span>
                  ))}
                  {recommendation.affected_columns.length > 10 && (
                    <span className="inline-flex bg-muted text-muted-foreground px-2 rounded font-mono text-xs py-0.5">
                      +{recommendation.affected_columns.length - 10} more
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
