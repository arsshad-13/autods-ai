'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  getDataset,
  getDatasetProfile,
  getPreprocessingPlan,
  getTrainedModels,
  getTrainingStatus,
  trainModels,
} from '@/lib/api';
import {
  Dataset,
  DatasetPreprocessingResponse,
  DatasetProfile,
  TrainedModel,
} from '@/types/api';
import { toast } from 'sonner';
import { ArrowLeft, BrainCircuit, Loader2, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { ModelLeaderboard } from '@/components/models/ModelLeaderboard';

/** Poll the training status endpoint every N milliseconds. */
const POLL_INTERVAL_MS = 3000;

export default function ModelTrainingPage() {
  const params = useParams();
  const router = useRouter();
  const uuid = params.uuid as string;

  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [profile, setProfile] = useState<DatasetProfile | null>(null);
  const [preprocessing, setPreprocessing] = useState<DatasetPreprocessingResponse | null>(null);
  const [models, setModels] = useState<TrainedModel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isTraining, setIsTraining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Holds the setInterval handle so we can cancel it on unmount or completion
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ---------------------------------------------------------------------------
  // Polling helpers
  // ---------------------------------------------------------------------------

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const startPolling = useCallback(() => {
    // Cancel any existing poll before starting a new one
    stopPolling();

    pollingRef.current = setInterval(async () => {
      try {
        const statusResponse = await getTrainingStatus(uuid);
        setModels(statusResponse.trained_models);

        if (statusResponse.status === 'COMPLETED') {
          stopPolling();
          setIsTraining(false);
          toast.success('Models trained successfully!');
        } else if (statusResponse.status === 'FAILED') {
          stopPolling();
          setIsTraining(false);
          toast.error(statusResponse.error_message || 'Model training failed.');
        }
        // RUNNING / PENDING → keep polling
      } catch {
        // Transient network error — keep polling, do not surface to user
      }
    }, POLL_INTERVAL_MS);
  }, [uuid, stopPolling]);

  // Clean up the interval when the component is unmounted
  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  // ---------------------------------------------------------------------------
  // Initial data load
  // ---------------------------------------------------------------------------

  useEffect(() => {
    let active = true;

    const loadData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const ds = await getDataset(uuid);
        if (!active) return;
        setDataset(ds);

        const prof = await getDatasetProfile(uuid);
        if (!active) return;
        setProfile(prof);

        const prep = await getPreprocessingPlan(uuid);
        if (!active) return;
        setPreprocessing(prep);

        const trainedModels = await getTrainedModels(uuid);
        if (!active) return;
        setModels(trainedModels);

        // If a training run was already in progress when the page loaded
        // (e.g. user refreshed mid-training), resume polling automatically.
        if (
          trainedModels.some(
            (m) => m.status === 'PENDING' || m.status === 'RUNNING',
          )
        ) {
          setIsTraining(true);
          if (active) startPolling();
        }
      } catch (err: any) {
        if (!active) return;
        setError(err.message || 'Failed to load data for model training.');
      } finally {
        if (active) setIsLoading(false);
      }
    };

    loadData();

    return () => {
      active = false;
    };
  }, [uuid, startPolling]);

  // ---------------------------------------------------------------------------
  // Train button handler
  // ---------------------------------------------------------------------------

  const handleTrainModels = async () => {
    setIsTraining(true);
    toast.dismiss();
    try {
      // POST returns immediately with HTTP 202 — placeholders in PENDING state
      const response = await trainModels(uuid);
      setModels(response.trained_models);
      toast.info('Model training started. This may take a while.', { duration: 5000 });
      // Begin polling for status updates
      startPolling();
    } catch (err: any) {
      toast.error(err.message || 'Failed to start model training.');
      setIsTraining(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (isLoading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[400px] gap-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
        <p className="text-muted-foreground text-sm font-medium">Loading data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 p-8 max-w-4xl mx-auto space-y-6">
        <Button
          variant="ghost"
          onClick={() => router.push(`/datasets/${uuid}/preprocess`)}
          className="gap-2"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Preprocessing
        </Button>
        <Card className="border-destructive/30 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-destructive">Error Loading Data</CardTitle>
            <CardDescription>{error}</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      <div className="flex items-center gap-3">
        <Button
          variant="outline"
          size="icon"
          onClick={() => router.push(`/datasets/${uuid}/preprocess`)}
        >
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-3xl font-bold tracking-tight flex items-center gap-2">
            <BrainCircuit className="h-8 w-8 text-indigo-500" />
            Model Training
          </h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            Train and evaluate machine learning models for {dataset?.original_filename}
          </p>
        </div>
      </div>

      <Card className="shadow-sm">
        <CardHeader>
          <CardTitle>Task Information</CardTitle>
          <CardDescription>
            The selected ML task and target derived from your dataset profile.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 border rounded-md bg-gray-50/50">
              <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                ML Task
              </span>
              <p className="text-lg font-bold text-primary">
                {profile?.recommended_task || 'Unknown'}
              </p>
            </div>
            <div className="p-4 border rounded-md bg-gray-50/50">
              <span className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">
                Target Column
              </span>
              <p className="text-lg font-bold font-mono">
                {profile?.recommended_target || 'None'}
              </p>
            </div>
          </div>

          <div className="mt-6 flex justify-center">
            <Button
              onClick={handleTrainModels}
              disabled={
                isTraining ||
                !preprocessing ||
                preprocessing.status !== 'COMPLETED'
              }
              className="gap-2 px-8 py-6 text-base bg-indigo-600 hover:bg-indigo-700"
            >
              {isTraining ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" /> Training Models...
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" /> Train Models
                </>
              )}
            </Button>
          </div>

          {(!preprocessing || preprocessing.status !== 'COMPLETED') && (
            <p className="text-center text-sm text-destructive mt-3">
              Dataset must be fully preprocessed before training models.
            </p>
          )}
        </CardContent>
      </Card>

      {(models.length > 0 || isTraining) && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle>Model Leaderboard</CardTitle>
            <CardDescription>
              Comparison of all models trained on this dataset. The best model is selected
              automatically.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isTraining && models.every((m) => m.status === 'PENDING' || m.status === 'RUNNING') ? (
              <div className="text-center p-8 border rounded-lg bg-gray-50/50">
                <Loader2 className="h-8 w-8 animate-spin text-primary mx-auto mb-2" />
                <p className="text-gray-500">Training baseline models. Please wait...</p>
              </div>
            ) : (
              <ModelLeaderboard models={models} datasetUuid={uuid} />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
