import { useState, useCallback } from 'react';
import { TrainedModel } from '@/types/api';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  AlertTriangle,
  Award,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Info,
  Layers,
  Loader2,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Zap,
} from 'lucide-react';
import { tuneModel, getModelDetails } from '@/lib/api';

interface ModelLeaderboardProps {
  models: TrainedModel[];
  datasetUuid?: string;
}

// Tuning status values we consider "active" (show spinner)
const TUNING_ACTIVE = new Set(['QUEUED', 'RUNNING']);

export function ModelLeaderboard({ models, datasetUuid }: ModelLeaderboardProps) {
  const [selectedModelUuid, setSelectedModelUuid] = useState<string | null>(null);
  const [tuningStates, setTuningStates] = useState<Record<string, string>>({});
  const [localModels, setLocalModels] = useState<TrainedModel[]>(models);
  const [tuningError, setTuningError] = useState<Record<string, string>>({});

  const effectiveModels = localModels.length >= models.length ? localModels : models;

  const handleTune = useCallback(
    async (model: TrainedModel) => {
      const uuid = model.uuid;
      const targetDatasetUuid = datasetUuid || (model.metadata_info?.dataset_uuid as string) || '';
      if (!targetDatasetUuid) {
        setTuningError((prev) => ({
          ...prev,
          [uuid]: 'Dataset UUID is required to tune this model.',
        }));
        return;
      }
      setTuningStates((prev) => ({ ...prev, [uuid]: 'QUEUED' }));
      setTuningError((prev) => {
        const n = { ...prev };
        delete n[uuid];
        return n;
      });

      try {
        await tuneModel(targetDatasetUuid, uuid, 30);
        // Start polling until COMPLETED or FAILED
        const poll = async () => {
          const updated = await getModelDetails(targetDatasetUuid, uuid);
          const ts = (updated.metadata_info?.tuning_status as string) || 'RUNNING';
          setTuningStates((prev) => ({ ...prev, [uuid]: ts }));
          setLocalModels((prev) =>
            prev.map((m) => (m.uuid === uuid ? updated : m))
          );
          if (TUNING_ACTIVE.has(ts)) {
            setTimeout(poll, 3000);
          }
        };
        setTimeout(poll, 3000);
      } catch (e: any) {
        setTuningStates((prev) => ({ ...prev, [uuid]: 'FAILED' }));
        setTuningError((prev) => ({
          ...prev,
          [uuid]: e.message || 'Tuning request failed.',
        }));
      }
    },
    [datasetUuid]
  );

  if (!effectiveModels || effectiveModels.length === 0) {
    return (
      <div className="text-center p-8 border rounded-lg bg-gray-50/50">
        <p className="text-gray-500">No models trained yet.</p>
      </div>
    );
  }

  const firstModel = effectiveModels[0];
  const isClassification = firstModel?.task_type === 'Classification';
  const metadata = firstModel?.metadata_info || {};
  const evalMethod = metadata.evaluation_method || {};
  const datasetWarning = metadata.dataset_size_warning;
  const leakageChecks = metadata.leakage_checks;
  const isTimeSeriesTask = firstModel?.task_type === 'Time Series' || firstModel?.task_type === 'Forecasting';

  const selectedModel = effectiveModels.find((m) => m.uuid === selectedModelUuid) || null;

  return (
    <div className="space-y-6">
      {/* 1. Evaluation Methodology Banner */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        <div className="p-3 border rounded-lg bg-indigo-50/50 flex items-start gap-2.5">
          <Layers className="h-5 w-5 text-indigo-600 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-semibold uppercase text-indigo-900 tracking-wider">
              Train / Test Split
            </div>
            <div className="text-sm font-medium text-indigo-950 mt-0.5">
              {evalMethod.split || (isClassification ? '80/20 Stratified Split' : '80/20 Split')}
            </div>
          </div>
        </div>

        <div className="p-3 border rounded-lg bg-blue-50/50 flex items-start gap-2.5">
          <Zap className="h-5 w-5 text-blue-600 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-semibold uppercase text-blue-900 tracking-wider">
              Cross-Validation
            </div>
            <div className="text-sm font-medium text-blue-950 mt-0.5">
              {evalMethod.cv || metadata.cv_method || 'Adaptive Cross-Validation'}
            </div>
          </div>
        </div>

        <div className="p-3 border rounded-lg bg-amber-50/50 flex items-start gap-2.5">
          <Award className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-semibold uppercase text-amber-900 tracking-wider">
              Selection Metric
            </div>
            <div className="text-sm font-medium text-amber-950 mt-0.5">
              {evalMethod.primary_metric || (isClassification ? 'F1 Score (Generalization)' : 'RMSE (Lower is better)')}
            </div>
          </div>
        </div>

        <div className="p-3 border rounded-lg bg-emerald-50/50 flex items-start gap-2.5">
          <ShieldCheck className="h-5 w-5 text-emerald-600 mt-0.5 shrink-0" />
          <div>
            <div className="text-xs font-semibold uppercase text-emerald-900 tracking-wider">
              Leakage Protection
            </div>
            <div className="text-sm font-medium text-emerald-950 mt-0.5">
              {leakageChecks?.checks_passed !== false ? 'Verified Leakage-Free' : 'Checks Completed'}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Small Dataset Warning Alert */}
      {datasetWarning && (
        <div className="flex items-center gap-3 p-3.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-lg text-sm">
          <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0" />
          <div>
            <span className="font-semibold">Dataset Size Notice: </span>
            {datasetWarning}
          </div>
        </div>
      )}

      {/* 3. Main Leaderboard Table */}
      <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
        <Table>
          <TableHeader className="bg-gray-50/80">
            <TableRow>
              <TableHead className="font-semibold">Algorithm</TableHead>
              <TableHead className="text-right font-semibold">
                {isClassification ? 'Accuracy' : 'RMSE'}
              </TableHead>
              <TableHead className="text-right font-semibold">
                {isClassification ? 'F1 Score' : 'MAE'}
              </TableHead>
              {isClassification && (
                <>
                  <TableHead className="text-right font-semibold">Precision</TableHead>
                  <TableHead className="text-right font-semibold">Recall</TableHead>
                  <TableHead className="text-right font-semibold">ROC-AUC</TableHead>
                </>
              )}
              {!isClassification && (
                <TableHead className="text-right font-semibold">R² Score</TableHead>
              )}
              <TableHead className="text-right font-semibold">CV Score</TableHead>
              <TableHead className="text-center font-semibold">Generalization</TableHead>
              <TableHead className="text-right font-semibold">Time (s)</TableHead>
              <TableHead className="text-center font-semibold">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {effectiveModels.map((model) => {
              const mMeta = model.metadata_info || {};
              const isSelected = selectedModelUuid === model.uuid;
              const genStatus = mMeta.generalization_status || 'Good Generalization';
              const cvScore = model.metrics?.['CV Score'] ?? mMeta.cv_score;
              const cvStd = model.metrics?.['CV Score Std'] ?? mMeta.cv_score_std;

              // Tuning state: prefer live poll state, fall back to metadata_info
              const tuningStatus =
                tuningStates[model.uuid] || mMeta.tuning_status || null;
              const isTuning = tuningStatus ? TUNING_ACTIVE.has(tuningStatus) : false;
              const wasTuned = tuningStatus === 'COMPLETED';
              const tuneImproved = mMeta.tuning_improved === true;
              const canTune = model.status === 'COMPLETED' && !isTuning && !isTimeSeriesTask;

              return (
                <TableRow
                  key={model.uuid}
                  className={`transition-colors ${
                    model.is_best ? 'bg-emerald-50/30' : ''
                  } ${isSelected ? 'bg-indigo-50/40' : ''}`}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span>{model.algorithm}</span>
                      {model.is_best && (
                        <Badge className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold">
                          BEST MODEL
                        </Badge>
                      )}
                      {wasTuned && tuneImproved && (
                        <Badge className="bg-violet-600 hover:bg-violet-700 text-white font-semibold gap-1">
                          <TrendingUp className="h-3 w-3" />
                          TUNED
                        </Badge>
                      )}
                      {wasTuned && !tuneImproved && (
                        <Badge variant="outline" className="border-violet-300 text-violet-700 bg-violet-50 font-semibold gap-1">
                          <Sparkles className="h-3 w-3" />
                          Tuned (no gain)
                        </Badge>
                      )}
                      {isTuning && (
                        <Badge variant="outline" className="border-blue-300 text-blue-700 bg-blue-50 gap-1">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          {tuningStatus}
                        </Badge>
                      )}
                      {tuningStatus === 'FAILED' && (
                        <Badge variant="outline" className="border-rose-300 text-rose-700 bg-rose-50">
                          Tune Failed
                        </Badge>
                      )}
                    </div>
                    {tuningError[model.uuid] && (
                      <p className="text-xs text-rose-600 mt-1">{tuningError[model.uuid]}</p>
                    )}
                  </TableCell>

                  <TableCell className="text-right font-mono">
                    {isClassification
                      ? model.metrics?.['Accuracy'] !== undefined
                        ? Number(model.metrics['Accuracy']).toFixed(4)
                        : '-'
                      : model.metrics?.['RMSE'] !== undefined
                      ? Number(model.metrics['RMSE']).toFixed(4)
                      : '-'}
                  </TableCell>

                  <TableCell className="text-right font-mono">
                    {isClassification
                      ? model.metrics?.['F1 Score'] !== undefined
                        ? Number(model.metrics['F1 Score']).toFixed(4)
                        : '-'
                      : model.metrics?.['MAE'] !== undefined
                      ? Number(model.metrics['MAE']).toFixed(4)
                      : '-'}
                  </TableCell>

                  {isClassification && (
                    <>
                      <TableCell className="text-right font-mono">
                        {model.metrics?.['Precision'] !== undefined
                          ? Number(model.metrics['Precision']).toFixed(4)
                          : '-'}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {model.metrics?.['Recall'] !== undefined
                          ? Number(model.metrics['Recall']).toFixed(4)
                          : '-'}
                      </TableCell>
                      <TableCell className="text-right font-mono">
                        {model.metrics?.['ROC-AUC'] !== undefined
                          ? Number(model.metrics['ROC-AUC']).toFixed(4)
                          : '-'}
                      </TableCell>
                    </>
                  )}

                  {!isClassification && (
                    <TableCell className="text-right font-mono">
                      {model.metrics?.['R2'] !== undefined
                        ? Number(model.metrics['R2']).toFixed(4)
                        : '-'}
                    </TableCell>
                  )}

                  <TableCell className="text-right font-mono">
                    {cvScore !== undefined && cvScore !== null ? (
                      <span title={cvStd ? `Std: ±${Number(cvStd).toFixed(4)}` : undefined}>
                        {Number(cvScore).toFixed(4)}
                        {cvStd !== undefined && cvStd !== null && (
                          <span className="text-xs text-muted-foreground ml-1">
                            ±{Number(cvStd).toFixed(2)}
                          </span>
                        )}
                      </span>
                    ) : (
                      '-'
                    )}
                  </TableCell>

                  <TableCell className="text-center">
                    <Badge
                      variant="outline"
                      className={
                        genStatus.includes('Severe')
                          ? 'border-rose-300 text-rose-700 bg-rose-50'
                          : genStatus.includes('Moderate')
                          ? 'border-amber-300 text-amber-700 bg-amber-50'
                          : 'border-emerald-300 text-emerald-700 bg-emerald-50'
                      }
                    >
                      {genStatus}
                    </Badge>
                  </TableCell>

                  <TableCell className="text-right text-muted-foreground font-mono">
                    {model.training_duration !== undefined
                      ? Number(model.training_duration).toFixed(2)
                      : '-'}
                  </TableCell>

                  <TableCell className="text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      {/* Details toggle */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() =>
                          setSelectedModelUuid(isSelected ? null : model.uuid)
                        }
                        className="gap-1 h-8 text-xs font-medium"
                      >
                        {isSelected ? (
                          <>
                            Hide <ChevronUp className="h-3.5 w-3.5" />
                          </>
                        ) : (
                          <>
                            Details <ChevronDown className="h-3.5 w-3.5" />
                          </>
                        )}
                      </Button>

                      {/* Tune button — hidden for time series */}
                      {!isTimeSeriesTask && (
                        <Button
                          variant="outline"
                          size="sm"
                          disabled={!canTune}
                          onClick={() => handleTune(model)}
                          className={`gap-1 h-8 text-xs font-medium transition-all ${
                            canTune
                              ? 'border-violet-300 text-violet-700 hover:bg-violet-50 hover:border-violet-400'
                              : 'opacity-50'
                          }`}
                          title={
                            isTimeSeriesTask
                              ? 'Tuning not supported for Time Series models'
                              : isTuning
                              ? 'Tuning in progress…'
                              : 'Run Optuna hyperparameter optimization'
                          }
                        >
                          {isTuning ? (
                            <>
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              Tuning…
                            </>
                          ) : (
                            <>
                              <Sparkles className="h-3.5 w-3.5" />
                              {wasTuned ? 'Re-tune' : 'Tune'}
                            </>
                          )}
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      {/* 4. Expanded Model Detail View */}
      {selectedModel && (
        <Card className="border-indigo-200 bg-indigo-50/10 shadow-sm animate-in fade-in duration-200">
          <CardHeader className="pb-3 border-b bg-gray-50/40">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <span>{selectedModel.name}</span>
                  {selectedModel.is_best && (
                    <Badge className="bg-emerald-600 hover:bg-emerald-700 text-white">
                      BEST GENERALIZING MODEL
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  Detailed evaluation metrics, train/test comparison, and verification diagnostics.
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedModelUuid(null)}
              >
                Close
              </Button>
            </div>
          </CardHeader>

          <CardContent className="pt-5 space-y-6">
            {/* Score Comparison Cards */}
            <div>
              <h4 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
                <Layers className="h-4 w-4 text-indigo-600" />
                Train vs Test vs Cross-Validation Comparison
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="p-3.5 border rounded-md bg-white">
                  <span className="text-xs text-muted-foreground font-medium uppercase">
                    Training Score
                  </span>
                  <div className="text-xl font-bold text-gray-900 mt-1 font-mono">
                    {isClassification
                      ? selectedModel.metrics?.['Train Accuracy'] !== undefined
                        ? Number(selectedModel.metrics['Train Accuracy']).toFixed(4)
                        : '-'
                      : selectedModel.metrics?.['Train RMSE'] !== undefined
                      ? Number(selectedModel.metrics['Train RMSE']).toFixed(4)
                      : '-'}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Fitted on {selectedModel.metadata_info?.train_rows || '80%'} rows
                  </span>
                </div>

                <div className="p-3.5 border rounded-md bg-white border-indigo-200">
                  <span className="text-xs text-indigo-700 font-semibold uppercase">
                    Test Score (Holdout)
                  </span>
                  <div className="text-xl font-bold text-indigo-600 mt-1 font-mono">
                    {isClassification
                      ? selectedModel.metrics?.['Accuracy'] !== undefined
                        ? Number(selectedModel.metrics['Accuracy']).toFixed(4)
                        : '-'
                      : selectedModel.metrics?.['RMSE'] !== undefined
                      ? Number(selectedModel.metrics['RMSE']).toFixed(4)
                      : '-'}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    Evaluated on {selectedModel.metadata_info?.test_rows || '20%'} holdout rows
                  </span>
                </div>

                <div className="p-3.5 border rounded-md bg-white">
                  <span className="text-xs text-muted-foreground font-medium uppercase">
                    Cross-Validation (Mean)
                  </span>
                  <div className="text-xl font-bold text-gray-900 mt-1 font-mono">
                    {selectedModel.metrics?.['CV Score'] !== undefined &&
                    selectedModel.metrics?.['CV Score'] !== null
                      ? Number(selectedModel.metrics['CV Score']).toFixed(4)
                      : 'N/A'}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {selectedModel.metadata_info?.cv_method || 'Adaptive CV'}
                  </span>
                </div>
              </div>
            </div>

            {/* Optuna Tuning Results Panel */}
            {selectedModel.metadata_info?.tuning_status && (
              <div>
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
                  <Sparkles className="h-4 w-4 text-violet-600" />
                  Optuna Hyperparameter Tuning Results
                </h4>
                <div className="border rounded-md bg-violet-50/30 p-4 space-y-4">
                  {/* Summary row */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-white border rounded p-3 text-center">
                      <div className="text-xs text-muted-foreground mb-1">Status</div>
                      <Badge
                        className={
                          selectedModel.metadata_info.tuning_status === 'COMPLETED'
                            ? 'bg-violet-600 text-white'
                            : selectedModel.metadata_info.tuning_status === 'FAILED'
                            ? 'bg-rose-600 text-white'
                            : 'bg-blue-500 text-white'
                        }
                      >
                        {selectedModel.metadata_info.tuning_status}
                      </Badge>
                    </div>
                    <div className="bg-white border rounded p-3 text-center">
                      <div className="text-xs text-muted-foreground mb-1">Trials Run</div>
                      <div className="font-bold font-mono text-lg">
                        {selectedModel.metadata_info.tuning_n_trials ?? '-'}
                      </div>
                    </div>
                    <div className="bg-white border rounded p-3 text-center">
                      <div className="text-xs text-muted-foreground mb-1">Duration (s)</div>
                      <div className="font-bold font-mono text-lg">
                        {selectedModel.metadata_info.tuning_duration !== undefined
                          ? Number(selectedModel.metadata_info.tuning_duration).toFixed(1)
                          : '-'}
                      </div>
                    </div>
                    <div className="bg-white border rounded p-3 text-center">
                      <div className="text-xs text-muted-foreground mb-1">Improved</div>
                      {selectedModel.metadata_info.tuning_status === 'COMPLETED' ? (
                        <Badge
                          className={
                            selectedModel.metadata_info.tuning_improved
                              ? 'bg-emerald-600 text-white'
                              : 'bg-gray-400 text-white'
                          }
                        >
                          {selectedModel.metadata_info.tuning_improved ? 'Yes' : 'No'}
                        </Badge>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </div>
                  </div>

                  {/* Baseline vs Tuned comparison */}
                  {selectedModel.metadata_info.tuning_status === 'COMPLETED' &&
                    selectedModel.metadata_info.tuning_baseline_score !== undefined && (
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
                        <div className="bg-white border rounded p-3">
                          <div className="text-xs text-muted-foreground mb-1 font-medium uppercase">
                            Baseline {selectedModel.metadata_info.tuning_metric}
                          </div>
                          <div className="font-bold font-mono text-base">
                            {Number(selectedModel.metadata_info.tuning_baseline_score).toFixed(6)}
                          </div>
                        </div>
                        <div className="bg-white border border-violet-200 rounded p-3">
                          <div className="text-xs text-violet-700 mb-1 font-semibold uppercase">
                            Tuned {selectedModel.metadata_info.tuning_metric}
                          </div>
                          <div className="font-bold font-mono text-base text-violet-700">
                            {Number(selectedModel.metadata_info.tuning_tuned_score).toFixed(6)}
                          </div>
                        </div>
                        <div className="bg-white border rounded p-3">
                          <div className="text-xs text-muted-foreground mb-1 font-medium uppercase">
                            Best CV Score
                          </div>
                          <div className="font-bold font-mono text-base">
                            {selectedModel.metadata_info.tuning_best_score !== undefined
                              ? Number(selectedModel.metadata_info.tuning_best_score).toFixed(6)
                              : '-'}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Trial #{selectedModel.metadata_info.tuning_best_trial}
                          </div>
                        </div>
                      </div>
                    )}

                  {/* Best params */}
                  {selectedModel.metadata_info.tuning_best_params && (
                    <div>
                      <div className="text-xs font-semibold text-violet-800 mb-1.5 uppercase tracking-wide">
                        Best Hyperparameters
                      </div>
                      <div className="p-3 border rounded bg-white text-xs font-mono max-h-32 overflow-y-auto">
                        <pre>{JSON.stringify(selectedModel.metadata_info.tuning_best_params, null, 2)}</pre>
                      </div>
                    </div>
                  )}

                  {/* Tuning error */}
                  {selectedModel.metadata_info.tuning_error && (
                    <div className="flex items-start gap-2 p-3 bg-rose-50 border border-rose-200 rounded text-rose-800 text-xs">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                      <span>{selectedModel.metadata_info.tuning_error}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Confusion Matrix (Classification only) */}
            {isClassification && selectedModel.metadata_info?.confusion_matrix && (
              <div>
                <h4 className="text-sm font-semibold mb-3 flex items-center gap-1.5">
                  <Info className="h-4 w-4 text-indigo-600" />
                  Holdout Confusion Matrix
                </h4>
                <div className="p-4 border rounded-md bg-white max-w-sm">
                  <div className="text-xs text-muted-foreground mb-2 text-center font-medium">
                    Rows: True Class | Columns: Predicted Class
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-center font-mono">
                    {selectedModel.metadata_info.confusion_matrix.map(
                      (row: number[], rIdx: number) =>
                        row.map((val: number, cIdx: number) => (
                          <div
                            key={`${rIdx}-${cIdx}`}
                            className={`p-3 rounded border font-semibold text-base ${
                              rIdx === cIdx
                                ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                                : 'bg-rose-50 text-rose-800 border-rose-200'
                            }`}
                          >
                            {val}
                          </div>
                        ))
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Leakage Checks & Diagnostics */}
            {selectedModel.metadata_info?.leakage_checks && (
              <div>
                <h4 className="text-sm font-semibold mb-2 flex items-center gap-1.5">
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                  Automated Leakage & Quality Diagnostics
                </h4>
                <div className="p-3 border rounded-md bg-white text-xs space-y-1.5">
                  <div className="flex items-center gap-2 text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Target column explicitly excluded from model features.</span>
                  </div>
                  <div className="flex items-center gap-2 text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Preprocessing and scaling fitted strictly on training partition only.</span>
                  </div>
                  <div className="flex items-center gap-2 text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>Holdout predictions generated via encapsulated sklearn Pipeline.</span>
                  </div>
                  {selectedModel.metadata_info?.tuning_status === 'COMPLETED' && (
                    <div className="flex items-center gap-2 text-violet-700">
                      <CheckCircle2 className="h-4 w-4" />
                      <span>
                        Optuna search used CV on X_train only — holdout test set never touched during optimization.
                      </span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Hyperparameters */}
            {selectedModel.hyperparameters && (
              <div>
                <h4 className="text-sm font-semibold mb-2">
                  Model Hyperparameters
                  {selectedModel.metadata_info?.tuning_improved && (
                    <span className="ml-2 text-violet-600 font-normal text-xs">
                      (Optuna-optimized)
                    </span>
                  )}
                </h4>
                <div className="p-3 border rounded-md bg-gray-50 text-xs font-mono max-h-36 overflow-y-auto">
                  <pre>{JSON.stringify(selectedModel.hyperparameters, null, 2)}</pre>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
