"use client";

import { useEffect, useState, use } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Play, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DatasetPreprocessingResponse, Dataset } from "@/types/api";
import { PreprocessingTabs } from "@/components/preprocessing/preprocessing-tabs";
import { getDataset, getPreprocessingPlan, generatePreprocessingPlan, applyPreprocessingPlan } from "@/lib/api";

export default function PreprocessPage({ params }: { params: Promise<{ uuid: string }> }) {
  const router = useRouter();
  const { uuid } = use(params);

  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [preprocessing, setPreprocessing] = useState<DatasetPreprocessingResponse | null>(null);
  const [selectedActions, setSelectedActions] = useState<string[]>([]);
  
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  useEffect(() => {
    const fetchDatasetAndPlan = async () => {
      try {
        const ds = await getDataset(uuid);
        setDataset(ds);

        try {
          const data = await getPreprocessingPlan(uuid);
          setPreprocessing(data);
          if (data.recommendations) {
            setSelectedActions(data.recommendations.map((r: any) => r.id));
          }
        } catch (planError: any) {
          // If 404, plan just hasn't been generated yet, which is fine
          if (!planError.message?.includes('404') && !planError.message?.includes('not found')) {
            console.error("Failed to fetch preprocessing plan", planError);
          }
        }
      } catch (error) {
        console.error("Failed to fetch preprocessing data", error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchDatasetAndPlan();
  }, [uuid]);

  const handleGeneratePlan = async () => {
    setIsGenerating(true);
    try {
      const data = await generatePreprocessingPlan(uuid);
      setPreprocessing(data);
      if (data.recommendations) {
        setSelectedActions(data.recommendations.map((r: any) => r.id));
      }
      toast.success("Preprocessing plan generated successfully.");
    } catch (error: any) {
      toast.error(error.message || "Failed to generate plan");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApplyPreprocessing = async () => {
    if (selectedActions.length === 0) {
      toast.error("Please select at least one action to apply.");
      return;
    }

    setIsApplying(true);
    try {
      const data = await applyPreprocessingPlan(uuid, selectedActions);
      setPreprocessing(data);
      toast.success("Preprocessing applied successfully.");
    } catch (error: any) {
      toast.error(error.message || "Failed to apply preprocessing");
    } finally {
      setIsApplying(false);
    }
  };

  const toggleAction = (id: string, selected: boolean) => {
    if (selected) {
      setSelectedActions((prev) => [...prev, id]);
    } else {
      setSelectedActions((prev) => prev.filter((a) => a !== id));
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading preprocessing data...</div>;
  }

  const isPlanGenerated = preprocessing?.status === 'PLAN_GENERATED';
  const isCompleted = preprocessing?.status === 'COMPLETED';

  return (
    <div className="flex flex-col gap-6 max-w-5xl mx-auto w-full pb-24">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
        <div>
          <Button variant="ghost" size="sm" className="-ml-2 mb-2" onClick={() => router.push(`/datasets/${uuid}`)}>
            <ArrowLeft className="w-4 h-4 mr-1" />
            Back to Dataset
          </Button>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">Preprocessing</h1>
            {preprocessing?.status && (
              <Badge variant={
                preprocessing.status === 'COMPLETED' ? 'default' :
                preprocessing.status === 'FAILED' ? 'destructive' :
                'secondary'
              }>
                {preprocessing.status.replace('_', ' ')}
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1">
            {dataset?.original_filename || "Dataset"}
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          {!isCompleted && (
            <Button 
              variant="outline" 
              onClick={handleGeneratePlan}
              disabled={isGenerating || isApplying}
            >
              {isGenerating ? (
                <span className="flex items-center gap-2">
                  <div className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
                  Generating...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Wand2 className="w-4 h-4" />
                  {preprocessing ? 'Regenerate Plan' : 'Generate Plan'}
                </span>
              )}
            </Button>
          )}

          {isPlanGenerated && (
            <Button 
              onClick={handleApplyPreprocessing}
              disabled={isApplying || selectedActions.length === 0}
            >
              {isApplying ? (
                <span className="flex items-center gap-2">
                  <div className="h-4 w-4 rounded-full border-2 border-current border-t-transparent animate-spin" />
                  Applying...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Play className="w-4 h-4" />
                  Apply Preprocessing
                </span>
              )}
            </Button>
          )}

          {isCompleted && (
            <Button 
              onClick={() => router.push(`/datasets/${uuid}/models`)}
              className="bg-indigo-600 hover:bg-indigo-700"
            >
              <span className="flex items-center gap-2">
                Proceed to Model Training
                <ArrowLeft className="w-4 h-4 rotate-180" />
              </span>
            </Button>
          )}
        </div>
      </div>

      {/* Summary Cards (High Level) */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-sm font-medium text-muted-foreground mb-1">Recommendations</p>
            <p className="text-2xl font-bold">{preprocessing?.recommendations?.length || 0}</p>
          </CardContent>
        </Card>
        
        <Card>
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-sm font-medium text-muted-foreground mb-1">Selected Actions</p>
            <p className="text-2xl font-bold">{selectedActions.length}</p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-sm font-medium text-muted-foreground mb-1">Affected Columns</p>
            <p className="text-2xl font-bold">
              {preprocessing?.recommendations
                ? new Set(preprocessing.recommendations.flatMap((r) => r.affected_columns)).size
                : 0}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4 flex flex-col justify-center h-full">
            <p className="text-sm font-medium text-muted-foreground mb-1">Est. Quality Improvement</p>
            <p className="text-2xl font-bold text-green-500">
              {preprocessing?.recommendations?.length ? '+15%' : '0%'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <PreprocessingTabs 
        preprocessing={preprocessing}
        selectedActions={selectedActions}
        onToggleAction={toggleAction}
        isApplying={isApplying}
        datasetUuid={uuid}
      />
    </div>
  );
}
