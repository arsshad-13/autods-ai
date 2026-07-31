"use client";

import { CheckCircle2, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DatasetPreprocessingResponse } from "@/types/api";

interface PreprocessingSummaryProps {
  preprocessing: DatasetPreprocessingResponse;
}

export function PreprocessingSummary({ preprocessing }: PreprocessingSummaryProps) {
  if (!preprocessing.processing_summary) {
    return null;
  }

  const { messages, quality_before, quality_after } = preprocessing.processing_summary;

  return (
    <Card className="border-green-500/20 bg-green-500/5">
      <CardHeader>
        <CardTitle className="text-xl flex items-center gap-2 text-green-700 dark:text-green-400">
          <CheckCircle2 className="w-5 h-5" />
          Preprocessing Complete
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="space-y-3">
          {messages?.map((msg, idx) => (
            <div key={idx} className="flex items-start gap-2 text-sm">
              <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
              <span>{msg}</span>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-green-500/10">
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs font-medium uppercase">Processing Time</p>
            <div className="flex items-center gap-1.5 font-medium text-sm">
              <Clock className="w-4 h-4 text-muted-foreground" />
              {preprocessing.processing_time?.toFixed(2) || "0.00"} seconds
            </div>
          </div>
          
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs font-medium uppercase">Quality Before</p>
            <p className="font-medium text-sm">{typeof quality_before === 'number' ? `${quality_before.toFixed(0)}%` : 'N/A'}</p>
          </div>
          
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs font-medium uppercase">Quality After</p>
            <p className="font-medium text-sm text-green-600 dark:text-green-400">
              {typeof quality_after === 'number' ? `${quality_after.toFixed(0)}%` : 'N/A'}
            </p>
          </div>
          
          <div className="space-y-1">
            <p className="text-muted-foreground text-xs font-medium uppercase">Output File</p>
            <p className="font-medium text-sm font-mono truncate" title={preprocessing.clean_dataset_path?.split('/').pop() || preprocessing.clean_dataset_path?.split('\\').pop()}>
              {preprocessing.clean_dataset_path?.split('/').pop() || preprocessing.clean_dataset_path?.split('\\').pop() || 'Unknown'}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
