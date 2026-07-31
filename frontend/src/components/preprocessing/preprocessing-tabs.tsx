"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DatasetPreprocessingResponse } from "@/types/api";
import { RecommendationCard } from "./recommendation-card";
import { PreprocessingSummary } from "./preprocessing-summary";
import { Button } from "@/components/ui/button";
import { Download } from "lucide-react";
import { downloadCleanedDataset } from "@/lib/api";
import { toast } from "sonner";

interface PreprocessingTabsProps {
  preprocessing: DatasetPreprocessingResponse | null;
  selectedActions: string[];
  onToggleAction: (id: string, selected: boolean) => void;
  isApplying: boolean;
  datasetUuid: string;
}

export function PreprocessingTabs({
  preprocessing,
  selectedActions,
  onToggleAction,
  isApplying,
  datasetUuid,
}: PreprocessingTabsProps) {
  const [activeTab, setActiveTab] = useState("recommendations");

  if (!preprocessing || preprocessing.status === 'NOT_GENERATED') {
    return (
      <div className="flex flex-col items-center justify-center p-12 border rounded-lg bg-muted/20 border-dashed">
        <p className="text-muted-foreground text-center">
          No preprocessing plan generated yet. <br />
          Click &quot;Generate Preprocessing Plan&quot; to analyze the dataset.
        </p>
      </div>
    );
  }

  const isCompleted = preprocessing.status === 'COMPLETED';

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
      <TabsList className="grid w-full grid-cols-3 max-w-[400px]">
        <TabsTrigger value="recommendations">Recommendations</TabsTrigger>
        <TabsTrigger value="summary" disabled={!isCompleted}>Summary</TabsTrigger>
        <TabsTrigger value="download" disabled={!isCompleted}>Download</TabsTrigger>
      </TabsList>

      <TabsContent value="recommendations" className="space-y-4">
        {isCompleted && (
          <div className="mb-6 p-4 border border-amber-500/20 bg-amber-500/10 rounded-lg text-amber-600 dark:text-amber-400 text-sm">
            Preprocessing has already been applied. You can generate a new plan or view the summary.
          </div>
        )}
        
        <div className="grid gap-4">
          {preprocessing.recommendations?.map((rec) => (
            <RecommendationCard
              key={rec.id}
              recommendation={rec}
              isSelected={selectedActions.includes(rec.id)}
              onToggle={onToggleAction}
              disabled={isApplying || isCompleted}
            />
          ))}
          {(!preprocessing.recommendations || preprocessing.recommendations.length === 0) && (
            <div className="p-8 text-center border rounded-lg text-muted-foreground">
              No preprocessing recommendations found. Your dataset looks clean!
            </div>
          )}
        </div>
      </TabsContent>

      <TabsContent value="summary" className="space-y-4">
        {isCompleted && <PreprocessingSummary preprocessing={preprocessing} />}
      </TabsContent>

      <TabsContent value="download" className="space-y-4">
        {isCompleted && (
          <div className="flex flex-col items-center justify-center p-12 border rounded-lg gap-6">
            <div className="text-center space-y-2">
              <h3 className="text-xl font-semibold">Cleaned Dataset Ready</h3>
              <p className="text-muted-foreground max-w-md">
                Your dataset has been processed and is ready for download. 
                The file is versioned and will not overwrite your original upload.
              </p>
            </div>
            
            <Button 
              size="lg" 
              className="gap-2" 
              onClick={async () => {
                try {
                  await downloadCleanedDataset(datasetUuid);
                  toast.success("Download started successfully.");
                } catch (error: any) {
                  toast.error(error.message || "Failed to download dataset");
                }
              }}
            >
              <Download className="w-4 h-4" />
              Download Dataset
            </Button>
          </div>
        )}
      </TabsContent>
    </Tabs>
  );
}
